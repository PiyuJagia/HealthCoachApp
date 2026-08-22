"""Configurable data-maturity and claim-eligibility rules (F4.1).

Thresholds are MVP product knobs, not physiological constants.
"""

from __future__ import annotations

from dataclasses import dataclass

# Windowing
CURRENT_WINDOW_DAYS = 7
BASELINE_LOOKBACK_DAYS = 60
MEDIUM_HORIZON_DAYS = 30
LONG_HORIZON_DAYS = 90

# Observation thresholds (valid days, not consecutive occupancy)
MIN_SNAPSHOT_OBSERVATIONS = 1
MIN_EARLY_PATTERN_OBSERVATIONS = 3
MIN_BASELINE_VALID_DAYS = 10
MIN_TREND_RECENT_DAILY = 3
MIN_TREND_RECENT_EPISODIC = 1
MIN_LONGITUDINAL_REFERENCE_OBS = MIN_BASELINE_VALID_DAYS

# F4.1 conservative recommendation gate. Future product may allow
# snapshot- and pattern-based directives when evidence-authorized.
RECOMMENDATION_REQUIRES_TREND = True
MIN_RECOMMENDATION_COVERAGE_RATIO = 4 / 7

STABLE_PERCENT_THRESHOLD = 3.0
LONGITUDINAL_MATERIAL_PERCENT = STABLE_PERCENT_THRESHOLD

CADENCE_DAILY = "daily"
CADENCE_ACTIVITY_DEPENDENT = "activity_dependent"
CADENCE_EPISODIC = "episodic"

STATE_NO_USABLE_DATA = "NO_USABLE_DATA"
STATE_SNAPSHOT = "SNAPSHOT"
STATE_EARLY_PATTERN = "EARLY_PATTERN"
STATE_ESTABLISHED_TREND = "ESTABLISHED_TREND"

BASIS_NONE = "none"
BASIS_ESTABLISHED_TREND = "established_trend"
BASIS_EARLY_PATTERN = "early_pattern"
BASIS_SNAPSHOT = "snapshot"


@dataclass(frozen=True)
class MetricSpec:
    metric: str
    cadence: str
    higher_is_improvement: bool
    field_name: str
    control_metric: bool = False


METRIC_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec("sleep_duration_hours", CADENCE_DAILY, False, "sleep_duration_hours"),
    MetricSpec("resting_hr_bpm", CADENCE_DAILY, False, "resting_hr_bpm"),
    MetricSpec("hrv_sdnn_ms", CADENCE_DAILY, True, "hrv_sdnn_ms"),
    MetricSpec("exercise_minutes", CADENCE_ACTIVITY_DEPENDENT, True, "exercise_minutes"),
    MetricSpec("workout_count", CADENCE_ACTIVITY_DEPENDENT, True, "workout_count"),
    MetricSpec("steps", CADENCE_DAILY, True, "steps"),
    MetricSpec("vo2_max", CADENCE_EPISODIC, True, "vo2_max"),
    MetricSpec("respiratory_rate", CADENCE_DAILY, False, "respiratory_rate", True),
)


def expected_current_observations(cadence: str) -> int:
    if cadence == CADENCE_EPISODIC:
        return 1
    return CURRENT_WINDOW_DAYS


def coverage_ratio(observation_count: int, expected_count: int) -> float:
    if expected_count <= 0:
        return 0.0
    return round(min(1.0, observation_count / expected_count), 4)


def derive_maturity_state(
    *,
    snapshot_allowed: bool,
    early_pattern_allowed: bool,
    trend_allowed: bool,
) -> str:
    if trend_allowed:
        return STATE_ESTABLISHED_TREND
    if early_pattern_allowed:
        return STATE_EARLY_PATTERN
    if snapshot_allowed:
        return STATE_SNAPSHOT
    return STATE_NO_USABLE_DATA


