"""Structured analytics outputs — observational, not causal."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class TrendResult:
    metric: str
    current_value: float | None
    baseline_value: float | None
    absolute_change: float | None
    percent_change: float | None
    direction: str
    observation_count_current: int
    observation_count_baseline: int
    data_sufficient: bool
    period_start: date
    period_end: date
    baseline_period_start: date
    baseline_period_end: date

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "period_start",
            "period_end",
            "baseline_period_start",
            "baseline_period_end",
        ):
            payload[key] = payload[key].isoformat()
        return payload


@dataclass(frozen=True)
class WeeklySummary:
    week_start: date
    week_end: date
    average_sleep_hours: float | None
    total_exercise_minutes: float | None
    total_workouts: int | None
    average_resting_hr_bpm: float | None
    average_hrv_sdnn_ms: float | None
    average_steps: float | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["week_start"] = self.week_start.isoformat()
        payload["week_end"] = self.week_end.isoformat()
        return payload
