"""Offline tests for F4.5 longitudinal maintenance context."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from agent.model_observe import extract_longitudinal_context, observe_llm_request
from analytics.longitudinal import REASON_NO_OLDER_HISTORY
from analytics.trends import get_health_trends, get_weekly_summaries
from app.health_tools import get_health_trends_for_agent
from data.demo_seed import checkpoint_date, seed_demo_health_data
from data.models import HealthDaily
from data.repository import create_user, upsert_health_daily
from evals.longitudinal_inspection import inspect_b3_b1
from evals.trace_schema import ORIGIN_LONGITUDINAL_ANALYTICS
from tests.test_helpers import open_test_session
from tests.test_model_observe import _sample_request


class _SyntheticSeries:
    def __init__(self, session) -> None:
        self.session = session
        self.user = create_user(session, display_name="Longitudinal Fixture")
        session.flush()

    def write(self, start: date, days: list[dict]) -> None:
        for offset, fields in enumerate(days):
            upsert_health_daily(
                self.session,
                HealthDaily(user_id=self.user.id, date=start + timedelta(days=offset), **fields),
            )
        self.session.commit()


def _flat_day(*, rhr: float, exercise: float, hrv: float = 30.0) -> dict:
    return {
        "resting_hr_bpm": rhr,
        "exercise_minutes": exercise,
        "workout_count": 1 if exercise >= 20 else 0,
        "hrv_sdnn_ms": hrv,
        "sleep_duration_hours": 7.0,
        "steps": 8000,
        "vo2_max": 40.0,
    }


class LongitudinalMarcusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session, reset=True)
        cls.report = inspect_b3_b1(cls.session, cls.user.id)
        cls.b3 = next(item for item in cls.report["scenarios"] if item["scenario_id"] == "HC-EVAL-B3")
        cls.b1 = next(item for item in cls.report["scenarios"] if item["scenario_id"] == "HC-EVAL-B1")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()

    def _b3_metric(self, metric: str) -> dict:
        return next(row for row in self.b3["metrics"] if row["metric"] == metric)

    def test_b3_maintenance_of_gain_on_cardio_metrics(self) -> None:
        supporting = set(self.b3["metrics_maintaining_gains"])
        self.assertIn("resting_hr_bpm", supporting)
        self.assertIn("hrv_sdnn_ms", supporting)
        self.assertIn("vo2_max", supporting)
        rhr = self._b3_metric("resting_hr_bpm")
        self.assertEqual(rhr["recent_direction"], "stable")
        self.assertTrue(rhr["longitudinal"]["longitudinal_context_available"])
        self.assertLess(rhr["current_value"], rhr["longitudinal"]["long_term_reference_value"])

    def test_b3_recent_stable_does_not_erase_older_improvement(self) -> None:
        self.assertTrue(self.report["answers"]["b3_still_better_than_older_baseline"])
        self.assertTrue(self.report["answers"]["b3_can_distinguish_holding_gains"])

    def test_b1_is_negative_control(self) -> None:
        self.assertEqual(self.b1["metrics_maintaining_gains"], [])
        for row in self.b1["metrics"]:
            self.assertFalse(row["longitudinal"]["maintenance_of_gain"])
            self.assertFalse(row["longitudinal"]["longitudinal_context_available"])
            self.assertEqual(row["longitudinal"]["reason"], REASON_NO_OLDER_HISTORY)

    def test_weekly_summaries_cannot_create_maintenance_claim(self) -> None:
        self.assertTrue(self.report["answers"]["weekly_cannot_independently_claim_maintenance"])
        weeks = get_weekly_summaries(
            self.session, self.user.id, as_of_date=date(2026, 8, 17), weeks=1
        )
        payload = weeks[0].to_dict()
        self.assertNotIn("maintenance_of_gain", payload)
        for coverage in payload["coverage"].values():
            self.assertNotIn("maintenance_of_gain", coverage)
            self.assertIn("claim_semantics", coverage)


class LongitudinalSyntheticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = open_test_session()
        self.series = _SyntheticSeries(self.session)

    def tearDown(self) -> None:
        self.session.close()

    def _trend(self, as_of: date, metric: str):
        trends = get_health_trends(self.session, self.series.user.id, as_of_date=as_of)
        return next(item for item in trends if item.metric == metric)

    def test_prior_improvement_plus_recent_stability_is_maintenance(self) -> None:
        start = date(2026, 1, 1)
        days = [_flat_day(rhr=72.0, exercise=10.0, hrv=30.0) for _ in range(30)]
        days.extend(_flat_day(rhr=68.0, exercise=25.0, hrv=36.0) for _ in range(60))
        self.series.write(start, days)
        as_of = start + timedelta(days=89)
        rhr = self._trend(as_of, "resting_hr_bpm")
        self.assertEqual(rhr.direction, "stable")
        self.assertTrue(rhr.longitudinal.maintenance_of_gain)
        self.assertFalse(rhr.longitudinal.maintenance_of_decline)

    def test_stable_baseline_without_prior_improvement_is_false(self) -> None:
        start = date(2026, 1, 1)
        self.series.write(start, [_flat_day(rhr=72.0, exercise=12.0) for _ in range(90)])
        as_of = start + timedelta(days=89)
        rhr = self._trend(as_of, "resting_hr_bpm")
        self.assertEqual(rhr.direction, "stable")
        self.assertTrue(rhr.longitudinal.longitudinal_context_available)
        self.assertFalse(rhr.longitudinal.maintenance_of_gain)

    def test_improvement_then_reversal_is_not_maintenance(self) -> None:
        start = date(2026, 1, 1)
        days = [_flat_day(rhr=72.0, exercise=10.0) for _ in range(30)]
        days.extend(_flat_day(rhr=68.0, exercise=25.0) for _ in range(45))
        days.extend(_flat_day(rhr=76.0, exercise=8.0) for _ in range(15))
        self.series.write(start, days)
        as_of = start + timedelta(days=89)
        rhr = self._trend(as_of, "resting_hr_bpm")
        self.assertFalse(rhr.longitudinal.maintenance_of_gain)

    def test_insufficient_history_is_unavailable(self) -> None:
        start = date(2026, 6, 1)
        self.series.write(start, [_flat_day(rhr=70.0, exercise=12.0) for _ in range(15)])
        as_of = start + timedelta(days=14)
        rhr = self._trend(as_of, "resting_hr_bpm")
        self.assertFalse(rhr.longitudinal.longitudinal_context_available)
        self.assertFalse(rhr.longitudinal.maintenance_of_gain)

    def test_missing_recent_days_do_not_erase_historical_comparison(self) -> None:
        start = date(2026, 1, 1)
        days = [_flat_day(rhr=72.0, exercise=10.0, hrv=30.0) for _ in range(30)]
        days.extend(_flat_day(rhr=68.0, exercise=25.0, hrv=36.0) for _ in range(58))
        days.append(
            {
                "resting_hr_bpm": None,
                "exercise_minutes": None,
                "workout_count": None,
                "hrv_sdnn_ms": None,
                "sleep_duration_hours": None,
                "steps": None,
                "vo2_max": None,
            }
        )
        days.append(
            {
                "resting_hr_bpm": None,
                "exercise_minutes": None,
                "workout_count": None,
                "hrv_sdnn_ms": None,
                "sleep_duration_hours": None,
                "steps": None,
                "vo2_max": None,
            }
        )
        self.series.write(start, days)
        as_of = start + timedelta(days=89)
        rhr = self._trend(as_of, "resting_hr_bpm")
        self.assertFalse(rhr.as_of_date_available)
        self.assertTrue(rhr.gap_caveat_required)
        self.assertTrue(rhr.claim_eligibility.trend_allowed)
        self.assertTrue(rhr.longitudinal.longitudinal_context_available)
        self.assertTrue(rhr.longitudinal.maintenance_of_gain)

    def test_maturity_rules_still_apply(self) -> None:
        start = date(2026, 1, 1)
        days = [_flat_day(rhr=72.0, exercise=10.0) for _ in range(30)]
        days.extend(_flat_day(rhr=68.0, exercise=25.0) for _ in range(60))
        self.series.write(start, days)
        as_of = start + timedelta(days=89)
        rhr = self._trend(as_of, "resting_hr_bpm")
        self.assertTrue(rhr.claim_eligibility.trend_allowed)
        self.assertEqual(rhr.claim_eligibility.recommendation_basis, "established_trend")


class LongitudinalTraceTests(unittest.TestCase):
    def test_trace_exposes_longitudinal_origin(self) -> None:
        request = _sample_request()
        payload = request.contents[2].parts[0].function_response.response
        payload["longitudinal_summary"] = {
            "any_maintenance_of_gain": True,
            "metrics_maintaining_gains": ["resting_hr_bpm"],
        }
        payload["trends"][0]["longitudinal"] = {
            "longitudinal_context_available": True,
            "recent_state": 68.0,
            "long_term_reference_value": 72.0,
            "prior_significant_change_direction": "improving",
            "prior_significant_change_percent": -4.0,
            "current_vs_long_term_percent": -5.5,
            "maintenance_of_gain": True,
            "maintenance_of_decline": False,
            "reason": "older_reference_outside_recent_baseline",
        }
        captured = observe_llm_request(request, call_index=0)
        assert captured.longitudinal_context_visible is not None
        self.assertEqual(captured.longitudinal_context_visible["origin"], ORIGIN_LONGITUDINAL_ANALYTICS)
        self.assertEqual(ORIGIN_LONGITUDINAL_ANALYTICS, "deterministic_longitudinal_analytics")
        self.assertTrue(captured.longitudinal_context_visible["metrics"][0]["maintenance_of_gain"])
        provenance = next(item for item in captured.provenance if item.component == "longitudinal_context")
        self.assertTrue(provenance.present)
        extracted = extract_longitudinal_context(payload)
        assert extracted is not None
        self.assertEqual(extracted["origin"], "deterministic_longitudinal_analytics")

    def test_agent_payload_includes_longitudinal_contract(self) -> None:
        session = open_test_session()
        try:
            user = seed_demo_health_data(session, reset=True)
            payload = get_health_trends_for_agent(user.id, as_of_date=checkpoint_date(89))
            self.assertIn("longitudinal_summary", payload)
            self.assertIn("longitudinal", payload["trends"][0])
            self.assertIn("maintenance_of_gain", payload["trends"][0]["longitudinal"])
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
