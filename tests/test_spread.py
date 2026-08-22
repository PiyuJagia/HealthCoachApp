"""Offline tests for F4.9 / T12 within-window HRV spread."""

from __future__ import annotations

import json
import unittest
from datetime import date, timedelta
from statistics import mean, stdev

from agent.instructions import HEALTH_COACH_INSTRUCTIONS
from agent.model_observe import extract_within_window_spread, observe_llm_request
from analytics.maturity import STATE_EARLY_PATTERN, STATE_ESTABLISHED_TREND
from analytics.schemas import ClaimEligibility
from analytics.spread import (
    MIN_SPREAD_COMPARISON_CURRENT,
    MIN_USABLE_BASELINE_SPREAD,
    build_within_window_spread,
)
from analytics.trends import get_health_trends
from app.health_tools import get_health_trends_for_agent
from data.demo_seed import seed_demo_health_data
from data.models import HealthDaily
from data.repository import create_user, upsert_health_daily
from evals.trace_schema import ORIGIN_SPREAD_ANALYTICS
from tests.test_helpers import open_test_session
from tests.test_model_observe import _sample_request

C4 = date(2026, 7, 28)
B1 = date(2026, 6, 18)
C4_CURRENT_HRV = (28.7, 48.9, 30.5, 44.9, 25.7, 44.4, 24.7)


def _claim(*, trend_allowed: bool = True) -> ClaimEligibility:
    return ClaimEligibility(
        snapshot_allowed=True,
        early_pattern_allowed=True,
        trend_allowed=trend_allowed,
        recommendation_support_allowed=trend_allowed,
        recommendation_basis="established_trend" if trend_allowed else "none",
    )


def _day(
    *,
    sleep: float | None = 7.0,
    rhr: float | None = 70.0,
    hrv: float | None = 32.0,
    exercise: float | None = 12.0,
    workouts: int | None = 0,
    steps: int | None = 8000,
    vo2: float | None = 40.0,
    rr: float | None = 14.5,
) -> dict:
    return {
        "sleep_duration_hours": sleep,
        "resting_hr_bpm": rhr,
        "hrv_sdnn_ms": hrv,
        "exercise_minutes": exercise,
        "workout_count": workouts,
        "steps": steps,
        "vo2_max": vo2,
        "respiratory_rate": rr,
    }


def _write_days(session, user_id: int, start: date, days: list[dict]) -> None:
    for offset, fields in enumerate(days):
        upsert_health_daily(
            session,
            HealthDaily(user_id=user_id, date=start + timedelta(days=offset), **fields),
        )
    session.commit()


def _by_metric(trends) -> dict:
    return {item.metric: item for item in trends}


def _round2(value: float) -> float:
    return round(value, 2)


