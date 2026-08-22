"""Targeted post-F4.4 Gemini run for HC-EVAL-C1/C2/C3 only.

Does not update frozen baseline_trace_index or human labels.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from agent.runner import run_health_review
from data.database import get_session_factory
from data.demo_seed import DEMO_DISPLAY_NAME, seed_demo_health_data
from data.models import User
from evals.baseline_dataset import load_baseline_scenarios

load_dotenv(PROJECT_ROOT / ".env")

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
ARCHIVE_DIR = RESULTS_DIR / "f44_c_family_traces"
REPORT_MD = RESULTS_DIR / "f44_c_family_post_remediation_v1.md"
REPORT_JSON = RESULTS_DIR / "f44_c_family_post_remediation_v1.json"

TARGET_IDS = ("HC-EVAL-C1", "HC-EVAL-C2", "HC-EVAL-C3")

CAUSAL_PATTERNS = (
    re.compile(r"\bcaused\b", re.I),
    re.compile(r"\bcausing\b", re.I),
    re.compile(r"\bbecause of (?:your )?caffeine\b", re.I),
    re.compile(r"\bdue to (?:your )?caffeine\b", re.I),
    re.compile(r"\bcaffeine (?:made|caused|ruined|worsened)\b", re.I),
    re.compile(r"\balcohol (?:caused|made|worsened)\b", re.I),
    re.compile(r"\blate[- ]work (?:caused|made)\b", re.I),
    re.compile(r"\bwork stress (?:caused|made)\b", re.I),
)
ASSOCIATION_PATTERNS = (
    re.compile(r"\bassociat", re.I),
    re.compile(r"\bcoincid", re.I),
    re.compile(r"\bco-occur", re.I),
    re.compile(r"\bsame period\b", re.I),
    re.compile(r"\bmay be relevant\b", re.I),
    re.compile(r"\bobservational\b", re.I),
    re.compile(r"\bwithout establishing causation\b", re.I),
    re.compile(r"\bdoes not (?:prove|establish) caus", re.I),
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


def _lifestyle_tool_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    for item in payload.get("tool_calls") or []:
        if item.get("tool_name") == "get_lifestyle_context":
            return item
    return None


def _evidence_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in payload.get("tool_calls") or [] if item.get("tool_name") == "retrieve_authorized_evidence"]


def _lifestyle_visible_from_model_calls(payload: dict[str, Any]) -> dict[str, Any] | None:
    last = None
    for call in payload.get("model_calls") or []:
        visible = call.get("lifestyle_context_visible")
        if visible:
            last = visible
        for result in call.get("tool_results_visible") or []:
            if result.get("tool_name") == "get_lifestyle_context":
                last = {
                    "origin": result.get("origin"),
                    "summary": call.get("lifestyle_context_visible"),
                    "payload": result.get("payload"),
                }
    return last


def _available_inputs_reached_policy(payload: dict[str, Any]) -> dict[str, Any]:
    inputs: list[str] = []
    for item in _evidence_calls(payload):
        summary = item.get("result_summary") or {}
        found = list(summary.get("available_inputs") or [])
        if found:
            inputs = found
    if not inputs:
        for item in payload.get("activity_log") or []:
            if item.get("tool") == "retrieve_authorized_evidence":
                found = list((item.get("summary") or {}).get("available_inputs") or [])
                if found:
                    inputs = found
    # Full payloads may keep available_inputs only on the tool result, not the summary.
    # Inspect model-call function responses as a fallback.
    if not inputs:
        for call in payload.get("model_calls") or []:
            rag = call.get("rag_evidence_visible") or {}
            found = list(rag.get("available_inputs") or [])
            if found:
                inputs = found
            for result in call.get("tool_results_visible") or []:
                if result.get("tool_name") == "retrieve_authorized_evidence":
                    found = list((result.get("payload") or {}).get("available_inputs") or [])
                    if found:
                        inputs = found
    return {
        "available_inputs": inputs,
        "reached": bool(inputs),
        "has_caffeine_mg": "caffeine_mg" in inputs,
        "has_alcohol_units": "alcohol_units" in inputs,
    }


def _relationship_ids(payload: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for item in payload.get("retrieval") or []:
        rel = item.get("relationship_id")
        if rel:
            ids.append(str(rel))
    return ids


def _text_bundle(structured: dict[str, Any]) -> str:
    return " ".join(
        str(structured.get(key) or "")
        for key in ("theme", "insight", "recommendation", "user_facing_summary")
    )


def _association_vs_causation(text: str) -> dict[str, Any]:
    causal_hits = [pattern.pattern for pattern in CAUSAL_PATTERNS if pattern.search(text)]
    association_hits = [pattern.pattern for pattern in ASSOCIATION_PATTERNS if pattern.search(text)]
    return {
        "causal_hits": causal_hits,
        "association_hits": association_hits,
        "preserved": len(causal_hits) == 0,
    }


def _mentions(text: str, *needles: str) -> dict[str, bool]:
    lowered = text.lower()
    return {needle: needle.lower() in lowered for needle in needles}


def analyze_trace(scenario_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    names = _tool_names(payload)
    structured = payload.get("structured_result") or {}
    text = _text_bundle(structured)
    lifestyle_visible = _lifestyle_visible_from_model_calls(payload)
    lifestyle_call = _lifestyle_tool_payload(payload)
    inputs = _available_inputs_reached_policy(payload)
    policy = payload.get("policy") or {}
    guard = payload.get("final_guard") or {}
    model_calls = payload.get("model_calls") or []
    events = []
    if isinstance(lifestyle_visible, dict):
        payload_events = lifestyle_visible.get("payload") or {}
        if isinstance(payload_events, dict):
            events = list(payload_events.get("events") or [])
    return {
        "scenario_id": scenario_id,
        "run_id": payload.get("run_id"),
        "trace_file": f"{payload.get('run_id')}.json",
        "as_of_date": payload.get("as_of_date"),
        "get_trend_signals_called": "get_trend_signals" in names,
        "get_lifestyle_context_called": "get_lifestyle_context" in names,
        "retrieve_authorized_evidence_called": "retrieve_authorized_evidence" in names,
        "tool_names": names,
        "lifestyle_result_summary": None if lifestyle_call is None else lifestyle_call.get("result_summary"),
        "lifestyle_context_visible_to_gemini": lifestyle_visible,
        "lifestyle_events_visible": events,
        "policy_available_inputs": inputs,
        "relationship_ids": _relationship_ids(payload),
        "evidence_queries": [
            (item.get("result_summary") or {}).get("query") for item in _evidence_calls(payload)
        ],
        "policy_verdict": policy.get("overall_verdict"),
        "policy_reasons": policy.get("reasons"),
        "recommendation_authorized": structured.get("recommendation_authorized"),
        "association_vs_causation": _association_vs_causation(text),
        "mentions": _mentions(text, "caffeine", "alcohol", "late work", "work", "sleep"),
        "final_status": structured.get("status"),
        "theme": structured.get("theme"),
        "insight": structured.get("insight"),
        "recommendation": structured.get("recommendation"),
        "final_guard_passed": guard.get("passed"),
        "final_guard_violations": guard.get("violations") or [],
        "model_call_count": len(model_calls),
        "model_calls_have_f42_fidelity": all(
            call.get("capture_fidelity") == "adk_pre_model_request" for call in model_calls
        )
        if model_calls
        else False,
        "latency_ms": payload.get("latency_ms"),
        "activity_log": payload.get("activity_log"),
    }


def compare_to_baseline(scenario_id: str, current: dict[str, Any]) -> dict[str, Any]:
    baseline = {
        "HC-EVAL-C1": {
            "get_lifestyle_context_called": False,
            "caffeine_visible": False,
            "available_inputs": [],
            "relationship_ids": ["R-02", "R-01", "R-01"],
            "policy_verdict": "QUALIFY",
            "final_status": "INSIGHT",
            "theme": "Sleep Duration Decline",
            "recommendation_authorized": False,
            "final_guard_passed": True,
            "model_call_count": None,
            "latency_ms": 26977,
            "frozen_human_pass_fail": "FAIL",
            "note": "Lifestyle inaccessible; generic sleep-trend analysis; R-07 not evaluable.",
        },
        "HC-EVAL-C2": {
            "get_lifestyle_context_called": False,
            "caffeine_visible": False,
            "available_inputs": [],
            "relationship_ids": ["R-01", "R-02", "R-01"],
            "policy_verdict": "QUALIFY",
            "final_status": "INSIGHT",
            "theme": "Recent Decrease in Sleep Duration",
            "recommendation_authorized": False,
            "final_guard_passed": True,
            "model_call_count": None,
            "latency_ms": 50952,
            "frozen_human_pass_fail": "FAIL",
            "note": "Caffeine and late-work omitted; generic sleep-trend analysis.",
        },
        "HC-EVAL-C3": {
            "get_lifestyle_context_called": False,
            "caffeine_visible": False,
            "available_inputs": [],
            "relationship_ids": ["R-05", "R-05"],
            "policy_verdict": "SURFACE",
            "final_status": "RECOMMENDATION",
            "theme": "Aerobic Exercise and Cardiovascular Indicators",
            "recommendation_authorized": True,
            "final_guard_passed": True,
            "model_call_count": None,
            "latency_ms": 12570,
            "frozen_human_pass_fail": "FAIL",
            "note": "Caffeine inaccessible, so C3 control could not be tested; agent discussed exercise not caffeine.",
        },
    }[scenario_id]
    mentions = current.get("mentions") or {}
    improved_access = bool(current.get("get_lifestyle_context_called"))
    caffeine_visible = bool(mentions.get("caffeine") or current.get("lifestyle_events_visible"))
    if current.get("lifestyle_events_visible"):
        caffeine_visible = any(
            event.get("event_type") == "caffeine" for event in current["lifestyle_events_visible"]
        ) or bool(mentions.get("caffeine"))
    preserved = bool((current.get("association_vs_causation") or {}).get("preserved"))
    cherry_pick = False
    if scenario_id == "HC-EVAL-C3":
        cherry_pick = bool(mentions.get("caffeine")) and "sleep" in (current.get("theme") or "").lower()
        if "caffeine" in (current.get("theme") or "").lower() and current.get("final_status") != "NO_SIGNIFICANT_NEW_PATTERN":
            # Flag only if caffeine is framed as a sleep problem despite stable sleep.
            insight = str(current.get("insight") or "").lower()
            cherry_pick = "sleep" in insight and any(
                token in insight for token in ("declin", "poor", "wors", "problem", "disrupt")
            )
    return {
        "baseline": baseline,
        "improved_lifestyle_access": improved_access,
        "caffeine_now_visible": caffeine_visible,
        "policy_inputs_now_reached": bool((current.get("policy_available_inputs") or {}).get("reached")),
        "association_preserved": preserved,
        "possible_c3_cherry_pick": cherry_pick if scenario_id == "HC-EVAL-C3" else False,
        "frozen_human_pass_fail_unchanged": baseline["frozen_human_pass_fail"],
    }


def write_report(rows: list[dict[str, Any]]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps({"scenarios": rows}, indent=2), encoding="utf-8")
    lines = [
        "# F4.4 targeted post-remediation evaluation — C1 / C2 / C3",
        "",
        "Live Gemini run on the current F4.4 system. Frozen human PASS/FAIL labels were **not** changed.",
        "Prompts, policy principles, analytics, and lifestyle tooling were not modified for this run.",
        "Only HC-EVAL-C1, C2, and C3 were executed. Capture fidelity: `adk_pre_model_request`.",
        "",
    ]
    for row in rows:
        current = row["current"]
        comparison = row["comparison"]
        lines.extend(
            [
                f"## {current['scenario_id']} — {current['as_of_date']}",
                "",
                f"- get_trend_signals called: **{current['get_trend_signals_called']}**",
                f"- get_lifestyle_context called: **{current['get_lifestyle_context_called']}**",
                f"- retrieve_authorized_evidence called: **{current['retrieve_authorized_evidence_called']}**",
                f"- lifestyle summary: `{json.dumps(current['lifestyle_result_summary'])}`",
                f"- policy available_inputs reached: **{current['policy_available_inputs']}**",
                f"- relationships retrieved: `{current['relationship_ids']}`",
                f"- evidence queries: `{current['evidence_queries']}`",
                f"- policy verdict: **{current['policy_verdict']}** reasons=`{current['policy_reasons']}`",
                f"- association ≠ causation preserved: **{current['association_vs_causation']['preserved']}** "
                f"(causal_hits={current['association_vs_causation']['causal_hits']}; "
                f"association_hits={current['association_vs_causation']['association_hits']})",
                f"- mentions: `{current['mentions']}`",
                f"- final status: **{current['final_status']}**",
                f"- theme: {current['theme']}",
                f"- insight: {current['insight']}",
                f"- recommendation: {current['recommendation']}",
                f"- recommendation_authorized: {current['recommendation_authorized']}",
                f"- final guard: passed={current['final_guard_passed']} violations={current['final_guard_violations']}",
                f"- model-call count: **{current['model_call_count']}** (F4.2 fidelity={current['model_calls_have_f42_fidelity']})",
                f"- latency_ms: **{current['latency_ms']}**",
                f"- run_id / trace: `{current['run_id']}` / `{ARCHIVE_DIR / current['trace_file']}`",
                "",
                "Lifestyle events visible to Gemini:",
                "",
            ]
        )
        events = current.get("lifestyle_events_visible") or []
        if not events:
            lines.append("- none")
        for event in events:
            lines.append(
                f"- {event.get('occurred_at')} {event.get('event_type')} "
                f"qty={event.get('quantity')} {event.get('unit')} notes={event.get('notes')}"
            )
        lines.extend(
            [
                "",
                f"Frozen baseline human label (unchanged): **{comparison['frozen_human_pass_fail_unchanged']}**",
                f"Lifestyle access vs baseline: improved={comparison['improved_lifestyle_access']}; "
                f"caffeine visible={comparison['caffeine_now_visible']}; "
                f"policy inputs reached={comparison['policy_inputs_now_reached']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Comparison table — frozen baseline vs post-F4.4",
            "",
            "| Scenario | Lifestyle tool | Caffeine visible | Policy inputs | Relationships | Verdict | Status | Guard | Association preserved | Frozen human label |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        current = row["current"]
        comparison = row["comparison"]
        baseline = comparison["baseline"]
        lines.append(
            f"| {current['scenario_id']} baseline | no | no | none | {baseline['relationship_ids']} | "
            f"{baseline['policy_verdict']} | {baseline['final_status']} | {baseline['final_guard_passed']} | "
            f"n/a (context missing) | {baseline['frozen_human_pass_fail']} |"
        )
        lines.append(
            f"| {current['scenario_id']} post-F4.4 | {current['get_lifestyle_context_called']} | "
            f"{comparison['caffeine_now_visible']} | {current['policy_available_inputs']['available_inputs']} | "
            f"{current['relationship_ids']} | {current['policy_verdict']} | {current['final_status']} | "
            f"{current['final_guard_passed']} | {current['association_vs_causation']['preserved']} | unchanged |"
        )
    lines.extend(["", "New failure modes are discussed in the run summary after inspection.", ""])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    _configure_stdout()
    user_id = ensure_demo_user()
    lookup = {item.scenario_id: item for item in load_baseline_scenarios()}
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for scenario_id in TARGET_IDS:
        scenario = lookup[scenario_id]
        print("=" * 72)
        print(f"POST-F4.4 RUN: {scenario_id} as_of={scenario.as_of_date.isoformat()} user_id={user_id}")
        result = run_health_review(
            scenario_id=scenario.scenario_id,
            user_id=user_id,
            as_of_date=scenario.as_of_date,
        )
        payload = json.loads(result.trace_path.read_text(encoding="utf-8"))
        archived = ARCHIVE_DIR / result.trace_path.name
        shutil.copy2(result.trace_path, archived)
        current = analyze_trace(scenario_id, payload)
        comparison = compare_to_baseline(scenario_id, current)
        rows.append({"current": current, "comparison": comparison})
        print(f"status={current['final_status']} lifestyle={current['get_lifestyle_context_called']}")
        print(f"verdict={current['policy_verdict']} latency_ms={current['latency_ms']}")
        print(f"trace={archived}")
    write_report(rows)
    print(f"\nReport: {REPORT_MD}")
    print(f"JSON: {REPORT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
