"""Offline tests for F4.1 data-maturity and claim-eligibility rules."""

from __future__ import annotations

import unittest

from analytics.maturity import (
    CADENCE_DAILY,
    CADENCE_EPISODIC,
    MIN_RECOMMENDATION_COVERAGE_RATIO,
    STATE_EARLY_PATTERN,
    STATE_ESTABLISHED_TREND,
    STATE_NO_USABLE_DATA,
    STATE_SNAPSHOT,
    compute_claim_flags,
    compute_weekly_claim_semantics,
    expected_current_observations,
)


class MaturityRuleTests(unittest.TestCase):
    def test_daily_expected_current_is_seven(self) -> None:
        self.assertEqual(expected_current_observations(CADENCE_DAILY), 7)

    def test_episodic_expected_current_is_one(self) -> None:
        self.assertEqual(expected_current_observations(CADENCE_EPISODIC), 1)

    def test_no_observations_is_unusable(self) -> None:
        flags = compute_claim_flags(
            cadence=CADENCE_DAILY,
            current_count=0,
            baseline_count=0,
            expected_current=7,
            has_any_valid_observation=False,
            as_of_available=False,
        )
        self.assertEqual(flags["data_maturity_state"], STATE_NO_USABLE_DATA)
        self.assertFalse(flags["snapshot_allowed"])
        self.assertFalse(flags["trend_allowed"])
        self.assertTrue(flags["gap_caveat_required"])

    def test_one_recent_observation_is_snapshot_only(self) -> None:
        flags = compute_claim_flags(
            cadence=CADENCE_DAILY,
            current_count=1,
            baseline_count=0,
            expected_current=7,
            has_any_valid_observation=True,
            as_of_available=True,
        )
        self.assertEqual(flags["data_maturity_state"], STATE_SNAPSHOT)
        self.assertTrue(flags["snapshot_allowed"])
        self.assertFalse(flags["early_pattern_allowed"])
        self.assertFalse(flags["trend_allowed"])
        self.assertFalse(flags["recommendation_support_allowed"])

    def test_three_recent_without_baseline_is_early_pattern(self) -> None:
        flags = compute_claim_flags(
            cadence=CADENCE_DAILY,
            current_count=3,
            baseline_count=4,
            expected_current=7,
            has_any_valid_observation=True,
            as_of_available=True,
        )
        self.assertEqual(flags["data_maturity_state"], STATE_EARLY_PATTERN)
        self.assertTrue(flags["early_pattern_allowed"])
        self.assertFalse(flags["trend_allowed"])
        self.assertFalse(flags["recommendation_support_allowed"])

    def test_established_trend_requires_ten_baseline_and_three_recent(self) -> None:
        flags = compute_claim_flags(
            cadence=CADENCE_DAILY,
            current_count=5,
            baseline_count=10,
            expected_current=7,
            has_any_valid_observation=True,
            as_of_available=True,
        )
        self.assertEqual(flags["data_maturity_state"], STATE_ESTABLISHED_TREND)
        self.assertTrue(flags["trend_allowed"])
        self.assertGreaterEqual(flags["coverage_ratio"], MIN_RECOMMENDATION_COVERAGE_RATIO)
        self.assertTrue(flags["recommendation_support_allowed"])
        self.assertEqual(flags["recommendation_basis"], "established_trend")

    def test_as_of_missing_does_not_block_trend_but_requires_gap_caveat(self) -> None:
        flags = compute_claim_flags(
            cadence=CADENCE_DAILY,
            current_count=5,
            baseline_count=20,
            expected_current=7,
            has_any_valid_observation=True,
            as_of_available=False,
        )
        self.assertTrue(flags["trend_allowed"])
        self.assertTrue(flags["gap_caveat_required"])
        self.assertTrue(flags["partial_coverage"])

    def test_episodic_missing_today_does_not_require_gap_caveat(self) -> None:
        flags = compute_claim_flags(
            cadence=CADENCE_EPISODIC,
            current_count=1,
            baseline_count=12,
            expected_current=1,
            has_any_valid_observation=True,
            as_of_available=False,
        )
        self.assertTrue(flags["trend_allowed"])
        self.assertFalse(flags["gap_caveat_required"])

    def test_episodic_three_estimates_unlock_early_pattern(self) -> None:
        flags = compute_claim_flags(
            cadence=CADENCE_EPISODIC,
            current_count=1,
            baseline_count=2,
            expected_current=1,
            has_any_valid_observation=True,
            as_of_available=True,
        )
        self.assertEqual(flags["data_maturity_state"], STATE_EARLY_PATTERN)
        self.assertFalse(flags["trend_allowed"])

    def test_weekly_value_allowed_with_partial_coverage(self) -> None:
        flags = compute_weekly_claim_semantics(
            observed_count=5,
            week_aligns_with_as_of_trend=True,
            trend_allowed=True,
            recommendation_support_allowed=True,
        )
        self.assertTrue(flags["summary_value_allowed"])
        self.assertTrue(flags["summary_comparison_allowed"])

    def test_weekly_comparison_requires_as_of_trend_gate(self) -> None:
        flags = compute_weekly_claim_semantics(
            observed_count=7,
            week_aligns_with_as_of_trend=True,
            trend_allowed=False,
            recommendation_support_allowed=False,
        )
        self.assertTrue(flags["summary_value_allowed"])
        self.assertFalse(flags["summary_comparison_allowed"])
        self.assertFalse(flags["summary_recommendation_support_allowed"])

    def test_weekly_no_observations_forbids_aggregate_claim(self) -> None:
        flags = compute_weekly_claim_semantics(
            observed_count=0,
            week_aligns_with_as_of_trend=True,
            trend_allowed=True,
            recommendation_support_allowed=True,
        )
        self.assertFalse(flags["summary_value_allowed"])
        self.assertFalse(flags["summary_comparison_allowed"])
        self.assertFalse(flags["summary_recommendation_support_allowed"])


if __name__ == "__main__":
    unittest.main()