class SpreadUnitTests(unittest.TestCase):
    def test_non_hrv_metric_returns_none(self) -> None:
        self.assertIsNone(
            build_within_window_spread(
                metric="vo2_max",
                current_values=[40.0, 40.1],
                baseline_values=[39.8, 39.9, 40.0],
                claim=_claim(),
                baseline_ready=True,
                partial_coverage=False,
                gap_caveat_required=False,
            )
        )
        self.assertIsNone(
            build_within_window_spread(
                metric="respiratory_rate",
                current_values=[14.4, 14.6, 14.5],
                baseline_values=[14.5, 14.4, 14.6],
                claim=_claim(),
                baseline_ready=True,
                partial_coverage=False,
                gap_caveat_required=False,
            )
        )

    def test_single_observation_is_facts_only(self) -> None:
        spread = build_within_window_spread(
            metric="hrv_sdnn_ms",
            current_values=[32.0],
            baseline_values=[31.0, 32.0, 33.0],
            claim=_claim(),
            baseline_ready=True,
            partial_coverage=True,
            gap_caveat_required=False,
        )
        assert spread is not None
        self.assertEqual(spread.observation_count, 1)
        self.assertIsNone(spread.sample_standard_deviation)
        self.assertFalse(spread.spread_observation_allowed)
        self.assertFalse(spread.spread_comparison_allowed)
        self.assertIsNone(spread.spread_ratio)

    def test_three_current_observations_allow_facts_not_comparison(self) -> None:
        current = [28.0, 36.0, 32.0]
        spread = build_within_window_spread(
            metric="hrv_sdnn_ms",
            current_values=current,
            baseline_values=[31.0, 32.0, 33.0, 32.5],
            claim=_claim(),
            baseline_ready=True,
            partial_coverage=False,
            gap_caveat_required=False,
        )
        assert spread is not None
        self.assertEqual(spread.observation_count, 3)
        self.assertLess(spread.observation_count, MIN_SPREAD_COMPARISON_CURRENT)
        self.assertTrue(spread.spread_observation_allowed)
        self.assertFalse(spread.spread_comparison_allowed)
        self.assertIsNone(spread.spread_ratio)
        self.assertEqual(spread.sample_standard_deviation, _round2(stdev(current)))

    def test_near_zero_baseline_sd_blocks_ratio(self) -> None:
        current = [28.0, 36.0, 30.0, 34.0]
        spread = build_within_window_spread(
            metric="hrv_sdnn_ms",
            current_values=current,
            baseline_values=[32.0] * 20,
            claim=_claim(),
            baseline_ready=True,
            partial_coverage=False,
            gap_caveat_required=False,
        )
        assert spread is not None
        self.assertEqual(spread.baseline_standard_deviation, 0.0)
        self.assertLess(spread.baseline_standard_deviation, MIN_USABLE_BASELINE_SPREAD)
        self.assertTrue(spread.spread_observation_allowed)
        self.assertFalse(spread.spread_comparison_allowed)
        self.assertIsNone(spread.spread_ratio)

    def test_immature_or_partial_or_gap_blocks_comparison(self) -> None:
        current = [28.0, 36.0, 30.0, 34.0, 29.0]
        baseline = [31.0, 32.0, 33.0, 32.5, 31.5]
        kwargs = {
            "metric": "hrv_sdnn_ms",
            "current_values": current,
            "baseline_values": baseline,
        }
        blocked = [
            build_within_window_spread(
                **kwargs,
                claim=_claim(trend_allowed=False),
                baseline_ready=True,
                partial_coverage=False,
                gap_caveat_required=False,
            ),
            build_within_window_spread(
                **kwargs,
                claim=_claim(),
                baseline_ready=False,
                partial_coverage=False,
                gap_caveat_required=False,
            ),
            build_within_window_spread(
                **kwargs,
                claim=_claim(),
                baseline_ready=True,
                partial_coverage=True,
                gap_caveat_required=False,
            ),
            build_within_window_spread(
                **kwargs,
                claim=_claim(),
                baseline_ready=True,
                partial_coverage=False,
                gap_caveat_required=True,
            ),
        ]
        for spread in blocked:
            assert spread is not None
            self.assertTrue(spread.spread_observation_allowed)
            self.assertFalse(spread.spread_comparison_allowed)
            self.assertIsNone(spread.spread_ratio)


class SpreadMarcusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session, reset=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()

    def _trends(self, as_of: date) -> dict:
        return _by_metric(get_health_trends(self.session, self.user.id, as_of_date=as_of))

    def test_c4_hrv_spread_visible_without_calling_level_declining(self) -> None:
        trends = self._trends(C4)
        hrv = trends["hrv_sdnn_ms"]
        spread = hrv.within_window_spread
        assert spread is not None
        self.assertEqual(spread.observation_count, 7)
        self.assertEqual(spread.mean, _round2(mean(C4_CURRENT_HRV)))
        self.assertEqual(spread.sample_standard_deviation, _round2(stdev(C4_CURRENT_HRV)))
        self.assertEqual(spread.min, 24.7)
        self.assertEqual(spread.max, 48.9)
        self.assertEqual(spread.range, 24.2)
        self.assertEqual(spread.mean, hrv.current_value)
        self.assertEqual(hrv.direction, "improving")
        self.assertNotEqual(hrv.direction, "declining")
        self.assertNotEqual(hrv.direction, "decreasing")
        self.assertEqual(hrv.data_maturity_state, STATE_ESTABLISHED_TREND)
        self.assertTrue(hrv.baseline_ready)
        self.assertTrue(hrv.claim_eligibility.trend_allowed)
        self.assertTrue(spread.spread_observation_allowed)
        self.assertTrue(spread.spread_comparison_allowed)
        self.assertIsNotNone(spread.baseline_standard_deviation)
        self.assertGreater(spread.baseline_standard_deviation, MIN_USABLE_BASELINE_SPREAD)
        self.assertGreater(spread.spread_ratio, 2.0)
        self.assertAlmostEqual(
            spread.spread_ratio,
            stdev(C4_CURRENT_HRV) / spread.baseline_standard_deviation,
            delta=0.02,
        )
        self.assertFalse(hrv.salience.insight_candidate)
        self.assertFalse(hrv.salience.recommendation_candidate)
        self.assertNotIn("hrv_sdnn_ms", get_health_trends_for_agent(self.user.id, as_of_date=C4)["insight_salience"]["primary_metrics"])

    def test_c4_payload_exposes_spread_and_keeps_level_distinct(self) -> None:
        payload = get_health_trends_for_agent(self.user.id, as_of_date=C4)
        hrv = next(item for item in payload["trends"] if item["metric"] == "hrv_sdnn_ms")
        spread = hrv["within_window_spread"]
        self.assertEqual(spread["observation_count"], 7)
        self.assertEqual(hrv["direction"], "improving")
        self.assertGreater(spread["spread_ratio"], 2.0)
        self.assertTrue(spread["spread_comparison_allowed"])
        self.assertFalse(hrv["salience"]["insight_candidate"])
        self.assertNotIn("variability_band", spread)
        self.assertNotIn("coefficient_of_variation", spread)
        self.assertNotIn("score", spread)

    def test_b1_stable_period_does_not_become_insight_from_spread(self) -> None:
        payload = get_health_trends_for_agent(self.user.id, as_of_date=B1)
        hrv = next(item for item in payload["trends"] if item["metric"] == "hrv_sdnn_ms")
        spread = hrv["within_window_spread"]
        assert spread is not None
        self.assertTrue(spread["spread_observation_allowed"])
        self.assertLess(abs(spread["spread_ratio"] - 1.0), 1.0)
        self.assertFalse(hrv["salience"]["insight_candidate"])
        self.assertFalse(payload["insight_salience"]["insight_worthy"])
        self.assertNotIn("hrv_sdnn_ms", payload["insight_salience"]["primary_metrics"])

    def test_vo2_has_no_spread_object(self) -> None:
        vo2 = self._trends(C4)["vo2_max"]
        self.assertIsNone(vo2.within_window_spread)
        self.assertEqual(vo2.cadence, "episodic")

    def test_respiratory_rate_control_unaffected(self) -> None:
        trends = self._trends(C4)
        rr = trends["respiratory_rate"]
        self.assertIsNone(rr.within_window_spread)
        self.assertTrue(rr.control_metric)
        self.assertFalse(rr.salience.insight_candidate)
        self.assertNotIn("respiratory_rate", get_health_trends_for_agent(self.user.id, as_of_date=C4)["insight_salience"]["primary_metrics"])


class SpreadSyntheticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = open_test_session()
        self.user = create_user(self.session, display_name="F49 Spread Fixture")
        self.session.flush()

    def tearDown(self) -> None:
        self.session.close()

    def _hrv(self, as_of: date):
        return _by_metric(get_health_trends(self.session, self.user.id, as_of_date=as_of))["hrv_sdnn_ms"]

    def test_stable_mean_and_normal_spread(self) -> None:
        start = date(2026, 4, 1)
        pattern = (31.0, 32.0, 33.0)
        days = [_day(hrv=pattern[offset % 3]) for offset in range(40)]
        _write_days(self.session, self.user.id, start, days)
        as_of = start + timedelta(days=39)
        hrv = self._hrv(as_of)
        spread = hrv.within_window_spread
        assert spread is not None
        self.assertIn(hrv.direction, {"stable", "improving", "decreasing"})
        self.assertNotEqual(hrv.direction, "declining")
        self.assertTrue(spread.spread_comparison_allowed)
        self.assertLess(abs((spread.spread_ratio or 99) - 1.0), 0.35)
        self.assertFalse(hrv.salience.insight_candidate)
        self.assertFalse(hrv.salience.recommendation_candidate)

    def test_immature_baseline_forbids_comparison(self) -> None:
        start = date(2026, 5, 1)
        days = [_day(hrv=30.0 + (offset % 3)) for offset in range(8)]
        _write_days(self.session, self.user.id, start, days)
        as_of = start + timedelta(days=7)
        hrv = self._hrv(as_of)
        spread = hrv.within_window_spread
        assert spread is not None
        self.assertEqual(hrv.data_maturity_state, STATE_EARLY_PATTERN)
        self.assertFalse(hrv.baseline_ready)
        self.assertFalse(hrv.claim_eligibility.trend_allowed)
        self.assertTrue(spread.spread_observation_allowed)
        self.assertFalse(spread.spread_comparison_allowed)
        self.assertIsNone(spread.spread_ratio)
        self.assertEqual(hrv.direction, "unknown")

    def test_partial_coverage_forbids_comparison(self) -> None:
        start = date(2026, 4, 1)
        days = [_day(hrv=32.0 + ((offset % 3) - 1) * 0.4) for offset in range(40)]
        for offset in (37, 38, 39):
            days[offset]["hrv_sdnn_ms"] = None
        days[36]["hrv_sdnn_ms"] = 28.0
        days[35]["hrv_sdnn_ms"] = 36.0
        days[34]["hrv_sdnn_ms"] = 30.0
        days[33]["hrv_sdnn_ms"] = 34.0
        _write_days(self.session, self.user.id, start, days)
        as_of = start + timedelta(days=39)
        hrv = self._hrv(as_of)
        spread = hrv.within_window_spread
        assert spread is not None
        self.assertTrue(hrv.partial_coverage)
        self.assertEqual(spread.observation_count, 4)
        self.assertTrue(spread.spread_observation_allowed)
        self.assertFalse(spread.spread_comparison_allowed)
        self.assertIsNone(spread.spread_ratio)

    def test_near_zero_baseline_sd_forbids_comparison(self) -> None:
        start = date(2026, 4, 1)
        days = [_day(hrv=32.0) for _ in range(40)]
        current = [28.0, 36.0, 30.0, 34.0, 29.0, 35.0, 31.0]
        for offset, value in enumerate(current):
            days[33 + offset]["hrv_sdnn_ms"] = value
        _write_days(self.session, self.user.id, start, days)
        as_of = start + timedelta(days=39)
        hrv = self._hrv(as_of)
        spread = hrv.within_window_spread
        assert spread is not None
        self.assertEqual(spread.baseline_standard_deviation, 0.0)
        self.assertTrue(spread.spread_observation_allowed)
        self.assertFalse(spread.spread_comparison_allowed)
        self.assertIsNone(spread.spread_ratio)
        self.assertNotEqual(hrv.direction, "declining")

    def test_one_extreme_outlier_is_visible_in_min_max(self) -> None:
        start = date(2026, 4, 1)
        days = [_day(hrv=32.0 + ((offset % 3) - 1) * 0.3) for offset in range(40)]
        for offset in range(33, 39):
            days[offset]["hrv_sdnn_ms"] = 33.0
        days[39]["hrv_sdnn_ms"] = 55.0
        _write_days(self.session, self.user.id, start, days)
        as_of = start + timedelta(days=39)
        hrv = self._hrv(as_of)
        spread = hrv.within_window_spread
        assert spread is not None
        self.assertEqual(spread.min, 33.0)
        self.assertEqual(spread.max, 55.0)
        self.assertEqual(spread.range, 22.0)
        self.assertTrue(spread.spread_observation_allowed)
        self.assertNotEqual(hrv.direction, "declining")
        self.assertNotIn("variability_band", spread.to_dict())

    def test_same_mean_high_spread_does_not_mint_insight(self) -> None:
        start = date(2026, 4, 1)
        days = [_day(hrv=32.0 + ((offset % 3) - 1) * 0.4) for offset in range(33)]
        days.extend(
            [
                _day(hrv=24.0),
                _day(hrv=40.0),
                _day(hrv=25.0),
                _day(hrv=39.0),
                _day(hrv=24.5),
                _day(hrv=39.5),
                _day(hrv=32.0),
            ]
        )
        _write_days(self.session, self.user.id, start, days)
        as_of = start + timedelta(days=39)
        hrv = self._hrv(as_of)
        spread = hrv.within_window_spread
        assert spread is not None
        self.assertIn(hrv.direction, {"stable", "improving"})
        self.assertNotEqual(hrv.direction, "declining")
        self.assertTrue(spread.spread_comparison_allowed)
        self.assertGreater(spread.spread_ratio, 2.0)
        self.assertFalse(hrv.salience.insight_candidate)
        self.assertFalse(hrv.salience.recommendation_candidate)
        payload = get_health_trends_for_agent(self.user.id, as_of_date=as_of)
        self.assertNotIn("hrv_sdnn_ms", payload["insight_salience"]["primary_metrics"])


class SpreadTraceAndPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session, reset=True)
        cls.payload = get_health_trends_for_agent(cls.user.id, as_of_date=C4)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()

    def test_trace_exposes_spread_with_deterministic_origin(self) -> None:
        request = _sample_request()
        request.contents[2].parts[0].function_response.response = self.payload
        captured = observe_llm_request(request, call_index=0)
        extracted = extract_within_window_spread(self.payload)
        assert extracted is not None
        assert captured.within_window_spread_visible is not None
        self.assertEqual(extracted["origin"], ORIGIN_SPREAD_ANALYTICS)
        self.assertEqual(ORIGIN_SPREAD_ANALYTICS, "deterministic_spread_analytics")
        self.assertEqual(captured.within_window_spread_visible["origin"], ORIGIN_SPREAD_ANALYTICS)
        hrv = next(item for item in extracted["metrics"] if item["metric"] == "hrv_sdnn_ms")
        self.assertEqual(hrv["observation_count"], 7)
        self.assertEqual(hrv["mean"], _round2(mean(C4_CURRENT_HRV)))
        self.assertEqual(hrv["sample_standard_deviation"], _round2(stdev(C4_CURRENT_HRV)))
        self.assertIsNotNone(hrv["baseline_standard_deviation"])
        self.assertIsNotNone(hrv["spread_ratio"])
        self.assertTrue(hrv["spread_observation_allowed"])
        self.assertTrue(hrv["spread_comparison_allowed"])
        self.assertEqual(hrv["direction"], "improving")
        self.assertEqual(hrv["data_maturity_state"], STATE_ESTABLISHED_TREND)
        self.assertTrue(hrv["trend_allowed"])
        provenance = next(item for item in captured.provenance if item.component == "within_window_spread")
        self.assertTrue(provenance.present)
        self.assertEqual(provenance.origin, ORIGIN_SPREAD_ANALYTICS)
        serialized = json.dumps(captured.to_dict())
        self.assertIn("within_window_spread", serialized)
        self.assertIn("deterministic_spread_analytics", serialized)
        self.assertNotIn("hidden chain of thought", serialized)

    def test_trace_omits_non_hrv_spread(self) -> None:
        extracted = extract_within_window_spread(self.payload)
        assert extracted is not None
        metrics = {item["metric"] for item in extracted["metrics"]}
        self.assertEqual(metrics, {"hrv_sdnn_ms"})

    def test_prompt_honor_is_descriptive_only(self) -> None:
        self.assertIn("within_window_spread is descriptive context", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("higher spread is not a decline", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("Do not infer stress, poor recovery", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("cardiovascular instability from spread alone", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("within_window_spread is day-to-day spread of readings", self.payload["disclaimer"])
        self.assertIn("not a decline", self.payload["disclaimer"])
        self.assertNotIn("variability band", HEALTH_COACH_INSTRUCTIONS)
        self.assertNotIn("0–100", HEALTH_COACH_INSTRUCTIONS)
        self.assertNotIn("0-100", HEALTH_COACH_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
