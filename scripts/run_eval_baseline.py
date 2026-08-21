"""Run Assignment 4 Phase F1 baseline traces through the current Health Coach agent."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.runner import run_health_review
from agent.schemas import HealthCoachStatus
from evals.baseline_dataset import (
    BASELINE_DATASET_VERSION,
    COMPLETED_RUN_STATUS,
    ERROR_RUN_STATUS,
    MANUAL_REVIEW_FIELDS,
    METADATA_PATH,
    PROVIDER_FAILURE_RUN_STATUS,
    RESULTS_DIR,
    TRACE_INDEX_COLUMNS,
    TRACE_INDEX_PATH,
    BaselineScenario,
    classify_run_status,
    load_baseline_scenarios,
    validate_baseline_manifest,
)

load_dotenv(PROJECT_ROOT / ".env")


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


TRACE_COMPLETENESS_FIELDS = (
    "run_id",
    "scenario_id",
    "user_id",
    "as_of_date",
    "candidate_signals",
    "tool_calls",
    "retrieval",
    "policy",
    "generation",
    "final_guard",
    "structured_result",
    "activity_log",
)


def verify_trace_completeness(trace_payload: dict[str, Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for field in TRACE_COMPLETENESS_FIELDS:
        if field not in trace_payload:
            missing.append(field)
            continue
        value = trace_payload[field]
        if field in {"candidate_signals", "tool_calls", "retrieval", "activity_log"} and value is None:
            missing.append(field)
    policy = trace_payload.get("policy") or {}
    if not policy.get("overall_verdict"):
        missing.append("policy.overall_verdict")
    structured = trace_payload.get("structured_result") or {}
    if not structured.get("status"):
        missing.append("structured_result.status")
    guard = trace_payload.get("final_guard") or {}
    if "passed" not in guard:
        missing.append("final_guard.passed")
    return len(missing) == 0, missing


def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_baseline_metadata() -> dict[str, Any]:
    from agent.agent import MAX_LLM_CALLS, MODEL
    from analytics.trends import (
        BASELINE_WINDOW_DAYS,
        CURRENT_WINDOW_DAYS,
        MIN_BASELINE_OBSERVATIONS,
        MIN_CURRENT_OBSERVATIONS,
        STABLE_PERCENT_THRESHOLD,
    )
    from rag.retrieval import DEFAULT_MIN_RELEVANCE_SCORE, DEFAULT_TOP_K, get_top_k
    from rag.vector_store import get_index_name, get_namespace

    try:
        import google.adk

        adk_version = getattr(google.adk, "__version__", "unknown")
    except ImportError:
        adk_version = "unknown"

    return {
        "baseline_dataset_version": BASELINE_DATASET_VERSION,
        "git_head": _git_head(),
        "gemini_model": MODEL,
        "adk_version": adk_version,
        "pinecone_index_name": get_index_name(),
        "pinecone_namespace": get_namespace(),
        "trend_configuration": {
            "current_window_days": CURRENT_WINDOW_DAYS,
            "baseline_window_days": BASELINE_WINDOW_DAYS,
            "min_current_observations": MIN_CURRENT_OBSERVATIONS,
            "min_baseline_observations": MIN_BASELINE_OBSERVATIONS,
            "stable_percent_threshold": STABLE_PERCENT_THRESHOLD,
        },
        "rag_top_k": get_top_k(),
        "rag_default_top_k": DEFAULT_TOP_K,
        "rag_min_relevance_score": DEFAULT_MIN_RELEVANCE_SCORE,
        "max_llm_calls": MAX_LLM_CALLS,
    }


def write_baseline_metadata() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_baseline_metadata()
    METADATA_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return METADATA_PATH


def _read_trace_index() -> dict[str, dict[str, str]]:
    if not TRACE_INDEX_PATH.exists():
        return {}
    with TRACE_INDEX_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {row["scenario_id"]: row for row in reader}


def _index_row_from_result(
    *,
    scenario: BaselineScenario,
    trace_payload: dict[str, Any],
    trace_file: str,
    run_status: str,
) -> dict[str, str]:
    policy = trace_payload.get("policy") or {}
    structured = trace_payload.get("structured_result") or {}
    tool_calls = trace_payload.get("tool_calls") or []
    evidence_called = any(
        call.get("tool_name") == "retrieve_authorized_evidence" for call in tool_calls
    )
    guard = trace_payload.get("final_guard") or {}
    return {
        "scenario_id": scenario.scenario_id,
        "family": scenario.family,
        "as_of_date": scenario.as_of_date.isoformat(),
        "trace_file": trace_file,
        "run_id": str(trace_payload.get("run_id") or ""),
        "run_status": run_status,
        "tool_call_count": str(len(tool_calls)),
        "evidence_tool_called": "true" if evidence_called else "false",
        "policy_verdict": str(policy.get("overall_verdict") or ""),
        "recommendation_authorized": str(
            structured.get("recommendation_authorized")
            if structured.get("recommendation_authorized") is not None
            else policy.get("recommendation_authorized", "")
        ),
        "final_status": str(structured.get("status") or ""),
        "final_guard_passed": str(guard.get("passed", "")),
        "latency_ms": str(trace_payload.get("latency_ms") or ""),
        "human_open_coding_notes": "",
        "human_pass_fail": "",
        "human_failure_label": "",
    }


def write_trace_index(rows: list[dict[str, str]]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ordered_ids = [row["scenario_id"] for row in rows]
    existing = _read_trace_index()
    merged_rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for scenario_id in ordered_ids:
        merged_rows.append(next(row for row in rows if row["scenario_id"] == scenario_id))
        seen.add(scenario_id)
    for scenario_id, row in sorted(existing.items()):
        if scenario_id not in seen:
            merged_rows.append(row)
    with TRACE_INDEX_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(TRACE_INDEX_COLUMNS))
        writer.writeheader()
        writer.writerows(merged_rows)
    return TRACE_INDEX_PATH


def _should_skip_resume(scenario_id: str, resume: bool) -> bool:
    if not resume:
        return False
    existing = _read_trace_index()
    row = existing.get(scenario_id)
    if row is None:
        return False
    return row.get("run_status") == COMPLETED_RUN_STATUS


def run_baseline_scenario(scenario: BaselineScenario) -> dict[str, Any]:
    result = run_health_review(
        scenario_id=scenario.scenario_id,
        user_id=scenario.user_id,
        as_of_date=scenario.as_of_date,
    )
    trace_payload = json.loads(result.trace_path.read_text(encoding="utf-8"))
    final_status = str(result.structured.get("status") or "")
    run_status = classify_run_status(final_status)
    complete, missing = verify_trace_completeness(trace_payload)
    if not complete and run_status == COMPLETED_RUN_STATUS:
        run_status = ERROR_RUN_STATUS
    return {
        "scenario_id": scenario.scenario_id,
        "run_status": run_status,
        "final_status": final_status,
        "trace_file": result.trace_path.name,
        "trace_path": str(result.trace_path),
        "run_id": trace_payload.get("run_id"),
        "trace_payload": trace_payload,
        "latency_ms": result.latency_ms,
        "guard_passed": result.guard_passed,
        "provider_retry": result.provider_retry,
        "trace_complete": complete,
        "trace_missing_fields": missing,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Assignment 4 baseline trace collection.")
    parser.add_argument("--all", action="store_true", help="Run all 15 baseline scenarios.")
    parser.add_argument(
        "--scenario",
        action="append",
        help="Run one baseline scenario id (e.g. HC-EVAL-A1).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip scenarios that already have a completed baseline product trace.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Write baseline metadata manifest without running live scenarios.",
    )
    return parser


def main() -> int:
    _configure_stdout()
    args = build_parser().parse_args()
    scenarios = load_baseline_scenarios()
    validate_baseline_manifest(scenarios)
    metadata_path = write_baseline_metadata()
    print(f"Baseline metadata: {metadata_path}")

    if args.metadata_only:
        return 0

    if args.all:
        selected = scenarios
    elif args.scenario:
        lookup = {scenario.scenario_id: scenario for scenario in scenarios}
        missing = [scenario_id for scenario_id in args.scenario if scenario_id not in lookup]
        if missing:
            print(f"Unknown scenario ids: {', '.join(missing)}", file=sys.stderr)
            return 2
        selected = [lookup[scenario_id] for scenario_id in args.scenario]
    else:
        print("Provide --all, --scenario HC-EVAL-A1, or --metadata-only", file=sys.stderr)
        return 2

    index_rows: list[dict[str, str]] = []
    attempted = 0
    completed = 0
    provider_failures = 0
    errors = 0
    stopped_for_provider = False

    for scenario in selected:
        if _should_skip_resume(scenario.scenario_id, args.resume):
            print(f"SKIP (resume): {scenario.scenario_id}")
            continue

        attempted += 1
        print("=" * 72)
        print(f"BASELINE RUN: {scenario.scenario_id} — {scenario.name}")
        print(f"as_of_date={scenario.as_of_date.isoformat()}")
        try:
            outcome = run_baseline_scenario(scenario)
        except Exception as exc:  # noqa: BLE001 — baseline runner records operational failures
            errors += 1
            print(f"ERROR: {scenario.scenario_id}: {exc!r}", file=sys.stderr)
            index_rows.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "family": scenario.family,
                    "as_of_date": scenario.as_of_date.isoformat(),
                    "trace_file": "",
                    "run_id": "",
                    "run_status": ERROR_RUN_STATUS,
                    "tool_call_count": "",
                    "evidence_tool_called": "",
                    "policy_verdict": "",
                    "recommendation_authorized": "",
                    "final_status": "",
                    "final_guard_passed": "",
                    "latency_ms": "",
                    **{field: "" for field in MANUAL_REVIEW_FIELDS},
                }
            )
            continue

        run_status = outcome["run_status"]
        print(f"run_status={run_status} final_status={outcome['final_status']}")
        print(f"trace_complete={outcome['trace_complete']} missing={outcome['trace_missing_fields']}")
        print(f"trace_file={outcome['trace_file']} run_id={outcome['run_id']}")
        print(f"latency_ms={outcome['latency_ms']}")

        index_rows.append(
            _index_row_from_result(
                scenario=scenario,
                trace_payload=outcome["trace_payload"],
                trace_file=outcome["trace_file"],
                run_status=run_status,
            )
        )

        if run_status == COMPLETED_RUN_STATUS:
            completed += 1
        elif run_status == PROVIDER_FAILURE_RUN_STATUS:
            provider_failures += 1
            print(
                f"PROVIDER FAILURE: {scenario.scenario_id} "
                f"status={outcome['final_status']} — not classified as product failure."
            )
            if outcome["final_status"] in {
                HealthCoachStatus.MODEL_QUOTA_EXHAUSTED.value,
                HealthCoachStatus.TEMPORARY_MODEL_UNAVAILABLE.value,
            }:
                stopped_for_provider = True
                print("Stopping baseline run due to provider limit. Re-run later with --resume.")
                break
        else:
            errors += 1

    if index_rows:
        index_path = write_trace_index(index_rows)
        print(f"\nTrace index updated: {index_path}")

    print("\nBASELINE SUMMARY")
    print(f"attempted={attempted} completed={completed} provider_failures={provider_failures} errors={errors}")
    if stopped_for_provider:
        print("Stopped early for provider quota/availability. Use --resume to continue.")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
