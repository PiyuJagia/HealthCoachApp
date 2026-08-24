"""Targeted F5.2 live Gemini measurement: A1/B1/B3/C2/E1/C4 only.

Measurement only. Does not change product code, prompts, frozen labels, or taxonomy.
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
ARCHIVE_DIR = RESULTS_DIR / "f52_targeted_live_traces"
TARGET_IDS = (
    "HC-EVAL-A1",
    "HC-EVAL-B1",
    "HC-EVAL-B3",
    "HC-EVAL-C2",
    "HC-EVAL-E1",
    "HC-EVAL-C4",
)
COPY_FIELDS = (
    "status",
    "primary_message",
    "subtext",
    "motivational_quote",
    "insight",
    "recommendation",
    "reason_not_surfaced",
    "theme",
    "recommendation_authorized",
    "recommendation_worthy",
    "final_recommendation_allowed",
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


def _parse_raw(raw_text: str | None) -> dict[str, Any] | None:
    if not raw_text:
        return None
    try:
        return parse_agent_json_payload(raw_text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def analyze_trace(scenario_id: str, payload: dict[str, Any], raw_text: str | None) -> dict[str, Any]:
    structured = payload.get("structured_result") or {}
    raw = _parse_raw(raw_text) or payload.get("raw_model_output") or {}
    model_calls = payload.get("model_calls") or []
    omitted = sum(int(call.get("omitted_thought_parts") or 0) for call in model_calls)
    f42 = bool(model_calls) and all(
        call.get("capture_fidelity") == "adk_pre_model_request" for call in model_calls
    )
    signals = payload.get("candidate_signals") or {}
    output_contract = payload.get("output_contract") or {}
    boundary = payload.get("recommendation_boundary") or {}
    guard = payload.get("final_guard") or {}
    raw_slice = {field: raw.get(field) for field in COPY_FIELDS}
    final_slice = {field: structured.get(field) for field in COPY_FIELDS}
    return {
        "scenario_id": scenario_id,
        "run_id": payload.get("run_id"),
        "as_of_date": payload.get("as_of_date"),
        "latency_ms": payload.get("latency_ms"),
        "model": payload.get("model"),
        "tool_names": [str(item.get("tool_name") or "") for item in payload.get("tool_calls") or []],
        "model_call_count": len(model_calls),
        "f42_fidelity": f42,
        "omitted_thought_parts": omitted,
        "insight_salience": signals.get("insight_salience"),
        "supporting_metric_facts": structured.get("supporting_metric_facts") or [],
        "output_contract": output_contract,
        "recommendation_boundary": boundary,
        "final_guard": guard,
        "raw": raw_slice,
        "final": final_slice,
        "raw_model_facts": raw.get("supporting_metric_facts"),
        "confidence_language": structured.get("confidence_language"),
        "source_refs": structured.get("source_refs"),
        "activity_log": payload.get("activity_log"),
        "policy": payload.get("policy"),
        "has_raw_model_output": payload.get("raw_model_output") is not None,
        "has_output_contract": bool(output_contract),
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
        print(f"F5.2 LIVE: {scenario_id} as_of={scenario.as_of_date.isoformat()} user_id={user_id}")
        result = run_health_review(
            scenario_id=scenario.scenario_id,
            user_id=user_id,
            as_of_date=scenario.as_of_date,
        )
        payload = json.loads(result.trace_path.read_text(encoding="utf-8"))
        archived = ARCHIVE_DIR / result.trace_path.name
        shutil.copy2(result.trace_path, archived)
        raw_parsed = _parse_raw(result.raw_final_text)
        raw_path = ARCHIVE_DIR / f"{result.trace_path.stem}.raw_model.json"
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
        final = current["final"]
        print(f"status raw={current['raw']['status']} final={final['status']}")
        print(f"primary={final.get('primary_message')!r}")
        print(f"quote={final.get('motivational_quote')!r}")
        print(f"guard={current['final_guard']} latency_ms={current['latency_ms']}")
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
                    "final_status": row["final"]["status"],
                    "raw_status": row["raw"]["status"],
                    "latency_ms": row["latency_ms"],
                    "model_call_count": row["model_call_count"],
                    "f42_fidelity": row["f42_fidelity"],
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
