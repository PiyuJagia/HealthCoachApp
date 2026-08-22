"""Targeted post-F4.8 Gemini run for HC-EVAL-E1 then HC-EVAL-B1 only.

Measurement only. Does not update frozen baseline_trace_index or human labels.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from agent.runner import run_health_review
from agent.schemas import parse_agent_json_payload
from data.database import get_session_factory
from data.demo_seed import DEMO_DISPLAY_NAME, seed_demo_health_data
from data.models import User
from evals.baseline_dataset import load_baseline_scenarios

load_dotenv(PROJECT_ROOT / ".env")

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
ARCHIVE_DIR = RESULTS_DIR / "f481_e1_b1_traces"
TARGET_IDS = ("HC-EVAL-E1", "HC-EVAL-B1")
FOCUS_METRICS = (
    "sleep_duration_hours",
    "resting_hr_bpm",
    "hrv_sdnn_ms",
    "exercise_minutes",
    "workout_count",
    "steps",
    "vo2_max",
    "respiratory_rate",
)


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def ensure_demo_user() -> int:
    session_factory = get_session_factory()
    with session_factory() as session:
        user = session.scalar(
            select(User).where(User.display_name == DEMO_DISPLAY_NAME).order_by(User.id.asc())
        )
        if user is not None:
            return int(user.id)
        user = seed_demo_health_data(session, reset=True)
        session.commit()
        return int(user.id)


def _tool_names(payload: dict[str, Any]) -> list[str]:
    return [str(item.get("tool_name") or "") for item in payload.get("tool_calls") or []]


def _first_trend_visibility(payload: dict[str, Any]) -> dict[str, Any]:
    for call in payload.get("model_calls") or []:
        maturity = call.get("trend_maturity_visible")
        salience = call.get("insight_salience_visible")
        results = call.get("tool_results_visible") or []
        trend_result = next(
            (
                item
                for item in results
                if item.get("tool_name") == "get_trend_signals"
            ),
            None,
        )
        if maturity or salience or trend_result:
            return {
                "call_index": call.get("call_index"),
                "capture_fidelity": call.get("capture_fidelity"),
                "origin": (maturity or {}).get("origin"),
                "trend_maturity_visible": maturity,
                "insight_salience_visible": salience,
                "tool_result_origin": None if trend_result is None else trend_result.get("origin"),
            }
    return {}


def _rr_from_signals(payload: dict[str, Any]) -> dict[str, Any] | None:
    signals = payload.get("candidate_signals") or {}
    for item in signals.get("trends") or []:
        if item.get("metric") == "respiratory_rate":
            return item
    return None


def _focus_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    signals = payload.get("candidate_signals") or {}
    rows = []
    for item in signals.get("trends") or []:
        if item.get("metric") not in FOCUS_METRICS:
            continue
        sal = item.get("salience") or {}
        rows.append(
            {
                "metric": item.get("metric"),
                "current_value": item.get("current_value"),
                "baseline_value": item.get("baseline_value"),
                "percent_change": item.get("percent_change"),
                "direction": item.get("direction"),
                "data_maturity_state": item.get("data_maturity_state"),
                "coverage_ratio": item.get("coverage_ratio"),
                "observation_count_current": item.get("observation_count_current"),
                "expected_observation_count_current": item.get("expected_observation_count_current"),
                "control_metric": item.get("control_metric") or sal.get("control_metric"),
                "insight_candidate": sal.get("insight_candidate"),
                "salience_level": sal.get("salience_level"),
                "magnitude_band": sal.get("magnitude_band"),
                "reasons": sal.get("reasons"),
            }
        )
    return rows


def analyze_trace(scenario_id: str, payload: dict[str, Any], raw_text: str | None) -> dict[str, Any]:
    structured = payload.get("structured_result") or {}
    raw_parsed = None
    if raw_text:
        try:
            raw_parsed = parse_agent_json_payload(raw_text)
        except (json.JSONDecodeError, TypeError, ValueError):
            raw_parsed = None
    model_calls = payload.get("model_calls") or []
    salience = (payload.get("candidate_signals") or {}).get("insight_salience") or {}
    rr = _rr_from_signals(payload)
    rr_visible = False
    omitted = 0
    for call in model_calls:
        omitted += int(call.get("omitted_thought_parts") or 0)
        maturity = call.get("trend_maturity_visible") or {}
        for row in maturity.get("metrics") or []:
            if row.get("metric") == "respiratory_rate":
                rr_visible = True
        serialized = json.dumps(call)
        if "respiratory_rate" in serialized:
            rr_visible = True
    return {
        "scenario_id": scenario_id,
        "run_id": payload.get("run_id"),
        "as_of_date": payload.get("as_of_date"),
        "latency_ms": payload.get("latency_ms"),
        "model": payload.get("model"),
        "tool_names": _tool_names(payload),
        "model_call_count": len(model_calls),
        "f42_fidelity": all(
            call.get("capture_fidelity") == "adk_pre_model_request" for call in model_calls
        )
        if model_calls
        else False,
        "omitted_thought_parts": omitted,
        "respiratory_rate_visible_to_llm": rr_visible,
        "trend_visibility": _first_trend_visibility(payload),
        "focus_metrics": _focus_rows(payload),
        "respiratory_rate": None
        if rr is None
        else {
            "current_value": rr.get("current_value"),
            "baseline_value": rr.get("baseline_value"),
            "percent_change": rr.get("percent_change"),
            "direction": rr.get("direction"),
            "data_maturity_state": rr.get("data_maturity_state"),
            "coverage_ratio": rr.get("coverage_ratio"),
            "observation_count_current": rr.get("observation_count_current"),
            "expected_observation_count_current": rr.get("expected_observation_count_current"),
            "control_metric": rr.get("control_metric") or (rr.get("salience") or {}).get("control_metric"),
            "insight_candidate": (rr.get("salience") or {}).get("insight_candidate"),
            "salience_level": (rr.get("salience") or {}).get("salience_level"),
            "reasons": (rr.get("salience") or {}).get("reasons"),
        },
        "insight_salience": salience,
        "activity_log": payload.get("activity_log"),
        "policy": payload.get("policy"),
        "recommendation_boundary": payload.get("recommendation_boundary"),
        "final_guard": payload.get("final_guard"),
        "raw_status": None if raw_parsed is None else raw_parsed.get("status"),
        "raw_theme": None if raw_parsed is None else raw_parsed.get("theme"),
        "raw_insight": None if raw_parsed is None else raw_parsed.get("insight"),
        "raw_recommendation": None if raw_parsed is None else raw_parsed.get("recommendation"),
        "raw_reason_not_surfaced": None if raw_parsed is None else raw_parsed.get("reason_not_surfaced"),
        "final_status": structured.get("status"),
        "final_theme": structured.get("theme"),
        "final_insight": structured.get("insight"),
        "final_recommendation": structured.get("recommendation"),
        "final_reason_not_surfaced": structured.get("reason_not_surfaced"),
        "recommendation_authorized": structured.get("recommendation_authorized"),
        "recommendation_worthy": structured.get("recommendation_worthy"),
        "final_recommendation_allowed": structured.get("final_recommendation_allowed"),
        "confidence_language": structured.get("confidence_language"),
        "source_refs": structured.get("source_refs"),
        "retrieval": payload.get("retrieval"),
    }


def main() -> int:
    _configure_stdout()
    user_id = ensure_demo_user()
    lookup = {item.scenario_id: item for item in load_baseline_scenarios()}
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for scenario_id in TARGET_IDS:
        scenario = lookup[scenario_id]
        print("=" * 72)
        print(f"POST-F4.8 LIVE: {scenario_id} as_of={scenario.as_of_date.isoformat()} user_id={user_id}")
        result = run_health_review(
            scenario_id=scenario.scenario_id,
            user_id=user_id,
            as_of_date=scenario.as_of_date,
        )
        payload = json.loads(result.trace_path.read_text(encoding="utf-8"))
        archived = ARCHIVE_DIR / result.trace_path.name
        shutil.copy2(result.trace_path, archived)
        raw_path = ARCHIVE_DIR / f"{result.trace_path.stem}.raw_model.json"
        raw_parsed = None
        if result.raw_final_text:
            try:
                raw_parsed = parse_agent_json_payload(result.raw_final_text)
            except (json.JSONDecodeError, TypeError, ValueError):
                raw_parsed = None
            raw_path.write_text(
                json.dumps(
                    {"raw_final_text": result.raw_final_text, "parsed": raw_parsed},
                    indent=2,
                ),
                encoding="utf-8",
            )
        current = analyze_trace(scenario_id, payload, result.raw_final_text)
        current["trace_file"] = archived.name
        rows.append(current)
        print(f"status={current['final_status']} raw={current['raw_status']}")
        print(f"rr_visible={current['respiratory_rate_visible_to_llm']} insight_worthy={current['insight_salience'].get('insight_worthy')}")
        print(f"latency_ms={current['latency_ms']} model_calls={current['model_call_count']}")
        print(f"trace={archived}")
    (ARCHIVE_DIR / "analysis.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (ARCHIVE_DIR / "run_manifest.json").write_text(
        json.dumps(
            [
                {
                    "scenario_id": row["scenario_id"],
                    "run_id": row["run_id"],
                    "trace_file": row["trace_file"],
                    "as_of_date": row["as_of_date"],
                    "final_status": row["final_status"],
                    "raw_status": row["raw_status"],
                    "latency_ms": row["latency_ms"],
                    "model_call_count": row["model_call_count"],
                }
                for row in rows
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nArchive: {ARCHIVE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
