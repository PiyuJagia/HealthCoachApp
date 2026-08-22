"""Offline tests for F4.3 weekly-summary claim semantics."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from analytics.maturity import CADENCE_EPISODIC
from analytics.trends import get_health_trends, get_weekly_summaries
from data.demo_seed import seed_demo_health_data
from data.models import HealthDaily
from data.repository import create_user, upsert_health_daily
from tests.test_helpers import open_test_session


class WeeklySummaryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = open_test_session()

    def tearDown(self) -> None:
        self.session.close()

    def _user(self, name: str):
        user = create_user(self.session, display_name=name)
        self.session.flush()
        return user

    def _write_days(self, user_id: int, start: date, days: list[dict]) -> None:
        for offset, fields in enumerate(days):
            upsert_health_daily(
                self.session,
                HealthDaily(user_id=user_id, date=start + timedelta(days=offset), **fields),
            )
        self.session.commit()

    def test_full_coverage_week(self) -> None:
        user = self._user("Full Week")
        start = date(2026, 4, 1)
        self._write_days(
            user.id,
            start,
            [{"sleep_duration_hours": 7.0, "hrv_sdnn_ms": 30.0} for _ in range(20)],
        )
        as_of = start + timedelta(days=19)
        week = get_weekly_summaries(self.session, user.id, as_of_date=as_of, weeks=1)[0]
        sleep = week.coverage["sleep_duration_hours"]
        self.assertTrue(week.as_of_aligned)
        self.assertEqual(sleep.observation_count, 7)
        self.assertEqual(sleep.expected_observation_count, 7)
        self.assertEqual(sleep.missing_count, 0)
        self.assertFalse(sleep.partial_coverage)
        self.assertTrue(sleep.claim_semantics.summary_value_allowed)
        self.assertEqual(sleep.aggregate_value, week.average_sleep_hours)

    def test_partial_coverage_week(self) -> None:
        user = self._user("Partial Week")
        start = date(2026, 4, 1)
        days = []
        for offset in range(20):
            days.append({"hrv_sdnn_ms": None if offset >= 18 else 32.0, "sleep_duration_hours": 7.0})
        self._write_days(user.id, start, days)
        as_of = start + timedelta(days=19)
        week = get_weekly_summaries(self.session, user.id, as_of_date=as_of, weeks=1)[0]
        hrv = week.coverage["hrv_sdnn_ms"]
        self.assertEqual(hrv.observation_count, 5)
        self.assertEqual(hrv.expected_observation_count, 7)
        self.assertEqual(hrv.missing_count, 2)
        self.assertTrue(hrv.partial_coverage)
        self.assertTrue(hrv.claim_semantics.summary_value_allowed)
        self.assertIsNotNone(hrv.aggregate_value)

    def test_no_observations_forbids_aggregate(self) -> None:
        user = self._user("Empty HRV")
        start = date(2026, 4, 1)
        self._write_days(
            user.id,
            start,
            [{"sleep_duration_hours": 7.0, "hrv_sdnn_ms": None} for _ in range(20)],
        )
        as_of = start + timedelta(days=19)
        week = get_weekly_summaries(self.session, user.id, as_of_date=as_of, weeks=1)[0]
        hrv = week.coverage["hrv_sdnn_ms"]
        self.assertEqual(hrv.observation_count, 0)
        self.assertIsNone(hrv.aggregate_value)
        self.assertIsNone(week.average_hrv_sdnn_ms)
        self.assertFalse(hrv.claim_semantics.summary_value_allowed)
        self.assertFalse(hrv.claim_semantics.summary_comparison_allowed)

    def test_zero_workout_is_valid_not_null(self) -> None:
        user = self._user("Rest Week")
        start = date(2026, 4, 1)
        self._write_days(
            user.id,
            start,
            [{"workout_count": 0, "exercise_minutes": 0.0} for _ in range(20)],
        )
        as_of = start + timedelta(days=19)
        week = get_weekly_summaries(self.session, user.id, as_of_date=as_of, weeks=1)[0]
        workouts = week.coverage["workout_count"]
        exercise = week.coverage["exercise_minutes"]
        self.assertEqual(workouts.observation_count, 7)
        self.assertEqual(workouts.aggregate_value, 0.0)
        self.assertEqual(week.total_workouts, 0)
        self.assertEqual(exercise.aggregate_value, 0.0)
        self.assertEqual(week.total_exercise_minutes, 0.0)
        self.assertTrue(workouts.as_of_date_available)

    def test_null_exercise_is_missing_not_zero(self) -> None:
        user = self._user("Missing Exercise")
        start = date(2026, 4, 1)
        days = []
        for offset in range(20):
            if offset == 19:
                days.append({"workout_count": None, "exercise_minutes": None, "sleep_duration_hours": 7.0})
            else:
                days.append({"workout_count": 1, "exercise_minutes": 20.0, "sleep_duration_hours": 7.0})
        self._write_days(user.id, start, days)
        as_of = start + timedelta(days=19)
        week = get_weekly_summaries(self.session, user.id, as_of_date=as_of, weeks=1)[0]
        exercise = week.coverage["exercise_minutes"]
        self.assertFalse(exercise.as_of_date_available)
        self.assertTrue(exercise.gap_caveat_required)
        self.assertEqual(exercise.observation_count, 6)
        self.assertIsNotNone(exercise.aggregate_value)

    def test_episodic_vo2_does_not_use_daily_coverage(self) -> None:
        user = seed_demo_health_data(self.session, reset=True)
        week = get_weekly_summaries(
            self.session, user.id, as_of_date=date(2026, 7, 13), weeks=1
        )[0]
        vo2 = week.coverage["vo2_max"]
        self.assertEqual(vo2.cadence, CADENCE_EPISODIC)
        self.assertEqual(vo2.expected_observation_count, 1)
        self.assertFalse(vo2.gap_caveat_required)
        self.assertLessEqual(vo2.missing_count, 1)
        if vo2.observation_count >= 1:
            self.assertFalse(vo2.partial_coverage)
            self.assertEqual(vo2.coverage_ratio, 1.0)

    def test_gap_caveat_propagates_on_as_of_week(self) -> None:
        user = seed_demo_health_data(self.session, reset=True)
        week = get_weekly_summaries(
            self.session, user.id, as_of_date=date(2026, 7, 13), weeks=1
        )[0]
        hrv = week.coverage["hrv_sdnn_ms"]
        trend = next(
            item
            for item in get_health_trends(self.session, user.id, as_of_date=date(2026, 7, 13))
            if item.metric == "hrv_sdnn_ms"
        )
        self.assertTrue(hrv.gap_caveat_required)
        self.assertEqual(hrv.gap_caveat_required, trend.gap_caveat_required)
        self.assertFalse(hrv.as_of_date_available)

    def test_weekly_cannot_authorize_comparison_when_trend_forbids(self) -> None:
        user = self._user("Early Pattern")
        start = date(2026, 1, 1)
        self._write_days(
            user.id,
            start,
            [{"sleep_duration_hours": 7.0} for _ in range(10)],
        )
        as_of = start + timedelta(days=9)
        trend = next(
            item
            for item in get_health_trends(self.session, user.id, as_of_date=as_of)
            if item.metric == "sleep_duration_hours"
        )
        week = get_weekly_summaries(self.session, user.id, as_of_date=as_of, weeks=1)[0]
        sleep = week.coverage["sleep_duration_hours"]
        self.assertFalse(trend.claim_eligibility.trend_allowed)
        self.assertTrue(sleep.claim_semantics.summary_value_allowed)
        self.assertFalse(sleep.claim_semantics.summary_comparison_allowed)
        self.assertNotIn("claim_eligibility", sleep.to_dict())

    def test_weekly_cannot_bypass_recommendation_eligibility(self) -> None:
        user = self._user("Thin Recent")
        start = date(2026, 3, 1)
        all_days = []
        for offset in range(41):
            if offset <= 9 or offset >= 38:
                all_days.append({"sleep_duration_hours": 7.0 if offset <= 9 else 6.0})
            else:
                all_days.append({"sleep_duration_hours": None})
        self._write_days(user.id, start, all_days)
        as_of = start + timedelta(days=40)
        trend = next(
            item
            for item in get_health_trends(self.session, user.id, as_of_date=as_of)
            if item.metric == "sleep_duration_hours"
        )
        week = get_weekly_summaries(self.session, user.id, as_of_date=as_of, weeks=1)[0]
        sleep = week.coverage["sleep_duration_hours"]
        self.assertTrue(trend.claim_eligibility.trend_allowed)
        self.assertFalse(trend.claim_eligibility.recommendation_support_allowed)
        self.assertTrue(sleep.claim_semantics.summary_comparison_allowed)
        self.assertFalse(sleep.claim_semantics.summary_recommendation_support_allowed)

    def test_older_weeks_are_observed_only(self) -> None:
        user = seed_demo_health_data(self.session, reset=True)
        weeks = get_weekly_summaries(
            self.session, user.id, as_of_date=date(2026, 8, 2), weeks=4
        )
        self.assertTrue(weeks[-1].as_of_aligned)
        for older in weeks[:-1]:
            self.assertFalse(older.as_of_aligned)
            for coverage in older.coverage.values():
                if coverage.claim_semantics.summary_value_allowed:
                    self.assertFalse(coverage.claim_semantics.summary_comparison_allowed)
                    self.assertFalse(coverage.claim_semantics.summary_recommendation_support_allowed)

    def test_d1_d2_a1_alignment_closes_bypass(self) -> None:
        user = seed_demo_health_data(self.session, reset=True)
        from evals.weekly_inspection import inspect_weekly_alignment

        report = inspect_weekly_alignment(self.session, user.id)
        self.assertTrue(report["alignment_safe_to_accept"])
        self.assertTrue(report["bypass_closed"])


if __name__ == "__main__":
    unittest.main()
