"""Structured analytics outputs — observational, not causal."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ClaimEligibility:
    """Deterministic claim gates. F4.1 recommendations require an established trend.

    Future product may set recommendation_basis to snapshot or early_pattern;
    the field exists so that path does not require a new contract.
    """

    snapshot_allowed: bool
    early_pattern_allowed: bool
    trend_allowed: bool
    recommendation_support_allowed: bool
    recommendation_basis: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WithinWindowSpread:
    """Day-to-day spread of readings in the F4.1 current window.

    Observational only. Distinct from F4.1 level/direction. HRV-only in MVP.
    Does not diagnose, score, or authorize insights or recommendations.
    """

    observation_count: int
    mean: float | None
    sample_standard_deviation: float | None
    min: float | None
    max: float | None
    range: float | None
    baseline_standard_deviation: float | None
    spread_ratio: float | None
    spread_observation_allowed: bool
    spread_comparison_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrendResult:
    metric: str
    cadence: str
    current_value: float | None
    baseline_value: float | None
    absolute_change: float | None
    percent_change: float | None
    direction: str
    as_of_date_value: float | None
    as_of_date_available: bool
    observation_count_current: int
    expected_observation_count_current: int
    coverage_ratio: float
    baseline_observation_count: int
    baseline_ready: bool
    latest_valid_observation_date: date | None
    latest_valid_observation_value: float | None
    period_start: date
    period_end: date
    baseline_period_start: date
    baseline_period_end: date
    partial_coverage: bool
    gap_caveat_required: bool
    data_maturity_state: str
    claim_eligibility: ClaimEligibility
    longitudinal: LongitudinalContext
    salience: MetricSalience
    control_metric: bool = False
    within_window_spread: WithinWindowSpread | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "period_start",
            "period_end",
            "baseline_period_start",
            "baseline_period_end",
            "latest_valid_observation_date",
        ):
            value = payload[key]
            payload[key] = value.isoformat() if value is not None else None
        payload["claim_eligibility"] = self.claim_eligibility.to_dict()
        payload["longitudinal"] = self.longitudinal.to_dict()
        payload["salience"] = self.salience.to_dict()
        payload["within_window_spread"] = (
            self.within_window_spread.to_dict() if self.within_window_spread is not None else None
        )
        return payload


@dataclass(frozen=True)
class LongitudinalContext:
    """Older-horizon context the 7-vs-60 trend window does not see.

    Observational only. maintenance_of_gain is not a celebration directive
    and does not authorize recommendations.
    """

    longitudinal_context_available: bool
    recent_state: float | None
    long_term_reference_value: float | None
    long_term_reference_start: date | None
    long_term_reference_end: date | None
    prior_significant_change_direction: str
    prior_significant_change_percent: float | None
    prior_change_period_start: date | None
    prior_change_period_end: date | None
    current_vs_long_term_percent: float | None
    maintenance_of_gain: bool
    maintenance_of_decline: bool
    days_since_change: int | None
    horizon_recent_days: int
    horizon_medium_days: int
    horizon_long_days: int
    horizon_medium_value: float | None
    horizon_long_value: float | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "long_term_reference_start",
            "long_term_reference_end",
            "prior_change_period_start",
            "prior_change_period_end",
        ):
            value = payload[key]
            payload[key] = value.isoformat() if value is not None else None
        return payload


@dataclass(frozen=True)
class WeeklyClaimSemantics:
    """What a weekly aggregate may support. Not a trend ClaimEligibility copy.

    summary_value_allowed: describe recorded observations (with coverage).
    summary_comparison_allowed: compare to baseline only if the as-of trend allows it.
    summary_recommendation_support_allowed: follow the as-of trend recommendation gate.
    """

    summary_value_allowed: bool
    summary_comparison_allowed: bool
    summary_recommendation_support_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WeeklyMetricCoverage:
    metric: str
    cadence: str
    aggregation: str
    aggregate_value: float | None
    observation_count: int
    expected_observation_count: int
    missing_count: int
    coverage_ratio: float
    partial_coverage: bool
    latest_valid_observation_date: date | None
    as_of_date_available: bool
    gap_caveat_required: bool
    claim_semantics: WeeklyClaimSemantics

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        latest = payload["latest_valid_observation_date"]
        payload["latest_valid_observation_date"] = latest.isoformat() if latest is not None else None
        payload["claim_semantics"] = self.claim_semantics.to_dict()
        return payload


@dataclass(frozen=True)
class MetricSalience:
    """Product insight-worthiness for one metric. Orthogonal to F4.1 eligibility.

    Does not hide direction. Does not authorize recommendations.
    Thresholds are product salience knobs, not clinical cutoffs.
    """

    salience_level: str
    magnitude_band: str
    insight_candidate: bool
    recommendation_candidate: bool
    corroborating_metrics: tuple[str, ...]
    reasons: tuple[str, ...]
    control_metric: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["corroborating_metrics"] = list(self.corroborating_metrics)
        payload["reasons"] = list(self.reasons)
        return payload


@dataclass(frozen=True)
class InsightSalienceSummary:
    """Review-level surfacing contract. Derived from per-metric salience."""

    insight_worthy: bool
    recommendation_worthy: bool
    primary_metrics: tuple[str, ...]
    corroborating_metrics: tuple[str, ...]
    reasons: tuple[str, ...]
    salience_level: str
    control_metrics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["primary_metrics"] = list(self.primary_metrics)
        payload["corroborating_metrics"] = list(self.corroborating_metrics)
        payload["control_metrics"] = list(self.control_metrics)
        payload["reasons"] = list(self.reasons)
        return payload


@dataclass(frozen=True)
class WeeklySummary:
    week_start: date
    week_end: date
    as_of_aligned: bool
    average_sleep_hours: float | None
    total_exercise_minutes: float | None
    total_workouts: int | None
    average_resting_hr_bpm: float | None
    average_hrv_sdnn_ms: float | None
    average_steps: float | None
    average_respiratory_rate: float | None
    coverage: dict[str, WeeklyMetricCoverage]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["week_start"] = self.week_start.isoformat()
        payload["week_end"] = self.week_end.isoformat()
        payload["coverage"] = {key: value.to_dict() for key, value in self.coverage.items()}
        return payload
