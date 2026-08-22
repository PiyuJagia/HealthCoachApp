"""Build human-readable Assignment 4 baseline trace review artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from evals.baseline_dataset import (
    BASELINE_DATASET_VERSION,
    DATASET_PATH,
    MANUAL_REVIEW_FIELDS,
    RESULTS_DIR,
    TRACE_INDEX_PATH,
    BaselineScenario,
    load_baseline_scenarios,
    validate_baseline_manifest,
)
from evals.trace_schema import SECRET_KEY_FRAGMENTS, sanitize_for_trace

TRACES_DIR = Path(__file__).resolve().parent / "traces"
REVIEW_BUNDLE_PATH = RESULTS_DIR / "baseline_human_review_bundle_v1.md"
REVIEW_PROGRESS_PATH = RESULTS_DIR / "baseline_review_progress_v1.csv"

REVIEW_PROGRESS_COLUMNS = (
    "scenario_id",
    "review_order",
    "review_complete",
    "human_open_coding_notes",
    "human_pass_fail",
    "human_failure_label",
)

MANUAL_REVIEW_TEMPLATE = """### MANUAL REVIEW

Human open-coding notes:



What was good?



What was bad / surprising?



Likely originating layer:
[ ] data / synthetic scenario
[ ] deterministic analytics
[ ] agent trajectory / tool selection
[ ] retrieval
[ ] evidence policy
[ ] generation
[ ] final guard
[ ] product limitation
[ ] unclear

Human PASS / FAIL:



Possible failure label:
(leave blank — taxonomy not yet defined)

