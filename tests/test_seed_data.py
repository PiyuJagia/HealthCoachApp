"""Offline tests for deterministic synthetic demo data (E1.1 story)."""

from __future__ import annotations

import unittest
from datetime import timedelta
from statistics import mean, pstdev

from data.demo_seed import (
    CHECKPOINT_DAY_60_INDEX,
    DEMO_DAY_COUNT,
    DEMO_DISPLAY_NAME,
    DEMO_END_DATE,
    DEMO_GOAL,
    DEMO_RANDOM_SEED,
    PHASE1_END_INDEX,
    PHASE2_END_INDEX,
    PHASE2_ROUTINE_START_INDEX,
    PHASE3_DISRUPTION_END_INDEX,
    PHASE3_DISRUPTION_START_INDEX,
    PHASE3_RECOVERY_START_INDEX,
    checkpoint_date,
    ensure_demo_health_data,
    seed_demo_health_data,
)
from data.repository import list_health_daily_for_user, list_lifestyle_events_for_user
from tests.test_helpers import open_test_session


class SeedDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = open_test_session()
        self.user = seed_demo_health_data(self.session, reset=True)

    def tearDown(self) -> None:
        self.session.close()

    def test_seed_is_deterministic(self) -> None:
        first = list_health_daily_for_user(self.session, self.user.id)
        self.session.close()

        session_two = open_test_session()
        user_two = seed_demo_health_data(session_two, reset=True)
        second = list_health_daily_for_user(session_two, user_two.id)
        session_two.close()

        self.assertEqual(
            [(r.date, r.sleep_duration_hours, r.resting_hr_bpm, r.hrv_sdnn_ms) for r in first],
            [(r.date, r.sleep_duration_hours, r.resting_hr_bpm, r.hrv_sdnn_ms) for r in second],
        )

    def test_ninety_day_coverage(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        self.assertEqual(len(records), DEMO_DAY_COUNT)
        self.assertEqual(records[0].date, DEMO_END_DATE - timedelta(days=DEMO_DAY_COUNT - 1))
        self.assertEqual(records[-1].date, DEMO_END_DATE)

    def test_demo_user_profile(self) -> None:
        self.assertEqual(self.user.display_name, DEMO_DISPLAY_NAME)
        self.assertEqual(self.user.goal, DEMO_GOAL)
        self.assertEqual(self.user.age, 36)
        self.assertEqual(self.user.sex, "male")
        self.assertEqual(self.user.height_cm, 177.0)
        self.assertEqual(self.user.weight_kg, 84.0)

    def test_phase1_lacks_strong_directional_trend(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)[: PHASE1_END_INDEX + 1]
        first_half = records[:15]
        second_half = records[15:]
        rhr_first = mean(r.resting_hr_bpm for r in first_half if r.resting_hr_bpm is not None)
        rhr_second = mean(r.resting_hr_bpm for r in second_half if r.resting_hr_bpm is not None)
        sleep_first = mean(r.sleep_duration_hours for r in first_half if r.sleep_duration_hours is not None)
        sleep_second = mean(r.sleep_duration_hours for r in second_half if r.sleep_duration_hours is not None)
        self.assertLess(abs(rhr_second - rhr_first), 2.5)
        self.assertLess(abs(sleep_second - sleep_first), 0.8)

    def test_structured_exercise_begins_around_day_35(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        pre_routine = records[PHASE2_ROUTINE_START_INDEX - 7 : PHASE2_ROUTINE_START_INDEX]
        post_routine = records[PHASE2_ROUTINE_START_INDEX : PHASE2_ROUTINE_START_INDEX + 14]
        pre_workouts = sum(r.workout_count or 0 for r in pre_routine)
        post_workouts = sum(r.workout_count or 0 for r in post_routine)
        self.assertLessEqual(pre_workouts, 3)
        self.assertGreaterEqual(post_workouts, 5)

    def test_phase2_workout_frequency_about_three_per_week(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        phase2 = records[PHASE2_ROUTINE_START_INDEX : PHASE2_END_INDEX + 1]
        workouts = sum(r.workout_count or 0 for r in phase2)
        weeks = len(phase2) / 7
        self.assertGreaterEqual(workouts / weeks, 2.5)
        self.assertLessEqual(workouts / weeks, 3.5)

    def test_phase2_positive_fitness_pattern(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        phase1_rhr = mean(r.resting_hr_bpm for r in records[:30] if r.resting_hr_bpm is not None)
        phase2_end_rhr = mean(r.resting_hr_bpm for r in records[50:60] if r.resting_hr_bpm is not None)
        vo2_early = [r.vo2_max for r in records[30:40] if r.vo2_max is not None]
        vo2_late = [r.vo2_max for r in records[50:60] if r.vo2_max is not None]
        self.assertLess(phase2_end_rhr, phase1_rhr)
        self.assertGreater(mean(vo2_late), mean(vo2_early))

    def test_disruption_lowers_sleep(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        phase2_sleep = mean(
            r.sleep_duration_hours
            for r in records[45:60]
            if r.sleep_duration_hours is not None
        )
        disruption_sleep = mean(
            r.sleep_duration_hours
            for r in records[PHASE3_DISRUPTION_START_INDEX : PHASE3_DISRUPTION_END_INDEX + 1]
            if r.sleep_duration_hours is not None
        )
        self.assertLess(disruption_sleep, phase2_sleep)

    def test_disruption_increases_hrv_volatility_not_just_lower_mean(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        phase2_hrv = [
            r.hrv_sdnn_ms
            for r in records[35:60]
            if r.hrv_sdnn_ms is not None
        ]
        disruption_hrv = [
            r.hrv_sdnn_ms
            for r in records[PHASE3_DISRUPTION_START_INDEX : PHASE3_DISRUPTION_END_INDEX + 1]
            if r.hrv_sdnn_ms is not None
        ]
        self.assertGreater(pstdev(disruption_hrv), pstdev(phase2_hrv) + 2.0)

    def test_disruption_rhr_worse_than_phase2_end(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        phase2_end_rhr = mean(r.resting_hr_bpm for r in records[55:60] if r.resting_hr_bpm is not None)
        disruption_rhr = mean(
            r.resting_hr_bpm
            for r in records[PHASE3_DISRUPTION_START_INDEX : PHASE3_DISRUPTION_END_INDEX + 1]
            if r.resting_hr_bpm is not None
        )
        self.assertGreater(disruption_rhr, phase2_end_rhr)

    def test_recovery_toward_end(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        disruption_sleep = mean(
            r.sleep_duration_hours
            for r in records[PHASE3_DISRUPTION_START_INDEX : PHASE3_DISRUPTION_END_INDEX + 1]
            if r.sleep_duration_hours is not None
        )
        recovery_sleep = mean(
            r.sleep_duration_hours
            for r in records[PHASE3_RECOVERY_START_INDEX + 10 :]
            if r.sleep_duration_hours is not None
        )
        disruption_rhr = mean(
            r.resting_hr_bpm
            for r in records[PHASE3_DISRUPTION_START_INDEX : PHASE3_DISRUPTION_END_INDEX + 1]
            if r.resting_hr_bpm is not None
        )
        recovery_rhr = mean(r.resting_hr_bpm for r in records[-7:] if r.resting_hr_bpm is not None)
        self.assertGreater(recovery_sleep, disruption_sleep)
        self.assertLess(recovery_rhr, disruption_rhr)

    def test_caffeine_inside_and_outside_disruption(self) -> None:
        events = list_lifestyle_events_for_user(self.session, self.user.id)
        caffeine = [e for e in events if e.event_type == "caffeine"]
        disruption_start = checkpoint_date(PHASE3_DISRUPTION_START_INDEX)
        disruption_end = checkpoint_date(PHASE3_DISRUPTION_END_INDEX)
        during = [
            e for e in caffeine if disruption_start <= e.occurred_at.date() <= disruption_end
        ]
        outside = [e for e in caffeine if e not in during]
        self.assertGreaterEqual(len(during), 5)
        self.assertGreaterEqual(len(outside), 5)

    def test_caffeine_not_deterministically_mapped_to_poor_sleep(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        events = list_lifestyle_events_for_user(self.session, self.user.id)
        caffeine_dates = {e.occurred_at.date() for e in events if e.event_type == "caffeine"}
        sleep_on_caffeine_days = [
            r.sleep_duration_hours
            for r in records
            if r.date in caffeine_dates and r.sleep_duration_hours is not None
        ]
        sleep_on_non_caffeine_days = [
            r.sleep_duration_hours
            for r in records
            if r.date not in caffeine_dates and r.sleep_duration_hours is not None
        ]
        # Overlap exists — caffeine days are not uniformly worse sleep
        self.assertGreater(max(sleep_on_caffeine_days), min(sleep_on_non_caffeine_days))
        self.assertLess(min(sleep_on_caffeine_days), max(sleep_on_non_caffeine_days))

    def test_respiratory_rate_stable_control_signal(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        phase1 = [r.respiratory_rate for r in records[:30] if r.respiratory_rate is not None]
        phase2 = [r.respiratory_rate for r in records[30:60] if r.respiratory_rate is not None]
        disruption = [
            r.respiratory_rate
            for r in records[60:75]
            if r.respiratory_rate is not None
        ]
        recovery = [r.respiratory_rate for r in records[75:] if r.respiratory_rate is not None]
        for label, values in [("p1", phase1), ("p2", phase2), ("dis", disruption), ("rec", recovery)]:
            self.assertGreaterEqual(min(values), 13.5, label)
            self.assertLessEqual(max(values), 15.5, label)
        self.assertLess(abs(mean(phase1) - mean(disruption)), 0.5)

    def test_intentional_missing_data(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        self.assertEqual(len(records), 90)
        self.assertGreater(sum(1 for r in records if r.sleep_duration_hours is None), 0)
        self.assertGreater(sum(1 for r in records if r.hrv_sdnn_ms is None), 0)
        self.assertGreater(sum(1 for r in records if r.vo2_max is None), 0)
        self.assertGreater(sum(1 for r in records if r.exercise_minutes is None), 0)

    def test_sanity_bounds(self) -> None:
        records = list_health_daily_for_user(self.session, self.user.id)
        for record in records:
            if record.resting_hr_bpm is not None:
                self.assertGreaterEqual(record.resting_hr_bpm, 50)
                self.assertLessEqual(record.resting_hr_bpm, 85)
            if record.sleep_duration_hours is not None:
                self.assertGreaterEqual(record.sleep_duration_hours, 4.5)
                self.assertLessEqual(record.sleep_duration_hours, 9.5)
            if record.steps is not None:
                self.assertGreaterEqual(record.steps, 0)
            if record.exercise_minutes is not None:
                self.assertGreaterEqual(record.exercise_minutes, 0)

    def test_fixed_random_seed_constant(self) -> None:
        self.assertEqual(DEMO_RANDOM_SEED, 42)

    def test_ensure_demo_health_data_is_idempotent(self) -> None:
        first = ensure_demo_health_data(self.session)
        second = ensure_demo_health_data(self.session)
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.display_name, DEMO_DISPLAY_NAME)
        self.assertEqual(len(list_health_daily_for_user(self.session, first.id)), DEMO_DAY_COUNT)
        self.assertEqual(len(list_health_daily_for_user(self.session, second.id)), DEMO_DAY_COUNT)


class EnsureDemoDataEmptyTests(unittest.TestCase):
    def test_ensure_seeds_when_demo_user_is_missing(self) -> None:
        session = open_test_session()
        user = ensure_demo_health_data(session)
        self.assertEqual(user.display_name, DEMO_DISPLAY_NAME)
        self.assertEqual(len(list_health_daily_for_user(session, user.id)), DEMO_DAY_COUNT)
        again = ensure_demo_health_data(session)
        self.assertEqual(again.id, user.id)
        session.close()


if __name__ == "__main__":
    unittest.main()
