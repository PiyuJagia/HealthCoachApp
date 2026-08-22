"""Offline tests for deterministic health trend analytics."""

from __future__ import annotations

import json
import unittest
from datetime import date, timedelta

from analytics.maturity import (
    CADENCE_ACTIVITY_DEPENDENT,
    CADENCE_DAILY,
    CADENCE_EPISODIC,
    STATE_EARLY_PATTERN,
    STATE_ESTABLISHED_TREND,
)
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
        self.assertTrue(rhr.claim_eligibility.trend_allowed)
        self.assertEqual(rhr.cadence, CADENCE_DAILY)
        self.assertIn(rhr.direction, {"stable", "increasing", "declining"})
        self.assertIn(sleep.direction, {"stable", "increasing", "declining", "decreasing", "improving"})

    def test_day_60_exercise_and_rhr_improvement_pattern(self) -> None:
        exercise = self._trend("exercise_minutes", CHECKPOINT_DAY_60_INDEX)
        rhr = self._trend("resting_hr_bpm", CHECKPOINT_DAY_60_INDEX)
        vo2 = self._trend("vo2_max", CHECKPOINT_DAY_60_INDEX)
        self.assertEqual(exercise.cadence, CADENCE_ACTIVITY_DEPENDENT)
        self.assertTrue(exercise.claim_eligibility.trend_allowed)
        self.assertEqual(exercise.direction, "improving")
        self.assertLess(rhr.current_value, rhr.baseline_value)
        self.assertEqual(vo2.cadence, CADENCE_EPISODIC)
        self.assertEqual(vo2.expected_observation_count_current, 1)
        self.assertGreater(vo2.current_value, vo2.baseline_value)

    def test_day_75_disruption_mixed_signals(self) -> None:
        sleep = self._trend("sleep_duration_hours", CHECKPOINT_DAY_75_INDEX)
        rhr = self._trend("resting_hr_bpm", CHECKPOINT_DAY_75_INDEX)
        self.assertTrue(sleep.claim_eligibility.trend_allowed)
        self.assertLess(sleep.current_value, sleep.baseline_value)
        self.assertIn(sleep.direction, {"declining", "decreasing"})
        self.assertGreater(rhr.current_value, rhr.baseline_value)

    def test_day_90_recovery_and_longer_term_fitness(self) -> None:
        sleep = self._trend("sleep_duration_hours", CHECKPOINT_DAY_90_INDEX)
        rhr = self._trend("resting_hr_bpm", CHECKPOINT_DAY_90_INDEX)
        exercise = self._trend("exercise_minutes", CHECKPOINT_DAY_90_INDEX)
        self.assertTrue(exercise.claim_eligibility.trend_allowed)
        self.assertGreater(sleep.current_value, 6.0)
        self.assertLess(rhr.current_value, 70.0)

    def test_missing_data_does_not_break_trends(self) -> None:
        hrv_trend = self._trend("hrv_sdnn_ms", CHECKPOINT_DAY_90_INDEX)
        self.assertIsNotNone(hrv_trend.current_value)
        self.assertIsNotNone(hrv_trend.baseline_value)

    def test_short_history_is_early_pattern_not_silenced(self) -> None:
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
        self.assertFalse(sleep_trend.baseline_ready)
        self.assertFalse(sleep_trend.claim_eligibility.trend_allowed)
        self.assertTrue(sleep_trend.claim_eligibility.early_pattern_allowed)
        self.assertEqual(sleep_trend.data_maturity_state, STATE_EARLY_PATTERN)
        self.assertEqual(sleep_trend.direction, "unknown")
        self.assertIsNone(sleep_trend.percent_change)
        self.assertNotIn("data_sufficient", sleep_trend.to_dict())

    def test_ten_valid_baseline_days_need_not_be_consecutive(self) -> None:
        user = create_user(self.session, display_name="Gappy Baseline")
        self.session.flush()
        start = date(2026, 3, 1)
        as_of = start + timedelta(days=40)
        # 10 scattered historical sleep days, then 4 recent days including as_of.
        historical = [0, 2, 5, 9, 12, 16, 20, 24, 28, 32]
        recent = [37, 38, 39, 40]
        for offset in historical + recent:
            upsert_health_daily(
                self.session,
                HealthDaily(
                    user_id=user.id,
                    date=start + timedelta(days=offset),
                    sleep_duration_hours=7.0 if offset in historical else 6.0,
                ),
            )
        self.session.commit()

        sleep = next(
            trend
            for trend in get_health_trends(self.session, user.id, as_of_date=as_of)
            if trend.metric == "sleep_duration_hours"
        )
        self.assertGreaterEqual(sleep.baseline_observation_count, 10)
        self.assertTrue(sleep.baseline_ready)
        self.assertGreaterEqual(sleep.observation_count_current, 3)
        self.assertTrue(sleep.claim_eligibility.trend_allowed)
        self.assertEqual(sleep.direction, "decreasing")

    def test_zero_workout_count_is_valid_observation(self) -> None:
        user = create_user(self.session, display_name="Rest Days")
        self.session.flush()
        start = date(2026, 4, 1)
        for offset in range(20):
            upsert_health_daily(
                self.session,
                HealthDaily(
                    user_id=user.id,
                    date=start + timedelta(days=offset),
                    workout_count=0,
                    exercise_minutes=0.0,
                ),
            )
        self.session.commit()
        trend = next(
            trend
            for trend in get_health_trends(
                self.session, user.id, as_of_date=start + timedelta(days=19)
            )
            if trend.metric == "workout_count"
        )
        self.assertEqual(trend.observation_count_current, 7)
        self.assertEqual(trend.baseline_observation_count, 13)
        self.assertTrue(trend.as_of_date_available)
        self.assertEqual(trend.as_of_date_value, 0.0)

    def test_null_is_missing_not_zero(self) -> None:
        user = create_user(self.session, display_name="Null Sleep")
        self.session.flush()
        start = date(2026, 4, 1)
        for offset in range(20):
            sleep = None if offset == 19 else 7.0
            upsert_health_daily(
                self.session,
                HealthDaily(
                    user_id=user.id,
                    date=start + timedelta(days=offset),
                    sleep_duration_hours=sleep,
                ),
            )
        self.session.commit()
        trend = next(
            trend
            for trend in get_health_trends(
                self.session, user.id, as_of_date=start + timedelta(days=19)
            )
            if trend.metric == "sleep_duration_hours"
        )
        self.assertFalse(trend.as_of_date_available)
        self.assertIsNone(trend.as_of_date_value)
        self.assertEqual(trend.observation_count_current, 6)
        self.assertTrue(trend.gap_caveat_required)

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

    def test_weekly_summaries_include_coverage_provenance(self) -> None:
        summaries = get_weekly_summaries(
            self.session,
            self.user.id,
            as_of_date=checkpoint_date(CHECKPOINT_DAY_90_INDEX),
            weeks=2,
        )
        self.assertEqual(len(summaries), 2)
        self.assertIsNotNone(summaries[-1].average_sleep_hours)
        sleep_coverage = summaries[-1].coverage["sleep_duration_hours"]
        self.assertGreater(sleep_coverage.observation_count, 0)
        self.assertEqual(sleep_coverage.expected_observation_count, 7)
        payload = summaries[-1].to_dict()
        self.assertIn("coverage", payload)
        self.assertTrue(payload["as_of_aligned"])
        self.assertIn("observation_count", payload["coverage"]["sleep_duration_hours"])
        self.assertIn("claim_semantics", payload["coverage"]["sleep_duration_hours"])
        self.assertNotIn("claim_eligibility", payload["coverage"]["sleep_duration_hours"])

    def test_agent_tool_returns_json_serializable_payload(self) -> None:
        payload = get_health_trends_for_agent(
            self.user.id, as_of_date=checkpoint_date(CHECKPOINT_DAY_90_INDEX)
        )
        serialized = json.dumps(payload)
        self.assertIn("trends", serialized)
        self.assertIn("disclaimer", serialized)
        self.assertIn("weekly_summaries", serialized)
        self.assertNotIn("data_sufficient", serialized)
        self.assertIn("claim_eligibility", serialized)
        self.assertIn("gap_caveat_required", serialized)
        self.assertIn("coverage", payload["weekly_summaries"][0])
        self.assertIn("claim_semantics", payload["weekly_summaries"][0]["coverage"]["sleep_duration_hours"])
        self.assertIn("summary_value_allowed", json.dumps(payload["weekly_summaries"][0]))


