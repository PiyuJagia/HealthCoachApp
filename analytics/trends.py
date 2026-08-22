"""Deterministic trend calculations from longitudinal health data."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from statistics import mean

from sqlalchemy.orm import Session

from analytics.maturity import (
    BASELINE_LOOKBACK_DAYS,
    CADENCE_EPISODIC,
    CURRENT_WINDOW_DAYS,
    LONG_HORIZON_DAYS,
    METRIC_SPECS,
    STABLE_PERCENT_THRESHOLD,
    MetricSpec,
    compute_claim_flags,
    compute_weekly_claim_semantics,
    coverage_ratio,
    expected_current_observations,
    weekly_aggregation,
    weekly_missing_count,
)
from analytics.longitudinal import build_longitudinal_context
from analytics.salience import attach_salience
from analytics.schemas import (
    ClaimEligibility,
    MetricSalience,
    TrendResult,
    WeeklyClaimSemantics,
    WeeklyMetricCoverage,
    WeeklySummary,
)
from analytics.spread import build_within_window_spread
from data.repository import list_health_daily_for_user


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return mean(values)


def _percent_change(current: float, baseline: float) -> float | None:
    if baseline == 0:
        return None
    return ((current - baseline) / baseline) * 100.0


def _direction(current: float | None, baseline: float | None, *, higher_is_improvement: bool) -> str:
    if current is None or baseline is None:
        return "unknown"
    if baseline == 0:
        return "unknown"
    percent = _percent_change(current, baseline)
    if percent is None or abs(percent) < STABLE_PERCENT_THRESHOLD:
        return "stable"
    increased = current > baseline
    if higher_is_improvement:
        return "improving" if increased else "declining"
    return "increasing" if increased else "decreasing"


def _metric_value(record, field_name: str) -> float | None:
    value = getattr(record, field_name)
    if value is None:
        return None
    return float(value)


def _extract_values(records, field_name: str) -> list[float]:
    values: list[float] = []
    for record in records:
        value = _metric_value(record, field_name)
        if value is not None:
            values.append(value)
    return values


def _latest_valid(records, field_name: str, *, as_of_date: date) -> tuple[date | None, float | None]:
    latest_date: date | None = None
    latest_value: float | None = None
    for record in records:
        if record.date > as_of_date:
            continue
        value = _metric_value(record, field_name)
        if value is None:
            continue
        if latest_date is None or record.date > latest_date:
            latest_date = record.date
            latest_value = round(value, 2)
    return latest_date, latest_value


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _build_trend(
    *,
    spec: MetricSpec,
    current_records: Sequence,
    baseline_records: Sequence,
    history_records: Sequence,
    as_of_date: date,
    current_start: date,
    current_end: date,
    baseline_start: date,
    baseline_end: date,
) -> TrendResult:
    field_name = spec.field_name
    current_values = _extract_values(current_records, field_name)
    baseline_values = _extract_values(baseline_records, field_name)
    current_value = _average(current_values)
    baseline_value = _average(baseline_values)
    expected_current = expected_current_observations(spec.cadence)
    as_of_record = next((record for record in current_records if record.date == as_of_date), None)
    as_of_value = _metric_value(as_of_record, field_name) if as_of_record is not None else None
    as_of_available = as_of_value is not None
    latest_date, latest_value = _latest_valid(history_records, field_name, as_of_date=as_of_date)
    flags = compute_claim_flags(
        cadence=spec.cadence,
        current_count=len(current_values),
        baseline_count=len(baseline_values),
        expected_current=expected_current,
        has_any_valid_observation=latest_date is not None,
        as_of_available=as_of_available,
    )
    trend_allowed = bool(flags["trend_allowed"])
    raw_absolute = (
        current_value - baseline_value
        if current_value is not None and baseline_value is not None
        else None
    )
    raw_percent = (
        _percent_change(current_value, baseline_value)
        if current_value is not None and baseline_value is not None
        else None
    )
    raw_direction = _direction(
        current_value,
        baseline_value,
        higher_is_improvement=spec.higher_is_improvement,
    )
    claim = ClaimEligibility(
        snapshot_allowed=bool(flags["snapshot_allowed"]),
        early_pattern_allowed=bool(flags["early_pattern_allowed"]),
        trend_allowed=trend_allowed,
        recommendation_support_allowed=bool(flags["recommendation_support_allowed"]),
        recommendation_basis=str(flags["recommendation_basis"]),
    )
    longitudinal = build_longitudinal_context(
        spec=spec,
        records=history_records,
        as_of_date=as_of_date,
        current_start=current_start,
        current_end=current_end,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        recent_state=_round_or_none(current_value),
        recent_direction=raw_direction if trend_allowed else "unknown",
        trend_allowed=trend_allowed,
    )
    return TrendResult(
        metric=spec.metric,
        cadence=spec.cadence,
        current_value=_round_or_none(current_value),
        baseline_value=_round_or_none(baseline_value),
        absolute_change=_round_or_none(raw_absolute) if trend_allowed else None,
        percent_change=_round_or_none(raw_percent) if trend_allowed else None,
        direction=raw_direction if trend_allowed else "unknown",
        as_of_date_value=_round_or_none(as_of_value),
        as_of_date_available=as_of_available,
        observation_count_current=len(current_values),
        expected_observation_count_current=expected_current,
        coverage_ratio=float(flags["coverage_ratio"]),
        baseline_observation_count=len(baseline_values),
        baseline_ready=bool(flags["baseline_ready"]),
        latest_valid_observation_date=latest_date,
        latest_valid_observation_value=latest_value,
        period_start=current_start,
        period_end=current_end,
        baseline_period_start=baseline_start,
        baseline_period_end=baseline_end,
        partial_coverage=bool(flags["partial_coverage"]),
        gap_caveat_required=bool(flags["gap_caveat_required"]),
        data_maturity_state=str(flags["data_maturity_state"]),
        claim_eligibility=claim,
        longitudinal=longitudinal,
        salience=MetricSalience(
            salience_level="none",
            magnitude_band="none",
            insight_candidate=False,
            recommendation_candidate=False,
            corroborating_metrics=(),
            reasons=(),
            control_metric=spec.control_metric,
        ),
        control_metric=spec.control_metric,
        within_window_spread=build_within_window_spread(
            metric=spec.metric,
            current_values=current_values,
            baseline_values=baseline_values,
            claim=claim,
            baseline_ready=bool(flags["baseline_ready"]),
            partial_coverage=bool(flags["partial_coverage"]),
            gap_caveat_required=bool(flags["gap_caveat_required"]),
        ),
    )


def _window_bounds(as_of_date: date) -> tuple[date, date, date, date]:
    current_end = as_of_date
    current_start = current_end - timedelta(days=CURRENT_WINDOW_DAYS - 1)
    lookback_start = current_end - timedelta(days=BASELINE_LOOKBACK_DAYS - 1)
    baseline_end = current_start - timedelta(days=1)
    baseline_start = lookback_start
    if baseline_start > baseline_end:
        baseline_start = baseline_end
    return current_start, current_end, baseline_start, baseline_end


def get_health_trends(
    session: Session,
    user_id: int,
    *,
    as_of_date: date | None = None,
) -> list[TrendResult]:
    """
    Compare recent-window averages to a valid-day baseline within a 60-day lookback.

    Returns observational trend facts plus claim-eligibility metadata.
    """
    if as_of_date is None:
        records = list_health_daily_for_user(session, user_id)
        if not records:
            raise ValueError(f"No health records found for user_id={user_id}.")
        as_of_date = records[-1].date

    current_start, current_end, baseline_start, baseline_end = _window_bounds(as_of_date)
    history_start = current_end - timedelta(days=LONG_HORIZON_DAYS - 1)
    records = list_health_daily_for_user(
        session,
        user_id,
        start_date=history_start,
        end_date=current_end,
    )
    current_records = [record for record in records if current_start <= record.date <= current_end]
    baseline_records = [record for record in records if baseline_start <= record.date <= baseline_end]
    trends = [
        _build_trend(
            spec=spec,
            current_records=current_records,
            baseline_records=baseline_records,
            history_records=records,
            as_of_date=as_of_date,
            current_start=current_start,
            current_end=current_end,
            baseline_start=baseline_start,
            baseline_end=baseline_end,
        )
        for spec in METRIC_SPECS
    ]
    return attach_salience(trends)


def _week_aggregate(week_records: Sequence, spec: MetricSpec) -> float | None:
    values = _extract_values(week_records, spec.field_name)
    if not values:
        return None
    if weekly_aggregation(spec.metric) == "sum":
        return float(sum(values))
    return mean(values)


def _weekly_coverage(
    week_records: Sequence,
    spec: MetricSpec,
    *,
    week_end: date,
    as_of_aligned: bool,
    trend: TrendResult | None,
) -> WeeklyMetricCoverage:
    values = _extract_values(week_records, spec.field_name)
    expected = expected_current_observations(spec.cadence)
    observed = len(values)
    latest_date, _ = _latest_valid(week_records, spec.field_name, as_of_date=week_end)
    as_of_record = next((record for record in week_records if record.date == week_end), None)
    as_of_available = (
        as_of_record is not None and _metric_value(as_of_record, spec.field_name) is not None
    )
    gap_caveat_required = spec.cadence != CADENCE_EPISODIC and not as_of_available
    flags = compute_weekly_claim_semantics(
        observed_count=observed,
        week_aligns_with_as_of_trend=as_of_aligned,
        trend_allowed=bool(trend.claim_eligibility.trend_allowed) if trend is not None else False,
        recommendation_support_allowed=(
            bool(trend.claim_eligibility.recommendation_support_allowed) if trend is not None else False
        ),
    )
    return WeeklyMetricCoverage(
        metric=spec.metric,
        cadence=spec.cadence,
        aggregation=weekly_aggregation(spec.metric),
        aggregate_value=_round_or_none(_week_aggregate(week_records, spec)),
        observation_count=observed,
        expected_observation_count=expected,
        missing_count=weekly_missing_count(
            cadence=spec.cadence,
            observed_count=observed,
            expected_count=expected,
        ),
        coverage_ratio=coverage_ratio(observed, expected),
        partial_coverage=observed < expected,
        latest_valid_observation_date=latest_date,
        as_of_date_available=as_of_available,
        gap_caveat_required=gap_caveat_required,
        claim_semantics=WeeklyClaimSemantics(
            summary_value_allowed=bool(flags["summary_value_allowed"]),
            summary_comparison_allowed=bool(flags["summary_comparison_allowed"]),
            summary_recommendation_support_allowed=bool(
                flags["summary_recommendation_support_allowed"]
            ),
        ),
    )


def get_weekly_summaries(
    session: Session,
    user_id: int,
    *,
    as_of_date: date | None = None,
    weeks: int = 4,
    trend_results: Sequence[TrendResult] | None = None,
) -> list[WeeklySummary]:
    """Return weekly observed aggregates with coverage and weekly claim semantics.

    A weekly summary describes what was recorded in the week. It is not a trend.
    Comparison and recommendation gates follow the as-of trend contract.
    """
    if weeks < 1:
        raise ValueError("weeks must be at least 1.")

    records = list_health_daily_for_user(session, user_id)
    if not records:
        return []

    if as_of_date is None:
        as_of_date = records[-1].date

    trends = list(trend_results) if trend_results is not None else get_health_trends(
        session, user_id, as_of_date=as_of_date
    )
    trend_by_metric = {trend.metric: trend for trend in trends}

    summaries: list[WeeklySummary] = []
    week_end = as_of_date
    for _ in range(weeks):
        week_start = week_end - timedelta(days=6)
        week_records = [record for record in records if week_start <= record.date <= week_end]
        as_of_aligned = week_end == as_of_date
        coverage = {
            spec.metric: _weekly_coverage(
                week_records,
                spec,
                week_end=week_end,
                as_of_aligned=as_of_aligned,
                trend=trend_by_metric.get(spec.metric) if as_of_aligned else None,
            )
            for spec in METRIC_SPECS
        }
        summaries.append(
            WeeklySummary(
                week_start=week_start,
                week_end=week_end,
                as_of_aligned=as_of_aligned,
                average_sleep_hours=coverage["sleep_duration_hours"].aggregate_value,
                total_exercise_minutes=coverage["exercise_minutes"].aggregate_value,
                total_workouts=(
                    int(coverage["workout_count"].aggregate_value)
                    if coverage["workout_count"].aggregate_value is not None
                    else None
                ),
                average_resting_hr_bpm=coverage["resting_hr_bpm"].aggregate_value,
                average_hrv_sdnn_ms=coverage["hrv_sdnn_ms"].aggregate_value,
                average_steps=coverage["steps"].aggregate_value,
                average_respiratory_rate=coverage["respiratory_rate"].aggregate_value,
                coverage=coverage,
            )
        )
        week_end = week_start - timedelta(days=1)

    summaries.reverse()
    return summaries
