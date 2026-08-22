"""Offline tests for F4.6 product salience / insight-worthiness."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from agent.model_observe import extract_insight_salience, observe_llm_request
from agent.tools import build_tools, RunContext
from analytics.maturity import STATE_EARLY_PATTERN, STATE_ESTABLISHED_TREND
from analytics.trends import get_health_trends
from app.health_tools import get_health_trends_for_agent
from app.lifestyle_tools import get_lifestyle_context_for_agent
from data.demo_seed import checkpoint_date, seed_demo_health_data
from data.models import HealthDaily
from data.repository import create_user, upsert_health_daily
from evals.trace_schema import ORIGIN_SALIENCE_ANALYTICS
from tests.test_helpers import open_test_session
from tests.test_model_observe import _sample_request

B1 = date(2026, 6, 18)
A1 = date(2026, 8, 2)
B3 = date(2026, 8, 17)
C3 = date(2026, 6, 29)


class _SyntheticSeries:
    def __init__(self, session) -> None:
        self.session = session
        self.user = create_user(session, display_name="Salience Fixture")
        session.flush()

    def write(self, start: date, days: list[dict]) -> None:
        for offset, fields in enumerate(days):
            upsert_health_daily(
                self.session,
                HealthDaily(user_id=self.user.id, date=start + timedelta(days=offset), **fields),
            )
        self.session.commit()


def _day(
    *,
    sleep: float | None = 7.0,
    rhr: float | None = 70.0,
    hrv: float | None = 32.0,
    exercise: float | None = 12.0,
    workouts: int | None = 0,
    steps: int | None = 8000,
    vo2: float | None = 40.0,
) -> dict:
    return {
        "sleep_duration_hours": sleep,
        "resting_hr_bpm": rhr,
        "hrv_sdnn_ms": hrv,
        "exercise_minutes": exercise,
        "workout_count": workouts,
        "steps": steps,
        "vo2_max": vo2,
    }


def _by_metric(trends) -> dict:
    return {item.metric: item for item in trends}


class SalienceMarcusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session, reset=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()

    def _payload(self, as_of: date) -> dict:
        return get_health_trends_for_agent(self.user.id, as_of_date=as_of)

    def test_b1_detectable_but_not_insight_worthy(self) -> None:
        payload = self._payload(B1)
        trends = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=B1))
        steps = trends["steps"]
        exercise = trends["exercise_minutes"]
        self.assertEqual(steps.direction, "improving")
        self.assertEqual(exercise.direction, "improving")
        self.assertGreater(abs(steps.percent_change or 0), 3)
        self.assertEqual(steps.salience.magnitude_band, "barely_directional")
        self.assertEqual(exercise.salience.magnitude_band, "barely_directional")
        self.assertEqual(steps.salience.salience_level, "low")
        self.assertFalse(steps.salience.insight_candidate)
        self.assertFalse(exercise.salience.insight_candidate)
        self.assertIn("same_family_weak_corroboration", steps.salience.reasons)
        self.assertIn("same_family_weak_corroboration", exercise.salience.reasons)
        self.assertEqual(steps.salience.corroborating_metrics, ())
        salience = payload["insight_salience"]
        self.assertFalse(salience["insight_worthy"])
        self.assertFalse(salience["recommendation_worthy"])
        self.assertEqual(salience["salience_level"], "low")
        self.assertEqual(payload["trends"][0]["direction"], trends[payload["trends"][0]["metric"]].direction)

    def test_a1_sleep_decline_is_insight_worthy(self) -> None:
        trends = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=A1))
        sleep = trends["sleep_duration_hours"]
        payload = self._payload(A1)
        self.assertEqual(sleep.direction, "decreasing")
        self.assertIn(sleep.salience.magnitude_band, {"clear", "strong"})
        self.assertTrue(sleep.salience.insight_candidate)
        self.assertTrue(payload["insight_salience"]["insight_worthy"])
        self.assertIn("sleep_duration_hours", payload["insight_salience"]["primary_metrics"])
        self.assertTrue(sleep.claim_eligibility.trend_allowed)

    def test_b3_maintenance_of_gain_remains_insight_eligible(self) -> None:
        trends = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=B3))
        payload = self._payload(B3)
        rhr = trends["resting_hr_bpm"]
        self.assertEqual(rhr.direction, "stable")
        self.assertTrue(rhr.longitudinal.maintenance_of_gain)
        self.assertTrue(rhr.salience.insight_candidate)
        self.assertIn("maintenance_of_gain", rhr.salience.reasons)
        self.assertTrue(payload["insight_salience"]["insight_worthy"])
        self.assertIn("resting_hr_bpm", payload["insight_salience"]["primary_metrics"])
        self.assertFalse(rhr.salience.recommendation_candidate)

    def test_c3_lifestyle_does_not_manufacture_sleep_salience(self) -> None:
        trends = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=C3))
        sleep = trends["sleep_duration_hours"]
        self.assertEqual(sleep.direction, "stable")
        self.assertFalse(sleep.salience.insight_candidate)
        self.assertEqual(sleep.salience.magnitude_band, "none")
        lifestyle = get_lifestyle_context_for_agent(self.user.id, as_of_date=C3)
        self.assertGreater(lifestyle["event_count"], 0)
        self.assertIn("caffeine_mg", lifestyle["policy_available_inputs"])
        self.assertNotIn("lifestyle_context_present_not_causal", sleep.salience.reasons)

    def test_b1_decision_log_distinguishes_detectable_from_insight_worthy(self) -> None:
        context = RunContext(scenario_id="HC-EVAL-B1", user_id=self.user.id, as_of_date=B1)
        get_trend_signals, _, _ = build_tools(context)
        get_trend_signals()
        labels = [item.get("label") or "" for item in context.activity_log if item.get("phase") == "DECISION"]
        joined = " ".join(labels)
        self.assertIn("not insight-worthy", joined)
        self.assertNotIn("Insight-worthy signal", joined)


class SalienceSyntheticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = open_test_session()
        self.series = _SyntheticSeries(self.session)

    def tearDown(self) -> None:
        self.session.close()

    def _trend(self, as_of: date, metric: str):
        trends = get_health_trends(self.session, self.series.user.id, as_of_date=as_of)
        return next(item for item in trends if item.metric == metric)

    def test_early_pattern_strong_observation_is_not_suppressed(self) -> None:
        start = date(2026, 6, 1)
        days = [_day(sleep=7.5, hrv=32.0) for _ in range(5)]
        days.extend(_day(sleep=5.4, hrv=24.0) for _ in range(7))
        self.series.write(start, days)
        as_of = start + timedelta(days=11)
        sleep = self._trend(as_of, "sleep_duration_hours")
        self.assertFalse(sleep.baseline_ready)
        self.assertFalse(sleep.claim_eligibility.trend_allowed)
        self.assertTrue(sleep.claim_eligibility.early_pattern_allowed)
        self.assertEqual(sleep.data_maturity_state, STATE_EARLY_PATTERN)
        self.assertEqual(sleep.direction, "unknown")
        self.assertIn(sleep.salience.magnitude_band, {"clear", "strong"})
        self.assertTrue(sleep.salience.insight_candidate)
        self.assertIn("early_pattern_observation", sleep.salience.reasons)
        self.assertFalse(sleep.salience.recommendation_candidate)
        summary = get_health_trends_for_agent(self.series.user.id, as_of_date=as_of)["insight_salience"]
        self.assertTrue(summary["insight_worthy"])
        self.assertFalse(summary["recommendation_worthy"])

    def test_partial_coverage_caps_but_does_not_create_salience(self) -> None:
        start = date(2026, 1, 1)
        days = [_day(sleep=7.0) for _ in range(83)]
        for _ in range(4):
            days.append(_day(sleep=None, rhr=None, hrv=None, exercise=None, workouts=None, steps=None, vo2=None))
        days.extend(_day(sleep=5.0) for _ in range(3))
        self.series.write(start, days)
        as_of = start + timedelta(days=89)
        sleep = self._trend(as_of, "sleep_duration_hours")
        self.assertTrue(sleep.partial_coverage)
        self.assertTrue(sleep.claim_eligibility.trend_allowed)
        self.assertTrue(sleep.salience.insight_candidate)
        self.assertEqual(sleep.salience.salience_level, "moderate")
        self.assertIn("coverage_caveat", sleep.salience.reasons)
        self.assertNotEqual(sleep.data_maturity_state, STATE_EARLY_PATTERN)
        self.assertEqual(sleep.data_maturity_state, STATE_ESTABLISHED_TREND)

        flat_start = date(2026, 3, 1)
        other = _SyntheticSeries(self.session)
        other.write(flat_start, [_day(sleep=7.0) for _ in range(20)])
        as_of_gap = flat_start + timedelta(days=19)
        # Punch holes in the current window without a real change.
        trends = get_health_trends(self.session, other.user.id, as_of_date=as_of_gap)
        payload = get_health_trends_for_agent(other.user.id, as_of_date=as_of_gap)
        sleep_flat = next(item for item in trends if item.metric == "sleep_duration_hours")
        self.assertFalse(sleep_flat.salience.insight_candidate)
        self.assertFalse(payload["insight_salience"]["insight_worthy"])

    def test_flat_series_is_not_insight_worthy(self) -> None:
        start = date(2026, 1, 1)
        self.series.write(start, [_day() for _ in range(90)])
        as_of = start + timedelta(days=89)
        payload = get_health_trends_for_agent(self.series.user.id, as_of_date=as_of)
        self.assertFalse(payload["insight_salience"]["insight_worthy"])
        self.assertEqual(payload["insight_salience"]["salience_level"], "none")
        for item in payload["trends"]:
            self.assertIn(item["direction"], {"stable", "unknown"})
            self.assertFalse(item["salience"]["insight_candidate"])


class SalienceTraceTests(unittest.TestCase):
    def test_trace_exposes_salience_origin(self) -> None:
        request = _sample_request()
        payload = request.contents[2].parts[0].function_response.response
        payload["insight_salience"] = {
            "insight_worthy": False,
            "recommendation_worthy": False,
            "primary_metrics": [],
            "reasons": ["same_family_weak_corroboration"],
            "salience_level": "low",
        }
        payload["trends"][0]["salience"] = {
            "salience_level": "low",
            "magnitude_band": "barely_directional",
            "insight_candidate": False,
            "recommendation_candidate": False,
            "corroborating_metrics": [],
            "reasons": ["detectable_but_small_absolute"],
        }
        captured = observe_llm_request(request, call_index=0)
        assert captured.insight_salience_visible is not None
        self.assertEqual(captured.insight_salience_visible["origin"], ORIGIN_SALIENCE_ANALYTICS)
        self.assertEqual(ORIGIN_SALIENCE_ANALYTICS, "deterministic_salience_analytics")
        self.assertFalse(captured.insight_salience_visible["summary"]["insight_worthy"])
        provenance = next(item for item in captured.provenance if item.component == "insight_salience")
        self.assertTrue(provenance.present)
        extracted = extract_insight_salience(payload)
        assert extracted is not None
        self.assertEqual(extracted["metrics"][0]["reasons"], ["detectable_but_small_absolute"])


if __name__ == "__main__":
    unittest.main()
