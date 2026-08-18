"""Deterministic trend calculations from longitudinal health data."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from statistics import mean

from sqlalchemy.orm import Session

from analytics.schemas import TrendResult, WeeklySummary
from data.repository import list_health_daily_for_user

CURRENT_WINDOW_DAYS = 7
BASELINE_WINDOW_DAYS = 30
MIN_CURRENT_OBSERVATIONS = 4
MIN_BASELINE_OBSERVATIONS = 15
STABLE_PERCENT_THRESHOLD = 3.0


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


def _extract_values(records, accessor: Callable) -> list[float]:
    values: list[float] = []
    for record in records:
        value = accessor(record)
        if value is not None:
            values.append(float(value))
    return values


def _build_trend(
    *,
    metric: str,
    current_records,
    baseline_records,
    accessor: Callable,
    higher_is_improvement: bool,
    current_start: date,
    current_end: date,
    baseline_start: date,
    baseline_end: date,
) -> TrendResult:
    current_values = _extract_values(current_records, accessor)
    baseline_values = _extract_values(baseline_records, accessor)
    current_value = _average(current_values)
    baseline_value = _average(baseline_values)
    absolute_change = (
        current_value - baseline_value
        if current_value is not None and baseline_value is not None
        else None
    )
    percent_change = (
        _percent_change(current_value, baseline_value)
        if current_value is not None and baseline_value is not None
        else None
    )
    data_sufficient = (
        len(current_values) >= MIN_CURRENT_OBSERVATIONS
        and len(baseline_values) >= MIN_BASELINE_OBSERVATIONS
        and current_value is not None
        and baseline_value is not None
    )
    return TrendResult(
        metric=metric,
        current_value=round(current_value, 2) if current_value is not None else None,
        baseline_value=round(baseline_value, 2) if baseline_value is not None else None,
        absolute_change=round(absolute_change, 2) if absolute_change is not None else None,
        percent_change=round(percent_change, 2) if percent_change is not None else None,
        direction=_direction(current_value, baseline_value, higher_is_improvement=higher_is_improvement),
        observation_count_current=len(current_values),
        observation_count_baseline=len(baseline_values),
        data_sufficient=data_sufficient,
        period_start=current_start,
        period_end=current_end,
        baseline_period_start=baseline_start,
        baseline_period_end=baseline_end,
    )


def get_health_trends(
    session: Session,
    user_id: int,
    *,
    as_of_date: date | None = None,
) -> list[TrendResult]:
    """
    Compare recent 7-day averages to the prior 30-day baseline window.

    Returns observational trend facts only — no causal interpretation.
    """
    if as_of_date is None:
        records = list_health_daily_for_user(session, user_id)
        if not records:
            raise ValueError(f"No health records found for user_id={user_id}.")
        as_of_date = records[-1].date

    current_end = as_of_date
    current_start = current_end - timedelta(days=CURRENT_WINDOW_DAYS - 1)
    baseline_end = current_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=BASELINE_WINDOW_DAYS - 1)

    history_start = baseline_start
    records = list_health_daily_for_user(
        session,
        user_id,
        start_date=history_start,
        end_date=current_end,
    )
    current_records = [record for record in records if current_start <= record.date <= current_end]
    baseline_records = [record for record in records if baseline_start <= record.date <= baseline_end]

    metric_specs = [
        ("sleep_duration_hours", lambda r: r.sleep_duration_hours, False),
        ("resting_hr_bpm", lambda r: r.resting_hr_bpm, False),
        ("hrv_sdnn_ms", lambda r: r.hrv_sdnn_ms, True),
        ("exercise_minutes", lambda r: r.exercise_minutes, True),
        ("workout_count", lambda r: r.workout_count, True),
        ("steps", lambda r: r.steps, True),
        ("vo2_max", lambda r: r.vo2_max, True),
    ]

    return [
        _build_trend(
            metric=metric,
            current_records=current_records,
            baseline_records=baseline_records,
            accessor=accessor,
            higher_is_improvement=higher_is_improvement,
            current_start=current_start,
            current_end=current_end,
            baseline_start=baseline_start,
            baseline_end=baseline_end,
        )
        for metric, accessor, higher_is_improvement in metric_specs
    ]


def get_weekly_summaries(
    session: Session,
    user_id: int,
    *,
    as_of_date: date | None = None,
    weeks: int = 4,
) -> list[WeeklySummary]:
    """Return deterministic weekly aggregates for recent complete weeks."""
    if weeks < 1:
        raise ValueError("weeks must be at least 1.")

    records = list_health_daily_for_user(session, user_id)
    if not records:
        return []

    if as_of_date is None:
        as_of_date = records[-1].date

    summaries: list[WeeklySummary] = []
    week_end = as_of_date
    for _ in range(weeks):
        week_start = week_end - timedelta(days=6)
        week_records = [record for record in records if week_start <= record.date <= week_end]
        if week_records:
            summaries.append(
                WeeklySummary(
                    week_start=week_start,
                    week_end=week_end,
                    average_sleep_hours=_average(
                        _extract_values(week_records, lambda r: r.sleep_duration_hours)
                    ),
                    total_exercise_minutes=sum(
                        value
                        for value in _extract_values(week_records, lambda r: r.exercise_minutes)
                    )
                    or None,
                    total_workouts=int(
                        sum(value for value in _extract_values(week_records, lambda r: r.workout_count))
                    )
                    if _extract_values(week_records, lambda r: r.workout_count)
                    else None,
                    average_resting_hr_bpm=_average(
                        _extract_values(week_records, lambda r: r.resting_hr_bpm)
                    ),
                    average_hrv_sdnn_ms=_average(
                        _extract_values(week_records, lambda r: r.hrv_sdnn_ms)
                    ),
                    average_steps=_average(_extract_values(week_records, lambda r: r.steps)),
                )
            )
        week_end = week_start - timedelta(days=1)

    summaries.reverse()
    return summaries