def compute_weekly_claim_semantics(
    *,
    observed_count: int,
    week_aligns_with_as_of_trend: bool,
    trend_allowed: bool,
    recommendation_support_allowed: bool,
) -> dict[str, bool]:
    """Weekly-summary gates. Distinct from trend snapshot/early/trend flags.

    A weekly aggregate may describe recorded values with partial coverage.
    Directional comparison and recommendation support are never authorized
    independently; they follow the matching as-of trend contract.
    """
    summary_value_allowed = observed_count > 0
    summary_comparison_allowed = (
        summary_value_allowed and week_aligns_with_as_of_trend and trend_allowed
    )
    summary_recommendation_support_allowed = (
        summary_value_allowed
        and week_aligns_with_as_of_trend
        and recommendation_support_allowed
    )
    return {
        "summary_value_allowed": summary_value_allowed,
        "summary_comparison_allowed": summary_comparison_allowed,
        "summary_recommendation_support_allowed": summary_recommendation_support_allowed,
    }


def weekly_aggregation(metric: str) -> str:
    if metric in {"exercise_minutes", "workout_count"}:
        return "sum"
    return "mean"


def weekly_missing_count(*, cadence: str, observed_count: int, expected_count: int) -> int:
    if cadence == CADENCE_EPISODIC:
        return 0 if observed_count >= expected_count else expected_count
    return max(0, expected_count - observed_count)


def compute_claim_flags(
    *,
    cadence: str,
    current_count: int,
    baseline_count: int,
    expected_current: int,
    has_any_valid_observation: bool,
    as_of_available: bool,
) -> dict[str, object]:
    snapshot_allowed = has_any_valid_observation and current_count + baseline_count >= MIN_SNAPSHOT_OBSERVATIONS
    if cadence == CADENCE_EPISODIC:
        early_pattern_allowed = (current_count + baseline_count) >= MIN_EARLY_PATTERN_OBSERVATIONS
        trend_recent_ok = current_count >= MIN_TREND_RECENT_EPISODIC
        gap_caveat_required = False
    else:
        early_pattern_allowed = current_count >= MIN_EARLY_PATTERN_OBSERVATIONS
        trend_recent_ok = current_count >= MIN_TREND_RECENT_DAILY
        gap_caveat_required = not as_of_available

    baseline_ready = baseline_count >= MIN_BASELINE_VALID_DAYS
    trend_allowed = baseline_ready and trend_recent_ok
    ratio = coverage_ratio(current_count, expected_current)
    recommendation_support_allowed = False
    recommendation_basis = BASIS_NONE
    if RECOMMENDATION_REQUIRES_TREND:
        recommendation_support_allowed = trend_allowed and ratio >= MIN_RECOMMENDATION_COVERAGE_RATIO
        if recommendation_support_allowed:
            recommendation_basis = BASIS_ESTABLISHED_TREND
    elif trend_allowed:
        recommendation_support_allowed = True
        recommendation_basis = BASIS_ESTABLISHED_TREND
    elif early_pattern_allowed:
        recommendation_support_allowed = True
        recommendation_basis = BASIS_EARLY_PATTERN
    elif snapshot_allowed:
        recommendation_support_allowed = True
        recommendation_basis = BASIS_SNAPSHOT

    partial_coverage = current_count < expected_current
    return {
        "snapshot_allowed": snapshot_allowed,
        "early_pattern_allowed": early_pattern_allowed,
        "trend_allowed": trend_allowed,
        "recommendation_support_allowed": recommendation_support_allowed,
        "recommendation_basis": recommendation_basis,
        "baseline_ready": baseline_ready,
        "coverage_ratio": ratio,
        "partial_coverage": partial_coverage,
        "gap_caveat_required": gap_caveat_required,
        "data_maturity_state": derive_maturity_state(
            snapshot_allowed=snapshot_allowed,
            early_pattern_allowed=early_pattern_allowed,
            trend_allowed=trend_allowed,
        ),
    }
