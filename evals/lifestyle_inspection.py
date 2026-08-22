"""F4.4 deterministic lifestyle-context inspection for C1/C2/C3 (no Gemini)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from analytics.trends import get_health_trends
from app.lifestyle_tools import DEFAULT_LOOKBACK_DAYS, get_lifestyle_context_for_agent
from rag.relationship_policy import (
    can_generate_recommendation,
    evaluate_relationship_request,
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"
INSPECTION_MD = RESULTS_DIR / "f44_lifestyle_context_v1.md"
INSPECTION_JSON = RESULTS_DIR / "f44_lifestyle_context_v1.json"

SCENARIOS = (
    {
        "scenario_id": "HC-EVAL-C1",
        "as_of_date": "2026-08-02",
        "role": "Sleep decline with caffeine cluster",
    },
    {
        "scenario_id": "HC-EVAL-C2",
        "as_of_date": "2026-07-31",
        "role": "Sleep decline with caffeine and late-work context",
    },
    {
        "scenario_id": "HC-EVAL-C3",
        "as_of_date": "2026-06-29",
        "role": "Caffeine present while sleep remains reasonable",
    },
)

POLICY_INPUT_MAP_DOC = (
    "caffeine + unit mg → caffeine_mg (gates R-07); "
    "alcohol + unit standard_drinks → alcohol_units (gates R-08). "
    "mood / late-work notes do not map to a policy input. "
    "cycle_phase is not present in lifestyle_events."
)


def _events_of_type(payload: dict[str, Any], event_type: str) -> list[dict[str, Any]]:
    return [event for event in payload.get("events") or [] if event.get("event_type") == event_type]


def _relationship_preview(available_inputs: list[str]) -> dict[str, Any]:
    input_set = set(available_inputs)
    preview = {}
    for relationship_id in ("R-07", "R-08", "R-09"):
        outcome = evaluate_relationship_request(relationship_id, available_inputs=input_set)
        preview[relationship_id] = {
            "evaluation_outcome_if_retrieved": outcome.value,
            "input_available": (
                (relationship_id == "R-07" and "caffeine_mg" in input_set)
                or (relationship_id == "R-08" and "alcohol_units" in input_set)
                or (relationship_id == "R-09" and "cycle_phase" in input_set)
            ),
            "recommendation_authorized_if_retrieved": (
                outcome.value == "relationship_detected" and can_generate_recommendation(relationship_id)
            ),
        }
    return preview


def inspect_lifestyle_scenario(session, user_id: int, spec: dict[str, str]) -> dict[str, Any]:
    as_of = date.fromisoformat(spec["as_of_date"])
    payload = get_lifestyle_context_for_agent(
        user_id, as_of_date=as_of, lookback_days=DEFAULT_LOOKBACK_DAYS
    )
    trends = {
        item.metric: item for item in get_health_trends(session, user_id, as_of_date=as_of)
    }
    sleep = trends.get("sleep_duration_hours")
    caffeine = _events_of_type(payload, "caffeine")
    alcohol = _events_of_type(payload, "alcohol")
    mood = _events_of_type(payload, "mood")
    late_work_notes = [
        event for event in mood if event.get("notes") and "late work" in str(event["notes"]).lower()
    ]
    forbidden_narrative_keys = {
        "cause",
        "causal",
        "relevance_score",
        "problem",
        "recommendation_authorized",
        "ranked_factors",
    }
    return {
        "scenario_id": spec["scenario_id"],
        "role": spec["role"],
        "as_of_date": spec["as_of_date"],
        "lookback_days": payload["lookback_days"],
        "window_start": payload["window_start"],
        "window_end": payload["window_end"],
        "event_count": payload["event_count"],
        "by_type": payload["by_type"],
        "events": payload["events"],
        "caffeine_count": len(caffeine),
        "caffeine_hours": [event["hour"] for event in caffeine],
        "caffeine_quantities": [event["quantity"] for event in caffeine],
        "caffeine_units": [event["unit"] for event in caffeine],
        "alcohol_count": len(alcohol),
        "mood_count": len(mood),
        "late_work_context_event_count": payload["late_work_context_event_count"],
        "late_work_notes_preserved": bool(late_work_notes),
        "policy_available_inputs": payload["policy_available_inputs"],
        "relationship_preview_if_retrieved": _relationship_preview(payload["policy_available_inputs"]),
        "sleep_direction": sleep.direction if sleep else None,
        "sleep_percent_change": sleep.percent_change if sleep else None,
        "sleep_trend_allowed": sleep.claim_eligibility.trend_allowed if sleep else None,
        "manufactures_problem": bool(forbidden_narrative_keys.intersection(payload.keys())),
        "disclaimer": payload["disclaimer"],
    }


def inspect_c1_c2_c3(session, user_id: int) -> dict[str, Any]:
    scenarios = [inspect_lifestyle_scenario(session, user_id, spec) for spec in SCENARIOS]
    by_id = {item["scenario_id"]: item for item in scenarios}
    c1 = by_id["HC-EVAL-C1"]
    c2 = by_id["HC-EVAL-C2"]
    c3 = by_id["HC-EVAL-C3"]
    return {
        "lookback_days_default": DEFAULT_LOOKBACK_DAYS,
        "policy_input_mapping": POLICY_INPUT_MAP_DOC,
        "scenarios": scenarios,
        "controls": {
            "c1_caffeine_present_for_investigation": c1["caffeine_count"] > 0,
            "c2_multiple_cooccurring_factors": (
                c2["caffeine_count"] > 0 and c2["late_work_context_event_count"] > 0
            ),
            "c3_caffeine_with_stable_sleep": (
                c3["caffeine_count"] > 0 and c3["sleep_direction"] in {"stable", None}
            ),
            "c3_does_not_manufacture_caffeine_problem": not c3["manufactures_problem"],
            "no_causal_scoring": all(not item["manufactures_problem"] for item in scenarios),
        },
    }


def write_lifestyle_inspection_artifacts(report: dict[str, Any]) -> dict[str, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    INSPECTION_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# F4.4 Lifestyle context inspection (C1 / C2 / C3)",
        "",
        "Deterministic inspection of `get_lifestyle_context`. No Gemini. No causal scoring.",
        "",
        f"**Default lookback:** {report['lookback_days_default']} days inclusive of as-of date.",
        "",
        f"**Policy input mapping:** {report['policy_input_mapping']}",
        "",
        "Lifestyle context is user-specific observational context. It is not scientific evidence.",
        "Association claims still require retrieve_authorized_evidence and evidence policy.",
        "",
    ]
    for item in report["scenarios"]:
        lines.extend(
            [
                f"## {item['scenario_id']} — {item['as_of_date']}",
                "",
                item["role"],
                "",
                f"- Window: {item['window_start']} → {item['window_end']} ({item['lookback_days']} days)",
                f"- Event count: {item['event_count']}",
                f"- Caffeine: n={item['caffeine_count']} hours={item['caffeine_hours']} qty={item['caffeine_quantities']} units={item['caffeine_units']}",
                f"- Alcohol: n={item['alcohol_count']}",
                f"- Mood events: n={item['mood_count']}; late-work notes={item['late_work_context_event_count']}",
                f"- Sleep trend (analytics, not lifestyle): direction={item['sleep_direction']} pct={item['sleep_percent_change']}",
                f"- policy_available_inputs: {item['policy_available_inputs']}",
                f"- R-07 if retrieved: {item['relationship_preview_if_retrieved']['R-07']}",
                f"- R-08 if retrieved: {item['relationship_preview_if_retrieved']['R-08']}",
                "",
                "Events:",
                "",
            ]
        )
        for event in item["events"]:
            lines.append(
                f"- {event['occurred_at']} {event['event_type']} "
                f"qty={event['quantity']} {event['unit']} notes={event['notes']}"
            )
        lines.append("")
    controls = report["controls"]
    lines.extend(
        [
            "## Negative / cherry-pick controls",
            "",
            f"- C1 caffeine present for investigation: {controls['c1_caffeine_present_for_investigation']}",
            f"- C2 multiple co-occurring factors: {controls['c2_multiple_cooccurring_factors']}",
            f"- C3 caffeine with stable sleep: {controls['c3_caffeine_with_stable_sleep']}",
            f"- C3 does not manufacture a caffeine problem: {controls['c3_does_not_manufacture_caffeine_problem']}",
            f"- No causal scoring in tool payload: {controls['no_causal_scoring']}",
            "",
        ]
    )
    INSPECTION_MD.write_text("\n".join(lines), encoding="utf-8")
    return {"md": INSPECTION_MD, "json": INSPECTION_JSON}
