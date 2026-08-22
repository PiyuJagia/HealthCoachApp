"""Offline tests for F4.8 respiratory-rate control-metric exposure."""

from __future__ import annotations

import json
import unittest
from datetime import date, timedelta

from agent.instructions import HEALTH_COACH_INSTRUCTIONS
from agent.model_observe import extract_insight_salience, extract_trend_maturity, observe_llm_request
from analytics.maturity import CADENCE_DAILY, METRIC_SPECS, STATE_EARLY_PATTERN, STATE_ESTABLISHED_TREND
from analytics.salience import CONTROL_METRICS, REASON_STABLE_CONTROL
from analytics.trends import get_health_trends, get_weekly_summaries
from app.health_tools import get_health_trends_for_agent
from data.demo_seed import seed_demo_health_data
from data.models import HealthDaily
from data.repository import create_user, upsert_health_daily
from evals.trace_schema import ORIGIN_DETERMINISTIC_ANALYTICS, ORIGIN_SALIENCE_ANALYTICS
from tests.test_helpers import open_test_session
from tests.test_model_observe import _sample_request

E1 = date(2026, 8, 2)
B1 = date(2026, 6, 18)
B3 = date(2026, 8, 17)
A1 = date(2026, 8, 2)
C3 = date(2026, 6, 29)
D2 = date(2026, 6, 10)


def _by_metric(trends) -> dict:
    return {item.metric: item for item in trends}


def _write_days(session, user_id: int, start: date, days: list[dict]) -> None:
    for offset, fields in enumerate(days):
        upsert_health_daily(
            session,
            HealthDaily(user_id=user_id, date=start + timedelta(days=offset), **fields),
        )
    session.commit()


def _rr_day(*, sleep: float | None = 7.0, rr: float | None = 14.5, hrv: float | None = 32.0) -> dict:
    return {
        "sleep_duration_hours": sleep,
        "resting_hr_bpm": 70.0,
        "hrv_sdnn_ms": hrv,
        "exercise_minutes": 12.0,
        "workout_count": 0,
        "steps": 8000,
        "vo2_max": 40.0,
        "respiratory_rate": rr,
    }


class RespiratorySpecTests(unittest.TestCase):
    def test_respiratory_rate_is_daily_control_spec(self) -> None:
        spec = next(item for item in METRIC_SPECS if item.metric == "respiratory_rate")
        self.assertEqual(spec.cadence, CADENCE_DAILY)
        self.assertTrue(spec.control_metric)
        self.assertIn("respiratory_rate", CONTROL_METRICS)


class RespiratoryMarcusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session, reset=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()

    def _payload(self, as_of: date) -> dict:
        return get_health_trends_for_agent(self.user.id, as_of_date=as_of)

    def test_included_in_get_trend_signals(self) -> None:
        payload = self._payload(E1)
        metrics = {item["metric"] for item in payload["trends"]}
        self.assertIn("respiratory_rate", metrics)
        self.assertIn("respiratory_rate", payload["insight_salience"]["control_metrics"])

    def test_daily_cadence_and_maturity_fields(self) -> None:
        rr = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=E1))["respiratory_rate"]
        self.assertEqual(rr.cadence, CADENCE_DAILY)
        self.assertTrue(rr.control_metric)
        self.assertEqual(rr.expected_observation_count_current, 7)
        self.assertEqual(rr.data_maturity_state, STATE_ESTABLISHED_TREND)
        self.assertTrue(rr.claim_eligibility.trend_allowed)
        self.assertTrue(rr.baseline_ready)
        self.assertGreaterEqual(rr.baseline_observation_count, 10)
        self.assertIsNotNone(rr.latest_valid_observation_date)
        self.assertIsNotNone(rr.latest_valid_observation_value)
        self.assertIsNotNone(rr.coverage_ratio)

    def test_e1_as_of_available(self) -> None:
        rr = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=E1))["respiratory_rate"]
        self.assertTrue(rr.as_of_date_available)
        self.assertIsNotNone(rr.as_of_date_value)

    def test_e1_control_role_bounds_sleep_without_reassurance_insight(self) -> None:
        trends = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=E1))
        payload = self._payload(E1)
        sleep = trends["sleep_duration_hours"]
        rr = trends["respiratory_rate"]
        self.assertEqual(sleep.direction, "decreasing")
        self.assertTrue(sleep.salience.insight_candidate)
        self.assertLess(sleep.percent_change or 0, -10)
        self.assertTrue(rr.claim_eligibility.trend_allowed)
        self.assertEqual(rr.direction, "stable")
        self.assertLess(abs(rr.percent_change or 99), 3.0)
        self.assertTrue(rr.control_metric)
        self.assertTrue(rr.salience.control_metric)
        self.assertFalse(rr.salience.insight_candidate)
        self.assertFalse(rr.salience.recommendation_candidate)
        self.assertEqual(rr.salience.salience_level, "none")
        self.assertIn(REASON_STABLE_CONTROL, rr.salience.reasons)
        self.assertNotIn("respiratory_rate", payload["insight_salience"]["primary_metrics"])
        self.assertIn("sleep_duration_hours", payload["insight_salience"]["primary_metrics"])
        self.assertTrue(payload["insight_salience"]["insight_worthy"])
        self.assertFalse(rr.longitudinal.maintenance_of_gain)
        self.assertFalse(rr.longitudinal.maintenance_of_decline)

    def test_b1_stable_respiratory_does_not_create_insight(self) -> None:
        trends = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=B1))
        payload = self._payload(B1)
        rr = trends["respiratory_rate"]
        self.assertEqual(rr.direction, "stable")
        self.assertFalse(rr.salience.insight_candidate)
        self.assertNotIn("respiratory_rate", payload["insight_salience"]["primary_metrics"])
        self.assertFalse(payload["insight_salience"]["insight_worthy"])

    def test_d2_missingness_preserved_no_imputation(self) -> None:
        rr = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=D2))["respiratory_rate"]
        self.assertFalse(rr.as_of_date_available)
        self.assertIsNone(rr.as_of_date_value)
        self.assertTrue(rr.gap_caveat_required)
        self.assertLess(rr.observation_count_current, rr.expected_observation_count_current)
        self.assertTrue(rr.partial_coverage)
        self.assertIsNotNone(rr.latest_valid_observation_date)
        self.assertNotEqual(rr.latest_valid_observation_date, D2)

    def test_weekly_summary_includes_respiratory_without_authorizing_trend(self) -> None:
        week = get_weekly_summaries(self.session, self.user.id, as_of_date=E1, weeks=1)[0]
        coverage = week.coverage["respiratory_rate"]
        self.assertEqual(week.average_respiratory_rate, coverage.aggregate_value)
        self.assertEqual(coverage.cadence, CADENCE_DAILY)
        self.assertEqual(coverage.expected_observation_count, 7)
        self.assertTrue(coverage.claim_semantics.summary_value_allowed)
        trends = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=E1))
        rr = trends["respiratory_rate"]
        self.assertEqual(
            coverage.claim_semantics.summary_comparison_allowed,
            rr.claim_eligibility.trend_allowed,
        )
        self.assertEqual(
            coverage.claim_semantics.summary_recommendation_support_allowed,
            rr.claim_eligibility.recommendation_support_allowed,
        )

    def test_f41_f43_f46_regression_anchors(self) -> None:
        a1 = self._payload(A1)
        b1 = self._payload(B1)
        b3 = self._payload(B3)
        c3_trends = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=C3))
        self.assertTrue(a1["insight_salience"]["insight_worthy"])
        self.assertIn("sleep_duration_hours", a1["insight_salience"]["primary_metrics"])
        self.assertFalse(b1["insight_salience"]["insight_worthy"])
        self.assertTrue(b3["insight_salience"]["insight_worthy"])
        self.assertIn("resting_hr_bpm", b3["insight_salience"]["primary_metrics"])
        self.assertFalse(c3_trends["sleep_duration_hours"].salience.insight_candidate)
        e1_week = get_weekly_summaries(self.session, self.user.id, as_of_date=E1, weeks=1)[0]
        sleep_week = e1_week.coverage["sleep_duration_hours"]
        sleep_trend = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=E1))[
            "sleep_duration_hours"
        ]
        self.assertEqual(
            sleep_week.claim_semantics.summary_comparison_allowed,
            sleep_trend.claim_eligibility.trend_allowed,
        )


class RespiratorySyntheticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = open_test_session()
        self.user = create_user(self.session, display_name="RR Fixture")
        self.session.flush()

    def tearDown(self) -> None:
        self.session.close()

    def test_partial_coverage_preserves_missing_days(self) -> None:
        start = date(2026, 4, 1)
        days = []
        for offset in range(40):
            days.append(_rr_day(rr=None if offset >= 37 else 14.5))
        _write_days(self.session, self.user.id, start, days)
        as_of = start + timedelta(days=39)
        rr = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=as_of))["respiratory_rate"]
        week = get_weekly_summaries(self.session, self.user.id, as_of_date=as_of, weeks=1)[0]
        coverage = week.coverage["respiratory_rate"]
        self.assertEqual(rr.observation_count_current, 4)
        self.assertEqual(rr.expected_observation_count_current, 7)
        self.assertTrue(rr.partial_coverage)
        self.assertTrue(rr.gap_caveat_required)
        self.assertFalse(rr.as_of_date_available)
        self.assertIsNone(rr.as_of_date_value)
        self.assertEqual(coverage.observation_count, 4)
        self.assertEqual(coverage.missing_count, 3)
        self.assertTrue(coverage.partial_coverage)
        self.assertTrue(coverage.claim_semantics.summary_value_allowed)
        self.assertFalse(rr.salience.insight_candidate)

    def test_immature_baseline_is_not_an_established_trend(self) -> None:
        start = date(2026, 5, 1)
        _write_days(self.session, self.user.id, start, [_rr_day(rr=14.6) for _ in range(8)])
        as_of = start + timedelta(days=7)
        rr = _by_metric(get_health_trends(self.session, self.user.id, as_of_date=as_of))["respiratory_rate"]
        week = get_weekly_summaries(self.session, self.user.id, as_of_date=as_of, weeks=1)[0]
        coverage = week.coverage["respiratory_rate"]
        self.assertIn(rr.data_maturity_state, {STATE_EARLY_PATTERN, "SNAPSHOT"})
        self.assertFalse(rr.claim_eligibility.trend_allowed)
        self.assertFalse(rr.baseline_ready)
        self.assertEqual(rr.direction, "unknown")
        self.assertIsNone(rr.percent_change)
        self.assertFalse(coverage.claim_semantics.summary_comparison_allowed)
        self.assertFalse(coverage.claim_semantics.summary_recommendation_support_allowed)
        self.assertTrue(coverage.claim_semantics.summary_value_allowed)
        self.assertFalse(rr.salience.insight_candidate)
        self.assertTrue(rr.salience.control_metric)

    def test_stable_respiratory_alone_is_not_insight_worthy(self) -> None:
        start = date(2026, 1, 1)
        _write_days(self.session, self.user.id, start, [_rr_day(rr=14.5) for _ in range(40)])
        as_of = start + timedelta(days=39)
        payload = get_health_trends_for_agent(self.user.id, as_of_date=as_of)
        rr = next(item for item in payload["trends"] if item["metric"] == "respiratory_rate")
        self.assertEqual(rr["direction"], "stable")
        self.assertTrue(rr["control_metric"])
        self.assertFalse(rr["salience"]["insight_candidate"])
        self.assertFalse(payload["insight_salience"]["insight_worthy"])
        self.assertEqual(payload["insight_salience"]["salience_level"], "none")
        self.assertNotIn("respiratory_rate", payload["insight_salience"]["primary_metrics"])


class RespiratoryTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session, reset=True)
        cls.payload = get_health_trends_for_agent(cls.user.id, as_of_date=E1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()

    def test_trace_exposes_respiratory_control_with_provenance(self) -> None:
        request = _sample_request()
        request.contents[2].parts[0].function_response.response = self.payload
        captured = observe_llm_request(request, call_index=0)
        maturity = extract_trend_maturity(self.payload)
        salience = extract_insight_salience(self.payload)
        assert maturity is not None
        assert salience is not None
        self.assertEqual(maturity["origin"], ORIGIN_DETERMINISTIC_ANALYTICS)
        self.assertEqual(ORIGIN_DETERMINISTIC_ANALYTICS, "deterministic_analytics")
        rr_maturity = next(item for item in maturity["metrics"] if item["metric"] == "respiratory_rate")
        rr_salience = next(item for item in salience["metrics"] if item["metric"] == "respiratory_rate")
        self.assertTrue(rr_maturity["control_metric"])
        self.assertEqual(rr_maturity["cadence"], CADENCE_DAILY)
        self.assertEqual(rr_maturity["direction"], "stable")
        self.assertEqual(rr_maturity["data_maturity_state"], STATE_ESTABLISHED_TREND)
        self.assertIsNotNone(rr_maturity["coverage_ratio"])
        self.assertTrue(rr_salience["control_metric"])
        self.assertFalse(rr_salience["insight_candidate"])
        self.assertIn("respiratory_rate", salience["summary"]["control_metrics"])
        self.assertTrue(captured.trend_maturity_visible is not None)
        serialized = json.dumps(captured.to_dict())
        self.assertIn("respiratory_rate", serialized)
        self.assertIn("control_metric", serialized)
        self.assertNotIn("hidden chain of thought", serialized)

    def test_prompt_honors_control_metric_bounding_role(self) -> None:
        self.assertIn("control_metric=true", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("bounding", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("cardiorespiratory wellness", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("control_metric=true", self.payload["disclaimer"])


if __name__ == "__main__":
    unittest.main()
