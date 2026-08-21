"""Assignment 4 Phase F1 baseline scenario manifest helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from analytics.trends import get_health_trends
from data.database import get_session_factory
from data.demo_seed import DEMO_END_DATE, demo_start_date
from data.repository import list_health_daily_for_user, list_lifestyle_events_for_user

BASELINE_DATASET_VERSION = "healthcoach_trace_baseline_v1"
DATASET_PATH = Path(__file__).resolve().parent / "datasets" / f"{BASELINE_DATASET_VERSION}.jsonl"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
TRACE_INDEX_PATH = RESULTS_DIR / "baseline_trace_index_v1.csv"
METADATA_PATH = RESULTS_DIR / "baseline_metadata_v1.json"

MANUAL_REVIEW_FIELDS = (
    "human_open_coding_notes",
    "human_pass_fail",
    "human_failure_label",
)

REQUIRED_SCENARIO_FIELDS = (
    "scenario_id",
    "family",
    "name",
    "user_id",
    "as_of_date",
    "scenario_description",
    "data_condition",
    "expected_high_level_behavior",
    "must_do",
    "must_not_do",
    *MANUAL_REVIEW_FIELDS,
)

TRACE_INDEX_COLUMNS = (
    "scenario_id",
    "family",
    "as_of_date",
    "trace_file",
    "run_id",
    "run_status",
    "tool_call_count",
    "evidence_tool_called",
    "policy_verdict",
    "recommendation_authorized",
    "final_status",
    "final_guard_passed",
    "latency_ms",
    *MANUAL_REVIEW_FIELDS,
)

PRODUCT_TRACE_STATUSES = frozenset(
    {
        "INSIGHT",
        "RECOMMENDATION",
        "NO_SIGNIFICANT_NEW_PATTERN",
        "BOUNDED_FAILURE",
        "GUARD_BLOCKED",
    }
)

PROVIDER_FAILURE_STATUSES = frozenset(
    {
        "TEMPORARY_MODEL_UNAVAILABLE",
        "MODEL_QUOTA_EXHAUSTED",
    }
)

COMPLETED_RUN_STATUS = "COMPLETED_PRODUCT_TRACE"
PROVIDER_FAILURE_RUN_STATUS = "PROVIDER_FAILURE"
ERROR_RUN_STATUS = "ERROR"


@dataclass(frozen=True)
class BaselineScenario:
    scenario_id: str
    family: str
    name: str
    user_id: int
    as_of_date: date
    scenario_description: str
    data_condition: str
    expected_high_level_behavior: str
    must_do: tuple[str, ...]
    must_not_do: tuple[str, ...]
    human_open_coding_notes: str = ""
    human_pass_fail: str = ""
    human_failure_label: str = ""
    data_support_status: str = "verified"
    primary_metrics: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BaselineScenario:
        return cls(
            scenario_id=str(payload["scenario_id"]),
            family=str(payload["family"]),
            name=str(payload["name"]),
            user_id=int(payload["user_id"]),
            as_of_date=date.fromisoformat(str(payload["as_of_date"])),
            scenario_description=str(payload["scenario_description"]),
            data_condition=str(payload["data_condition"]),
            expected_high_level_behavior=str(payload["expected_high_level_behavior"]),
            must_do=tuple(str(item) for item in payload["must_do"]),
            must_not_do=tuple(str(item) for item in payload["must_not_do"]),
            human_open_coding_notes=str(payload.get("human_open_coding_notes", "")),
            human_pass_fail=str(payload.get("human_pass_fail", "")),
            human_failure_label=str(payload.get("human_failure_label", "")),
            data_support_status=str(payload.get("data_support_status", "verified")),
            primary_metrics=tuple(str(item) for item in payload.get("primary_metrics", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "family": self.family,
            "name": self.name,
            "user_id": self.user_id,
            "as_of_date": self.as_of_date.isoformat(),
            "scenario_description": self.scenario_description,
            "data_condition": self.data_condition,
            "expected_high_level_behavior": self.expected_high_level_behavior,
            "must_do": list(self.must_do),
            "must_not_do": list(self.must_not_do),
            "human_open_coding_notes": self.human_open_coding_notes,
            "human_pass_fail": self.human_pass_fail,
            "human_failure_label": self.human_failure_label,
            "data_support_status": self.data_support_status,
            "primary_metrics": list(self.primary_metrics),
        }


def load_baseline_scenarios(path: Path | None = None) -> list[BaselineScenario]:
    dataset_path = path or DATASET_PATH
    scenarios: list[BaselineScenario] = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        scenarios.append(BaselineScenario.from_dict(json.loads(stripped)))
    return scenarios


def validate_baseline_manifest(scenarios: list[BaselineScenario] | None = None) -> None:
    items = scenarios if scenarios is not None else load_baseline_scenarios()
    if len(items) != 15:
        raise ValueError(f"Expected exactly 15 baseline scenarios; found {len(items)}.")

    seen_ids: set[str] = set()
    start = demo_start_date()
    end = DEMO_END_DATE
    for item in items:
        if item.scenario_id in seen_ids:
            raise ValueError(f"Duplicate scenario_id: {item.scenario_id}")
        seen_ids.add(item.scenario_id)

        missing = [field for field in REQUIRED_SCENARIO_FIELDS if not hasattr(item, field)]
        if missing:
            raise ValueError(f"Scenario {item.scenario_id} missing fields: {missing}")

        for field in MANUAL_REVIEW_FIELDS:
            if getattr(item, field):
                raise ValueError(
                    f"Scenario {item.scenario_id} must keep {field} blank before manual review."
                )

        if not (start <= item.as_of_date <= end):
            raise ValueError(
                f"Scenario {item.scenario_id} date {item.as_of_date} outside Marcus window "
                f"{start}..{end}."
            )


def inspect_scenario_data_support(scenario: BaselineScenario) -> dict[str, Any]:
    """Deterministic data verification for one baseline scenario."""
    session_factory = get_session_factory()
    with session_factory() as session:
        trends = {
            trend.metric: trend
            for trend in get_health_trends(session, scenario.user_id, as_of_date=scenario.as_of_date)
        }
        daily = list_health_daily_for_user(
            session,
            scenario.user_id,
            start_date=scenario.as_of_date,
            end_date=scenario.as_of_date,
        )
        day_record = daily[0] if daily else None
        events = list_lifestyle_events_for_user(
            session,
            scenario.user_id,
            start_at=datetime.combine(scenario.as_of_date, datetime.min.time()),
            end_at=datetime.combine(
                scenario.as_of_date.replace(day=scenario.as_of_date.day),
                datetime.max.time(),
            ),
        )
        week_start = scenario.as_of_date.fromordinal(scenario.as_of_date.toordinal() - 6)
        week_events = list_lifestyle_events_for_user(
            session,
            scenario.user_id,
            start_at=datetime.combine(week_start, datetime.min.time()),
            end_at=datetime.combine(scenario.as_of_date, datetime.max.time()),
        )

    metric_rows: dict[str, Any] = {}
    for metric_name in scenario.primary_metrics or trends.keys():
        trend = trends.get(metric_name)
        if trend is None:
            continue
        metric_rows[metric_name] = {
            "current_value": trend.current_value,
            "baseline_value": trend.baseline_value,
            "direction": trend.direction,
            "percent_change": trend.percent_change,
            "data_sufficient": trend.data_sufficient,
            "observation_count_current": trend.observation_count_current,
            "observation_count_baseline": trend.observation_count_baseline,
        }

    null_on_date: list[str] = []
    if day_record is not None:
        for field_name in (
            "sleep_duration_hours",
            "resting_hr_bpm",
            "hrv_sdnn_ms",
            "exercise_minutes",
            "vo2_max",
            "respiratory_rate",
            "steps",
        ):
            if getattr(day_record, field_name) is None:
                null_on_date.append(field_name)

    lifestyle_summary: dict[str, int] = {}
    for event in week_events:
        lifestyle_summary[event.event_type] = lifestyle_summary.get(event.event_type, 0) + 1

    same_day_events = [
        {
            "event_type": event.event_type,
            "notes": event.notes,
            "quantity": event.quantity,
            "unit": event.unit,
        }
        for event in events
    ]

    return {
        "scenario_id": scenario.scenario_id,
        "as_of_date": scenario.as_of_date.isoformat(),
        "data_support_status": scenario.data_support_status,
        "metrics": metric_rows,
        "null_on_date": null_on_date,
        "same_day_lifestyle_events": same_day_events,
        "lifestyle_event_counts_on_date": lifestyle_summary,
    }


def classify_run_status(final_status: str) -> str:
    if final_status in PRODUCT_TRACE_STATUSES:
        return COMPLETED_RUN_STATUS
    if final_status in PROVIDER_FAILURE_STATUSES:
        return PROVIDER_FAILURE_RUN_STATUS
    return ERROR_RUN_STATUS