"""


def _read_trace_index() -> list[dict[str, str]]:
    if not TRACE_INDEX_PATH.exists():
        raise FileNotFoundError(f"Missing trace index: {TRACE_INDEX_PATH}")
    with TRACE_INDEX_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_trace(trace_file: str) -> dict[str, Any]:
    path = TRACES_DIR / trace_file
    if not path.exists():
        raise FileNotFoundError(f"Missing baseline trace: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return sanitize_for_trace(payload)


def _bullet_lines(items: list[str]) -> str:
    if not items:
        return "- (none)"
    return "\n".join(f"- {item}" for item in items)


def _format_candidate_signals(trace: dict[str, Any]) -> str:
    signals = trace.get("candidate_signals") or {}
    trends = signals.get("trends") or []
    if not trends:
        return "- (none recorded)"
    lines: list[str] = []
    for trend in trends:
        lines.append(
            f"- **{trend.get('metric')}**: current={trend.get('current_value')} | "
            f"baseline={trend.get('baseline_value')} | direction={trend.get('direction')} | "
            f"percent_change={trend.get('percent_change')} | "
            f"maturity={trend.get('data_maturity_state')} | "
            f"as_of_available={trend.get('as_of_date_available')}"
        )
    return "\n".join(lines)


def _format_activity_trajectory(trace: dict[str, Any]) -> str:
    activity = trace.get("activity_log") or []
    if not activity:
        return "- (none recorded)"
    lines: list[str] = []
    for entry in activity:
        phase = str(entry.get("phase") or "UNKNOWN").upper()
        if phase == "ACT":
            tool = entry.get("tool") or entry.get("tool_name") or "unknown"
            args = entry.get("arguments") or {}
            lines.append(f"- **ACT** `{tool}` args={json.dumps(args, sort_keys=True)}")
        elif phase == "OBSERVE":
            tool = entry.get("tool") or entry.get("tool_name") or "unknown"
            summary = entry.get("summary") or entry.get("result_summary") or {}
            lines.append(
                f"- **OBSERVE** `{tool}` summary={json.dumps(summary, sort_keys=True)}"
            )
        elif phase == "DECISION":
            label = entry.get("label") or entry.get("summary") or ""
            lines.append(f"- **DECISION** {label}")
        elif phase == "FINAL":
            label = entry.get("label") or entry.get("summary") or ""
            lines.append(f"- **FINAL** {label}")
        else:
            lines.append(f"- **{phase}** {json.dumps(entry, sort_keys=True)}")
    return "\n".join(lines)


def _format_tool_calls(trace: dict[str, Any]) -> str:
    tool_calls = trace.get("tool_calls") or []
    if not tool_calls:
        return "- (none recorded)"
    lines: list[str] = []
    for call in tool_calls:
        name = call.get("tool_name") or "unknown"
        args = call.get("arguments") or {}
        summary = call.get("result_summary") or {}
        lines.append(f"- **{name}**")
        lines.append(f"  - arguments: `{json.dumps(args, sort_keys=True)}`")
        lines.append(f"  - result_summary: `{json.dumps(summary, sort_keys=True)}`")
    return "\n".join(lines)


def _format_retrieval(trace: dict[str, Any]) -> str:
    retrieval = trace.get("retrieval") or []
    if not retrieval:
        return "- (none recorded)"
    lines: list[str] = []
    for item in retrieval:
        policy_meta = item.get("policy_metadata") or {}
        strength = policy_meta.get("evidence_strength")
        lines.append(
            f"- query=`{item.get('query')}` | document_id=`{item.get('document_id')}` | "
            f"relationship_id=`{item.get('relationship_id') or '—'}` | score={item.get('score')} | "
            f"evidence_strength={strength if strength is not None else '—'}"
        )
    return "\n".join(lines)


def _policy_evidence_authorized(trace: dict[str, Any]) -> str:
    structured = trace.get("structured_result") or {}
    for call in reversed(trace.get("tool_calls") or []):
        if call.get("tool_name") == "retrieve_authorized_evidence":
            summary = call.get("result_summary") or {}
            if "evidence_authorized" in summary:
                return str(summary.get("evidence_authorized"))
    decisions = (trace.get("policy") or {}).get("relationship_decisions") or []
    if any(decision.get("evidence_authorized") for decision in decisions):
        return "True"
    if decisions:
        return "False"
    return "—"


def _format_policy(trace: dict[str, Any]) -> str:
    policy = trace.get("policy") or {}
    structured = trace.get("structured_result") or {}
    lines = [
        f"- overall_verdict: `{policy.get('overall_verdict')}`",
        f"- evidence_authorized: `{_policy_evidence_authorized(trace)}`",
        f"- recommendation_authorized: `{structured.get('recommendation_authorized')}`",
    ]
    decisions = policy.get("relationship_decisions") or []
    if decisions:
        lines.append("- relationship-level decisions:")
        for decision in decisions:
            lines.append(
                f"  - relationship_id=`{decision.get('relationship_id')}` | "
                f"verdict=`{decision.get('verdict')}` | "
                f"evidence_authorized={decision.get('evidence_authorized')} | "
                f"recommendation_authorized={decision.get('recommendation_authorized')} | "
                f"evidence_strength={decision.get('evidence_strength')} | "
                f"reasons={decision.get('reasons')}"
            )
    else:
        lines.append("- relationship-level decisions: (none recorded)")

    suppressed = policy.get("suppressed_relationship_ids") or []
    reasons = policy.get("reasons") or []
    if suppressed:
        lines.append(f"- suppressed_relationship_ids: `{suppressed}`")
    if reasons:
        lines.append(f"- suppression/policy reasons: `{reasons}`")
    return "\n".join(lines)


def _format_final_result(trace: dict[str, Any]) -> str:
    structured = trace.get("structured_result") or {}
    if not structured:
        return "- (none recorded)"
    lines = [
        f"- status: `{structured.get('status')}`",
        f"- theme: {structured.get('theme') or '—'}",
        f"- insight: {structured.get('insight') or '—'}",
        f"- recommendation: {structured.get('recommendation') or '—'}",
        f"- source_refs: `{structured.get('source_refs') or []}`",
        f"- confidence_language: {structured.get('confidence_language') or '—'}",
    ]
    return "\n".join(lines)


def _format_final_guard(trace: dict[str, Any]) -> str:
    guard = trace.get("final_guard") or {}
    passed = guard.get("passed")
    status = "PASS" if passed else "FAIL"
    violations = guard.get("violations") or []
    lines = [f"- result: **{status}**", f"- violations: `{violations}`"]
    return "\n".join(lines)


def _format_operational(trace: dict[str, Any], index_row: dict[str, str]) -> str:
    provider_retry = trace.get("provider_retry")
    lines = [
        f"- tool_call_count: {index_row.get('tool_call_count') or len(trace.get('tool_calls') or [])}",
        f"- latency_ms: {trace.get('latency_ms') or index_row.get('latency_ms')}",
        f"- run_status: `{index_row.get('run_status')}`",
        f"- trace_file: `{index_row.get('trace_file')}`",
        f"- run_id: `{trace.get('run_id') or index_row.get('run_id')}`",
    ]
    if provider_retry:
        lines.append(f"- provider_retry: `{json.dumps(provider_retry, sort_keys=True)}`")
    else:
        lines.append("- provider_failure_state: none")
    return "\n".join(lines)


def render_scenario_section(
    scenario: BaselineScenario,
    index_row: dict[str, str],
    trace: dict[str, Any],
) -> str:
    parts = [
        f"## {scenario.scenario_id} — Family {scenario.family}: {scenario.name}",
        "",
        f"**As-of date:** {scenario.as_of_date.isoformat()}",
        "",
        "### Scenario description",
        scenario.scenario_description,
        "",
        "### Expected high-level behavior",
        scenario.expected_high_level_behavior,
        "",
        "### Must do",
        _bullet_lines(list(scenario.must_do)),
        "",
        "### Must not do",
        _bullet_lines(list(scenario.must_not_do)),
        "",
        "### Deterministic candidate signals",
        _format_candidate_signals(trace),
        "",
        "### Observable agent trajectory",
        _format_activity_trajectory(trace),
        "",
        "### Tool calls",
        _format_tool_calls(trace),
        "",
        "### Retrieval",
        _format_retrieval(trace),
        "",
        "### Policy",
        _format_policy(trace),
        "",
        "### Final generated result",
        _format_final_result(trace),
        "",
        "### Final guard",
        _format_final_guard(trace),
        "",
        "### Operational information",
        _format_operational(trace, index_row),
        "",
        MANUAL_REVIEW_TEMPLATE.rstrip(),
        "",
        "---------------------------------------",
        "",
    ]
    return "\n".join(parts)


def build_review_bundle(*, force: bool = False) -> Path:
    if REVIEW_BUNDLE_PATH.exists() and not force:
        existing = REVIEW_BUNDLE_PATH.read_text(encoding="utf-8")
        if "Human PASS / FAIL: PASS" in existing or "Human PASS / FAIL: FAIL" in existing or "Human PASS / FAIL: Pass" in existing or "Human PASS / FAIL: Fail" in existing or "Human PASS / FAIL: fail" in existing:
            raise RuntimeError(
                f"Refusing to overwrite completed human reviews in {REVIEW_BUNDLE_PATH}. "
                "Use force=True only if you intend to regenerate blank manual sections."
            )
    scenarios = load_baseline_scenarios()
    validate_baseline_manifest(scenarios)
    index_rows = _read_trace_index()
    index_by_id = {row["scenario_id"]: row for row in index_rows}

    if len(index_rows) != 15:
        raise ValueError(f"Expected 15 index rows; found {len(index_rows)}.")

    header = "\n".join(
        [
            "# Assignment 4 Baseline — Human Trace Review Bundle v1",
            "",
            f"Dataset: `{BASELINE_DATASET_VERSION}`",
            "",
            "This bundle archives frozen baseline traces for manual open-coding.",
            "Do not treat expected behavior sections as PASS/FAIL labels.",
            "",
            "---------------------------------------",
            "",
        ]
    )

    sections: list[str] = [header]
    for order, scenario in enumerate(scenarios, start=1):
        index_row = index_by_id.get(scenario.scenario_id)
        if index_row is None:
            raise ValueError(f"Missing index row for scenario {scenario.scenario_id}.")
        trace = _load_trace(index_row["trace_file"])
        if trace.get("scenario_id") != scenario.scenario_id:
            raise ValueError(
                f"Trace scenario mismatch for {scenario.scenario_id}: "
                f"trace has {trace.get('scenario_id')}."
            )
        sections.append(render_scenario_section(scenario, index_row, trace))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_BUNDLE_PATH.write_text("".join(sections), encoding="utf-8")
    return REVIEW_BUNDLE_PATH


def build_review_progress_csv() -> Path:
    scenarios = load_baseline_scenarios()
    validate_baseline_manifest(scenarios)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "scenario_id": scenario.scenario_id,
            "review_order": str(index),
            "review_complete": "false",
            "human_open_coding_notes": "",
            "human_pass_fail": "",
            "human_failure_label": "",
        }
        for index, scenario in enumerate(scenarios, start=1)
    ]
    with REVIEW_PROGRESS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEW_PROGRESS_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return REVIEW_PROGRESS_PATH


def bundle_contains_secrets(text: str) -> bool:
    lowered = text.lower()
    forbidden_value_markers = ("sk-", "api_key=", "secret=", "password=", "authorization: bearer")
    for marker in forbidden_value_markers:
        if marker in lowered:
            return True
    for fragment in SECRET_KEY_FRAGMENTS:
        if fragment in ("openai", "pinecone"):
            continue
        if f'"{fragment}"' in lowered:
            return True
    return False
