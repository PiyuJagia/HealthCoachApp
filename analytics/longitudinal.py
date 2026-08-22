"""Compact multi-horizon longitudinal context (F4.5).

Recent 7-vs-60 trends answer "what changed lately?"
This module answers whether that recent state is still different from an
older personal reference that the 7-vs-60 window never sees.

Thresholds are MVP product knobs, not physiological truths.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from statistics import mean
from typing import Any

from analytics.maturity import (
    CURRENT_WINDOW_DAYS,
    LONG_HORIZON_DAYS,
    LONGITUDINAL_MATERIAL_PERCENT,
    MEDIUM_HORIZON_DAYS,
    MIN_LONGITUDINAL_REFERENCE_OBS,
    MetricSpec,
)
from analytics.schemas import LongitudinalContext

REASON_AVAILABLE = "older_reference_outside_recent_baseline"
REASON_NO_OLDER_HISTORY = "no_history_older_than_recent_baseline"
REASON_INSUFFICIENT_REFERENCE = "insufficient_long_term_reference_observations"
REASON_TREND_NOT_ALLOWED = "recent_trend_not_allowed"

HIGHER_IS_BETTER: dict[str, bool] = {
    "sleep_duration_hours": True,
    "resting_hr_bpm": False,
    "hrv_sdnn_ms": True,
    "exercise_minutes": True,
    "workout_count": True,
    "steps": True,
    "vo2_max": True,
}


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _percent_change(current: float, baseline: float) -> float | None:
    if baseline == 0:
        return None
    return ((current - baseline) / baseline) * 100.0


def _metric_value(record: Any, field_name: str) -> float | None:
    value = getattr(record, field_name)
    if value is None:
        return None
    return float(value)


def _average_in_range(
    records: Sequence,
    field_name: str,
    start: date,
    end: date,
) -> tuple[float | None, int]:
    values = [
        value
        for record in records
        if start <= record.date <= end
        for value in (_metric_value(record, field_name),)
        if value is not None
    ]
    if not values:
        return None, 0
    return mean(values), len(values)


def _is_materially_better(
    current: float | None,
    reference: float | None,
    *,
    higher_is_better: bool,
    threshold: float = LONGITUDINAL_MATERIAL_PERCENT,
) -> bool:
    if current is None or reference is None or reference == 0:
        return False
    percent = _percent_change(current, reference)
    if percent is None:
        return False
    if higher_is_better:
        return percent >= threshold
    return percent <= -threshold


def _is_materially_worse(
    current: float | None,
    reference: float | None,
    *,
    higher_is_better: bool,
    threshold: float = LONGITUDINAL_MATERIAL_PERCENT,
) -> bool:
    if current is None or reference is None or reference == 0:
        return False
    percent = _percent_change(current, reference)
    if percent is None:
        return False
    if higher_is_better:
        return percent <= -threshold
    return percent >= threshold


def _unavailable(
    *,
    reason: str,
    recent_state: float | None,
    medium_value: float | None = None,
    long_value: float | None = None,
) -> LongitudinalContext:
    return LongitudinalContext(
        longitudinal_context_available=False,
        recent_state=_round_or_none(recent_state),
        long_term_reference_value=None,
        long_term_reference_start=None,
        long_term_reference_end=None,
        prior_significant_change_direction="none",
        prior_significant_change_percent=None,
        prior_change_period_start=None,
        prior_change_period_end=None,
        current_vs_long_term_percent=None,
        maintenance_of_gain=False,
        maintenance_of_decline=False,
        days_since_change=None,
        horizon_recent_days=CURRENT_WINDOW_DAYS,
        horizon_medium_days=MEDIUM_HORIZON_DAYS,
        horizon_long_days=LONG_HORIZON_DAYS,
        horizon_medium_value=_round_or_none(medium_value),
        horizon_long_value=_round_or_none(long_value),
        reason=reason,
    )


def build_longitudinal_context(
    *,
    spec: MetricSpec,
    records: Sequence,
    as_of_date: date,
    current_start: date,
    current_end: date,
    baseline_start: date,
    baseline_end: date,
    recent_state: float | None,
    recent_direction: str,
    trend_allowed: bool,
) -> LongitudinalContext:
    """Compare the current 7-day state to history older than the F4.1 baseline."""
    field_name = spec.field_name
    higher_is_better = HIGHER_IS_BETTER.get(spec.metric, spec.higher_is_improvement)
    medium_start = as_of_date - timedelta(days=MEDIUM_HORIZON_DAYS - 1)
    long_start = as_of_date - timedelta(days=LONG_HORIZON_DAYS - 1)
    medium_value, _ = _average_in_range(records, field_name, medium_start, as_of_date)
    long_value, _ = _average_in_range(records, field_name, long_start, as_of_date)

    dated = [record for record in records if record.date <= as_of_date]
    if not dated:
        return _unavailable(reason=REASON_NO_OLDER_HISTORY, recent_state=recent_state)

    first_date = min(record.date for record in dated)
    effective_baseline_start = max(baseline_start, first_date)
    prefix_end = effective_baseline_start - timedelta(days=1)
    if prefix_end < first_date:
        return _unavailable(
            reason=REASON_NO_OLDER_HISTORY,
            recent_state=recent_state,
            medium_value=medium_value,
            long_value=long_value,
        )

    reference_value, reference_count = _average_in_range(
        dated, field_name, first_date, prefix_end
    )
    if reference_value is None or reference_count < MIN_LONGITUDINAL_REFERENCE_OBS:
        return _unavailable(
            reason=REASON_INSUFFICIENT_REFERENCE,
            recent_state=recent_state,
            medium_value=medium_value,
            long_value=long_value,
        )

    baseline_value, _ = _average_in_range(
        dated, field_name, effective_baseline_start, baseline_end
    )
    current_vs_long = (
        _percent_change(recent_state, reference_value)
        if recent_state is not None
        else None
    )
    prior_vs_long = (
        _percent_change(baseline_value, reference_value)
        if baseline_value is not None
        else None
    )
    prior_gain = _is_materially_better(
        baseline_value, reference_value, higher_is_better=higher_is_better
    )
    prior_decline = _is_materially_worse(
        baseline_value, reference_value, higher_is_better=higher_is_better
    )
    if prior_gain:
        prior_direction = "improving"
    elif prior_decline:
        prior_direction = "declining"
    else:
        prior_direction = "none"

    current_gain = _is_materially_better(
        recent_state, reference_value, higher_is_better=higher_is_better
    )
    current_decline = _is_materially_worse(
        recent_state, reference_value, higher_is_better=higher_is_better
    )
    recent_stable = recent_direction == "stable"
    available = True
    reason = REASON_AVAILABLE
    if spec.control_metric or not trend_allowed:
        reason = REASON_TREND_NOT_ALLOWED if not trend_allowed else REASON_AVAILABLE
        maintenance_gain = False
        maintenance_decline = False
    else:
        maintenance_gain = (
            recent_stable and current_gain and prior_gain
        )
        maintenance_decline = (
            recent_stable and current_decline and prior_decline
        )

    return LongitudinalContext(
        longitudinal_context_available=available,
        recent_state=_round_or_none(recent_state),
        long_term_reference_value=_round_or_none(reference_value),
        long_term_reference_start=first_date,
        long_term_reference_end=prefix_end,
        prior_significant_change_direction=prior_direction,
        prior_significant_change_percent=_round_or_none(prior_vs_long),
        prior_change_period_start=effective_baseline_start,
        prior_change_period_end=baseline_end,
        current_vs_long_term_percent=_round_or_none(current_vs_long),
        maintenance_of_gain=maintenance_gain,
        maintenance_of_decline=maintenance_decline,
        days_since_change=(as_of_date - prefix_end).days,
        horizon_recent_days=CURRENT_WINDOW_DAYS,
        horizon_medium_days=MEDIUM_HORIZON_DAYS,
        horizon_long_days=LONG_HORIZON_DAYS,
        horizon_medium_value=_round_or_none(medium_value),
        horizon_long_value=_round_or_none(long_value),
        reason=reason,
    )


def summarize_longitudinal(trends: Sequence) -> dict[str, Any]:
    maintaining = [
        trend.metric
        for trend in trends
        if getattr(trend, "longitudinal", None) is not None and trend.longitudinal.maintenance_of_gain
    ]
    declining = [
        trend.metric
        for trend in trends
        if getattr(trend, "longitudinal", None) is not None and trend.longitudinal.maintenance_of_decline
    ]
    return {
        "any_maintenance_of_gain": bool(maintaining),
        "any_maintenance_of_decline": bool(declining),
        "metrics_maintaining_gains": maintaining,
        "metrics_maintaining_decline": declining,
        "longitudinal_context_available": any(
            trend.longitudinal.longitudinal_context_available
            for trend in trends
            if getattr(trend, "longitudinal", None) is not None
        ),
    }
