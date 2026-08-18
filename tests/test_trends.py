"""Offline tests for deterministic health trend analytics."""

from __future__ import annotations

import json
import unittest
from datetime import date, timedelta

from analytics.trends import get_health_trends, get_weekly_summaries
from app.health_tools import get_health_trends_for_agent
from data.demo_seed import (
    CHECKPOINT_DAY_30_INDEX,
    CHECKPOINT_DAY_60_INDEX,
    CHECKPOINT_DAY_75_INDEX,
    CHECKPOINT_DAY_90_INDEX,
    checkpoint_date,
    seed_demo_health_data,
)
from data.models import HealthDaily
from data.repository import create_user, upsert_health_daily
from tests.test_helpers import open_test_session


class TrendEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = open_test_session()
        self.user = seed_demo_health_data(self.session, reset=True)

    def tearDown(self) -> None:
        self.session.close()

    def _trend(self, metric: str, day_index: int):
        trends = get_health_trends(
            self.session, self.user.id, as_of_date=checkpoint_date(day_index)
        )
        return next(trend for trend in trends if trend.metric == metric)

    def test_day_30_mostly_stable_signals(self) -> None:
        rhr = self._trend("resting_hr_bpm", CHECKPOINT_DAY_30_INDEX)
        sleep = self._trend("sleep_duration_hours", CHECKPOINT_DAY_30_INDEX)
        self.assertTrue(rhr.data_sufficient)
        self.assertIn(rhr.direction, {"stable", "increasing", "declining"})
        self.assertIn(sleep.direction, {"stable", "increasing", "declining", "decreasing", "improving"})

    def test_day_60_exercise_and_rhr_improvement_pattern(self) -> None:
        exercise = self._trend("exercise_minutes", CHECKPOINT_DAY_60_INDEX)
        rhr = self._trend("resting_hr_bpm", CHECKPOINT_DAY_60_INDEX)
        vo2 = self._trend("vo2_max", CHECKPOINT_DAY_60_INDEX)
        self.assertTrue(exercise.data_sufficient)
        self.assertEqual(exercise.direction, "improving")
        self.assertLess(rhr.current_value, rhr.baseline_value)
        self.assertTrue(vo2.data_sufficient)
        self.assertGreater(vo2.current_value, vo2.baseline_value)

    def test_day_75_disruption_mixed_signals(self) -> None:
        sleep = self._trend("sleep_duration_hours", CHECKPOINT_DAY_75_INDEX)
        rhr = self._trend("resting_hr_bpm", CHECKPOINT_DAY_75_INDEX)
        self.assertTrue(sleep.data_sufficient)
        self.assertLess(sleep.current_value, sleep.baseline_value)
        self.assertIn(sleep.direction, {"declining", "decreasing"})
        self.assertGreater(rhr.current_value, rhr.baseline_value)

    def test_day_90_recovery_and_longer_term_fitness(self) -> None:
        sleep = self._trend("sleep_duration_hours", CHECKPOINT_DAY_90_INDEX)
        rhr = self._trend("resting_hr_bpm", CHECKPOINT_DAY_90_INDEX)
        exercise = self._trend("exercise_minutes", CHECKPOINT_DAY_90_INDEX)
        self.assertTrue(exercise.data_sufficient)
        # Recovery week may show improving sleep vs disruption baseline window
        self.assertGreater(sleep.current_value, 6.0)
        self.assertLess(rhr.current_value, 70.0)

    def test_missing_data_does_not_break_trends(self) -> None:
        hrv_trend = self._trend("hrv_sdnn_ms", CHECKPOINT_DAY_90_INDEX)
        self.assertIsNotNone(hrv_trend.current_value)
        self.assertIsNotNone(hrv_trend.baseline_value)

    def test_insufficient_data_marks_data_sufficient_false(self) -> None:
        sparse_user = create_user(self.session, display_name="Sparse User")
        self.session.flush()
        start = date(2026, 1, 1)
        for offset in range(10):
            upsert_health_daily(
                self.session,
                HealthDaily(
                    user_id=sparse_user.id,
                    date=start + timedelta(days=offset),
                    sleep_duration_hours=7.0,
                    resting_hr_bpm=60.0,
                ),
            )
        self.session.commit()

        trends = get_health_trends(
            self.session,
            sparse_user.id,
            as_of_date=start + timedelta(days=9),
        )
        sleep_trend = next(trend for trend in trends if trend.metric == "sleep_duration_hours")
        self.assertFalse(sleep_trend.data_sufficient)

    def test_no_divide_by_zero_on_zero_baseline(self) -> None:
        user = create_user(self.session, display_name="Zero Baseline")
        self.session.flush()
        start = date(2026, 5, 1)
        for offset in range(40):
            upsert_health_daily(
                self.session,
                HealthDaily(
                    user_id=user.id,
                    date=start + timedelta(days=offset),
                    workout_count=0,
                ),
            )
        self.session.commit()

        trend = next(
            trend
            for trend in get_health_trends(
                self.session,
                user.id,
                as_of_date=start + timedelta(days=39),
            )
            if trend.metric == "workout_count"
        )
        self.assertIsNone(trend.percent_change)
        self.assertEqual(trend.direction, "unknown")

    def test_weekly_summaries_return_recent_aggregates(self) -> None:
        summaries = get_weekly_summaries(
            self.session,
            self.user.id,
            as_of_date=checkpoint_date(CHECKPOINT_DAY_90_INDEX),
            weeks=2,
        )
        self.assertEqual(len(summaries), 2)
        self.assertIsNotNone(summaries[-1].average_sleep_hours)

    def test_agent_tool_returns_json_serializable_payload(self) -> None:
        payload = get_health_trends_for_agent(
            self.user.id, as_of_date=checkpoint_date(CHECKPOINT_DAY_90_INDEX)
        )
        serialized = json.dumps(payload)
        self.assertIn("trends", serialized)
        self.assertIn("disclaimer", serialized)
        self.assertIn("weekly_summaries", serialized)


if __name__ == "__main__":
    unittest.main()
