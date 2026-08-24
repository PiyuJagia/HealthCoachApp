"""F7 post-remediation 15-scenario Gemini measurement.

Measurement only. Does not change product code, CODIFY graders, frozen labels,
or the F1 baseline_trace_index.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from agent.instructions import HEALTH_COACH_INSTRUCTIONS
from agent.runner import run_health_review
from agent.schemas import HealthCoachStatus, parse_agent_json_payload
from data.database import get_session_factory
from data.demo_seed import DEMO_DISPLAY_NAME, seed_demo_health_data
from data.models import User
from evals.baseline_dataset import (
    BASELINE_DATASET_VERSION,
    COMPLETED_RUN_STATUS,
    ERROR_RUN_STATUS,
    PROVIDER_FAILURE_RUN_STATUS,
    classify_run_status,
    load_baseline_scenarios,
    validate_baseline_manifest,
)
from evals.codify.catalog import DETERMINISTIC_SPECS, SEMANTIC_SPECS
from evals.codify.runner import grade_trace, grade_trace_paths, summarize_grades
from scripts.run_eval_baseline import build_baseline_metadata, verify_trace_completeness

load_dotenv(PROJECT_ROOT / ".env")

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RUN_ID = "post_remediation_v1"
ARCHIVE_DIR = RESULTS_DIR / "post_remediation_traces_v1"
CONFIG_PATH = RESULTS_DIR / "post_remediation_run_config_v1.json"
INDEX_PATH = RESULTS_DIR / "post_remediation_trace_index_v1.csv"
CODIFY_RESULTS_PATH = RESULTS_DIR / "post_remediation_codify_results_v1.json"
CODIFY_SUMMARY_PATH = RESULTS_DIR / "post_remediation_codify_summary_v1.json"
MANIFEST_PATH = ARCHIVE_DIR / "run_manifest.json"

EXPECTED_IDS = (
    "HC-EVAL-A1",
    "HC-EVAL-A2",
    "HC-EVAL-A3",
    "HC-EVAL-A4",
    "HC-EVAL-B1",
    "HC-EVAL-B2",
    "HC-EVAL-B3",
    "HC-EVAL-C1",
    "HC-EVAL-C2",
    "HC-EVAL-C3",
    "HC-EVAL-C4",
    "HC-EVAL-D1",
    "HC-EVAL-D2",
    "HC-EVAL-D3",
    "HC-EVAL-E1",
)


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _git(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


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


def build_run_config() -> dict[str, Any]:
    metadata = build_baseline_metadata()
    dirty = [line for line in _git(["status", "--porcelain"]).splitlines() if line.strip()]
    instruction_hash = hashlib.sha256(HEALTH_COACH_INSTRUCTIONS.encode("utf-8")).hexdigest()
    return {
        "run_id": RUN_ID,
        "phase": "F7",
        "purpose": "post_remediation_measurement",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": metadata.get("git_head"),
        "git_head_subject": _git(["log", "-1", "--format=%s"]),
        "working_tree_dirty": bool(dirty),
        "working_tree_paths": [
            line[3:].strip() if len(line) > 3 else line
            for line in dirty
            if ".env" not in line.lower()
        ],
        "gemini_model": metadata.get("gemini_model"),
        "provider": "google_gemini_via_adk",
        "adk_version": metadata.get("adk_version"),
        "baseline_dataset_version": BASELINE_DATASET_VERSION,
        "scenario_ids": list(EXPECTED_IDS),
        "instruction_sha256": instruction_hash,
        "codify_catalog_version": "codify_v1",
        "codify_deterministic_grader_ids": [item.grader_id for item in DETERMINISTIC_SPECS],
        "codify_semantic_spec_ids": [item.grader_id for item in SEMANTIC_SPECS],
        "max_llm_calls": metadata.get("max_llm_calls"),
        "pinecone_index_name": metadata.get("pinecone_index_name"),
        "pinecone_namespace": metadata.get("pinecone_namespace"),
        "rag_top_k": metadata.get("rag_top_k"),
        "rag_min_relevance_score": metadata.get("rag_min_relevance_score"),
        "trend_configuration": metadata.get("trend_configuration"),
        "notes": (
            "Frozen F1 baseline_trace_index and human labels are not written. "
            "CODIFY graders are invoked as-is. No secrets persisted."
        ),
    }


def write_run_config() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_run_config()
    CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return CONFIG_PATH


def _grade_payload(payload: dict[str, Any]) -> dict[str, Any]:
    grade = grade_trace(payload)
    return grade.to_dict()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _completed_ids() -> set[str]:
    if not MANIFEST_PATH.exists():
        return set()
    rows = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        str(row.get("scenario_id"))
        for row in rows
        if row.get("run_status") == COMPLETED_RUN_STATUS
    }


def main() -> int:
    _configure_stdout()
    validate_baseline_manifest()
    scenarios = load_baseline_scenarios()
    if [item.scenario_id for item in scenarios] != list(EXPECTED_IDS):
        raise SystemExit("Baseline scenario order/ids do not match the frozen 15-scenario set.")
    user_id = ensure_demo_user()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    config_path = write_run_config()
    print(f"F7 RUN CONFIG: {config_path}")
    print(json.dumps(json.loads(config_path.read_text(encoding="utf-8")), indent=2)[:1200])

    resume = "--resume" in sys.argv
    already = _completed_ids() if resume else set()
    manifest: list[dict[str, Any]] = []
    if resume and MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    for scenario in scenarios:
        if scenario.scenario_id in already:
            print(f"SKIP (resume): {scenario.scenario_id}")
            continue
        print("=" * 72)
        print(
            f"F7 LIVE: {scenario.scenario_id} as_of={scenario.as_of_date.isoformat()} "
            f"user_id={scenario.user_id} demo_user={user_id}"
        )
        try:
            result = run_health_review(
                scenario_id=scenario.scenario_id,
                user_id=scenario.user_id,
                as_of_date=scenario.as_of_date,
            )
            payload = json.loads(result.trace_path.read_text(encoding="utf-8"))
            archived = ARCHIVE_DIR / result.trace_path.name
            shutil.copy2(result.trace_path, archived)
            raw_parsed = _parse_raw(result.raw_final_text)
            (ARCHIVE_DIR / f"{result.trace_path.stem}.raw_model.json").write_text(
                json.dumps({"raw_final_text": result.raw_final_text, "parsed": raw_parsed}, indent=2),
                encoding="utf-8",
            )
            complete, missing = verify_trace_completeness(payload)
            final_status = str((payload.get("structured_result") or {}).get("status") or "")
            run_status = classify_run_status(final_status)
            if not complete and run_status == COMPLETED_RUN_STATUS:
                run_status = ERROR_RUN_STATUS
            model_calls = payload.get("model_calls") or []
            omitted = sum(int(call.get("omitted_thought_parts") or 0) for call in model_calls)
            fidelity = bool(model_calls) and all(
                call.get("capture_fidelity") == "adk_pre_model_request" for call in model_calls
            )
            grade_dict = _grade_payload(payload)
            structured = payload.get("structured_result") or {}
            row = {
                "scenario_id": scenario.scenario_id,
                "family": scenario.family,
                "as_of_date": scenario.as_of_date.isoformat(),
                "run_id": payload.get("run_id"),
                "trace_file": archived.name,
                "run_status": run_status,
                "final_status": final_status,
                "primary_message": structured.get("primary_message"),
                "motivational_quote": structured.get("motivational_quote"),
                "recommendation": structured.get("recommendation"),
                "final_recommendation_allowed": structured.get("final_recommendation_allowed"),
                "guard_passed": (payload.get("final_guard") or {}).get("passed"),
                "latency_ms": payload.get("latency_ms"),
                "model": payload.get("model"),
                "model_call_count": len(model_calls),
                "f42_fidelity": fidelity,
                "omitted_thought_parts": omitted,
                "trace_complete": complete,
                "trace_missing_fields": missing,
                "provider_retry": result.provider_retry,
                "codify": {
                    "pass": grade_dict.get("deterministic_pass_count"),
                    "fail": grade_dict.get("deterministic_fail_count"),
                    "results": grade_dict.get("results"),
                },
            }
            print(
                f"status={final_status} run_status={run_status} "
                f"codify_fail={row['codify']['fail']} latency_ms={row['latency_ms']}"
            )
            print(f"primary={structured.get('primary_message')!r}")
        except Exception as exc:  # noqa: BLE001 — measurement continues
            print(f"ERROR: {scenario.scenario_id}: {exc!r}", file=sys.stderr)
            row = {
                "scenario_id": scenario.scenario_id,
                "family": scenario.family,
                "as_of_date": scenario.as_of_date.isoformat(),
                "run_status": ERROR_RUN_STATUS,
                "error": repr(exc),
            }
        manifest = [item for item in manifest if item.get("scenario_id") != scenario.scenario_id]
        manifest.append(row)
        _write_json(MANIFEST_PATH, manifest)
        if row.get("run_status") == COMPLETED_RUN_STATUS:
            already.add(scenario.scenario_id)
        if row.get("final_status") == HealthCoachStatus.MODEL_QUOTA_EXHAUSTED.value:
            print("Quota exhausted. Stopping remaining scenarios. Re-run with --resume later.")
            break

    completed_paths = [
        ARCHIVE_DIR / row["trace_file"]
        for row in manifest
        if row.get("trace_file") and (ARCHIVE_DIR / row["trace_file"]).exists()
    ]
    all_grades = grade_trace_paths(completed_paths)
    _write_json(
        CODIFY_RESULTS_PATH,
        {
            "run_id": RUN_ID,
            "summary": summarize_grades(all_grades),
            "scenarios": [grade.to_dict() for grade in all_grades],
        },
    )
    _write_json(CODIFY_SUMMARY_PATH, {"run_id": RUN_ID, **summarize_grades(all_grades)})

    import csv

    fieldnames = [
        "scenario_id",
        "family",
        "as_of_date",
        "trace_file",
        "run_id",
        "run_status",
        "final_status",
        "latency_ms",
        "model_call_count",
        "f42_fidelity",
        "codify_pass",
        "codify_fail",
        "guard_passed",
    ]
    with INDEX_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in manifest:
            writer.writerow(
                {
                    "scenario_id": row.get("scenario_id"),
                    "family": row.get("family"),
                    "as_of_date": row.get("as_of_date"),
                    "trace_file": row.get("trace_file", ""),
                    "run_id": row.get("run_id", ""),
                    "run_status": row.get("run_status", ""),
                    "final_status": row.get("final_status", ""),
                    "latency_ms": row.get("latency_ms", ""),
                    "model_call_count": row.get("model_call_count", ""),
                    "f42_fidelity": row.get("f42_fidelity", ""),
                    "codify_pass": (row.get("codify") or {}).get("pass", ""),
                    "codify_fail": (row.get("codify") or {}).get("fail", ""),
                    "guard_passed": row.get("guard_passed", ""),
                }
            )
    print(f"\nArchive: {ARCHIVE_DIR}")
    print(f"Index: {INDEX_PATH}")
    print(f"CODIFY: {CODIFY_SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