class FamilyDContractTests(unittest.TestCase):
    """Deterministic D1/D2/D3 contract checks against Marcus seed dates."""

    def setUp(self) -> None:
        self.session = open_test_session()
        self.user = seed_demo_health_data(self.session, reset=True)

    def tearDown(self) -> None:
        self.session.close()

    def _by_metric(self, as_of: date) -> dict:
        return {
            trend.metric: trend
            for trend in get_health_trends(self.session, self.user.id, as_of_date=as_of)
        }

    def test_d1_hrv_missing_today_keeps_qualified_trend(self) -> None:
        trends = self._by_metric(date(2026, 7, 13))
        hrv = trends["hrv_sdnn_ms"]
        self.assertFalse(hrv.as_of_date_available)
        self.assertIsNone(hrv.as_of_date_value)
        self.assertTrue(hrv.gap_caveat_required)
        self.assertTrue(hrv.partial_coverage)
        self.assertEqual(hrv.observation_count_current, 5)
        self.assertEqual(hrv.expected_observation_count_current, 7)
        self.assertTrue(hrv.baseline_ready)
        self.assertTrue(hrv.claim_eligibility.trend_allowed)
        self.assertIsNotNone(hrv.percent_change)
        self.assertNotEqual(hrv.direction, "unknown")
        self.assertEqual(hrv.data_maturity_state, STATE_ESTABLISHED_TREND)

    def test_d2_full_sync_gap_today_does_not_silence_history(self) -> None:
        as_of = date(2026, 6, 10)
        trends = self._by_metric(as_of)
        payload = get_health_trends_for_agent(self.user.id, as_of_date=as_of)
        self.assertTrue(payload["gap_caveat_required"])
        self.assertFalse(payload["as_of_any_daily_metric_available"])
        for metric in (
            "sleep_duration_hours",
            "resting_hr_bpm",
            "hrv_sdnn_ms",
            "steps",
            "exercise_minutes",
            "workout_count",
        ):
            trend = trends[metric]
            self.assertFalse(trend.as_of_date_available, msg=metric)
            self.assertTrue(trend.gap_caveat_required, msg=metric)
            self.assertTrue(trend.claim_eligibility.snapshot_allowed, msg=metric)
            self.assertTrue(trend.baseline_ready, msg=metric)
            self.assertTrue(trend.claim_eligibility.trend_allowed, msg=metric)

    def test_d3_early_window_allows_qualified_daily_claims(self) -> None:
        trends = self._by_metric(date(2026, 6, 8))
        sleep = trends["sleep_duration_hours"]
        vo2 = trends["vo2_max"]
        self.assertGreaterEqual(sleep.baseline_observation_count, 10)
        self.assertTrue(sleep.baseline_ready)
        self.assertTrue(sleep.claim_eligibility.trend_allowed)
        self.assertTrue(sleep.claim_eligibility.snapshot_allowed)
        self.assertEqual(sleep.data_maturity_state, STATE_ESTABLISHED_TREND)
        self.assertEqual(vo2.cadence, CADENCE_EPISODIC)
        self.assertEqual(vo2.expected_observation_count_current, 1)
        self.assertIn(
            vo2.data_maturity_state,
            {STATE_EARLY_PATTERN, STATE_ESTABLISHED_TREND, "SNAPSHOT"},
        )


if __name__ == "__main__":
    unittest.main()
