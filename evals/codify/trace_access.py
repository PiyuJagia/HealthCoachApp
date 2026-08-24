"""Read structured TRACE fields for CODIFY graders. No product-side mutation."""

from __future__ import annotations

from typing import Any

import re

from app.output_guard import RECOMMENDATION_PHRASES
from app.recommendation_boundary import (
    INSIGHT_STATUS,
    NO_PATTERN_STATUS,
    RECOMMENDATION_STATUS,
    compute_final_recommendation_allowed,
)

LIFESTYLE_POLICY_INPUTS = frozenset({"caffeine_mg", "alcohol_units"})
LIFESTYLE_TOOL = "get_lifestyle_context"
CONTROL_METRIC_NAME = "respiratory_rate"
HRV_METRIC = "hrv_sdnn_ms"
ELEVATED_STATUSES = frozenset({INSIGHT_STATUS, RECOMMENDATION_STATUS})
ESTABLISHED_TREND = "ESTABLISHED_TREND"
OUTPUT_CONTRACT_ORIGIN = "deterministic_output_contract"


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def text_present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def structured(trace: dict[str, Any]) -> dict[str, Any]:
    return as_dict(trace.get("structured_result"))


def candidate_signals(trace: dict[str, Any]) -> dict[str, Any]:
    return as_dict(trace.get("candidate_signals"))


def insight_salience(trace: dict[str, Any]) -> dict[str, Any]:
    return as_dict(candidate_signals(trace).get("insight_salience"))


def trends(trace: dict[str, Any]) -> list[dict[str, Any]]:
    rows = candidate_signals(trace).get("trends")
    if isinstance(rows, list):
        return [item for item in rows if isinstance(item, dict)]
    return []


def trend_by_metric(trace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("metric")): item for item in trends(trace) if item.get("metric")}


def weekly_summaries(trace: dict[str, Any]) -> list[dict[str, Any]]:
    rows = candidate_signals(trace).get("weekly_summaries")
    if isinstance(rows, list):
        return [item for item in rows if isinstance(item, dict)]
    return []


def weekly_coverage_rows(trace: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for week in weekly_summaries(trace):
        coverage = week.get("coverage")
        if not isinstance(coverage, dict):
            continue
        for metric, payload in coverage.items():
            if not isinstance(payload, dict):
                continue
            row = dict(payload)
            row.setdefault("metric", metric)
            rows.append(row)
    return rows


def output_contract(trace: dict[str, Any]) -> dict[str, Any]:
    return as_dict(trace.get("output_contract"))


def recommendation_boundary(trace: dict[str, Any]) -> dict[str, Any]:
    return as_dict(trace.get("recommendation_boundary"))


def supporting_metric_facts(trace: dict[str, Any]) -> list[dict[str, Any]]:
    facts = structured(trace).get("supporting_metric_facts")
    if isinstance(facts, list):
        return [item for item in facts if isinstance(item, dict)]
    contract_facts = output_contract(trace).get("supporting_metric_facts")
    if isinstance(contract_facts, list):
        return [item for item in contract_facts if isinstance(item, dict)]
    return []


def final_status(trace: dict[str, Any]) -> str:
    return str(structured(trace).get("status") or "")


def tool_names(trace: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in as_list(trace.get("tool_calls")):
        if isinstance(item, dict):
            name = item.get("tool_name") or item.get("tool") or item.get("name")
            if name:
                names.append(str(name))
    for item in as_list(trace.get("activity_log")):
        if isinstance(item, dict):
            name = item.get("tool") or item.get("tool_name")
            if name:
                names.append(str(name))
    return names


def lifestyle_tool_called(trace: dict[str, Any]) -> bool:
    return LIFESTYLE_TOOL in tool_names(trace)


def lifestyle_policy_inputs(trace: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for call in as_list(trace.get("model_calls")):
        if not isinstance(call, dict):
            continue
        lifestyle = as_dict(call.get("lifestyle_context_visible"))
        for item in as_list(lifestyle.get("policy_available_inputs")):
            found.add(str(item))
        rag = as_dict(call.get("rag_evidence_visible"))
        for item in as_list(rag.get("available_inputs")):
            found.add(str(item))
    policy = as_dict(trace.get("policy"))
    # Policy objects do not always echo available_inputs; scan model-visible RAG.
    _ = policy
    return found & LIFESTYLE_POLICY_INPUTS


def user_facing_fields(trace: dict[str, Any]) -> dict[str, Any]:
    payload = structured(trace)
    return {
        "primary_message": payload.get("primary_message"),
        "subtext": payload.get("subtext"),
        "motivational_quote": payload.get("motivational_quote"),
        "insight": payload.get("insight"),
        "recommendation": payload.get("recommendation"),
        "reason_not_surfaced": payload.get("reason_not_surfaced"),
    }


def user_facing_text(trace: dict[str, Any], *, include_recommendation: bool = True) -> str:
    fields = user_facing_fields(trace)
    parts: list[str] = []
    for key, value in fields.items():
        if not include_recommendation and key == "recommendation":
            continue
        if text_present(value):
            parts.append(str(value))
    return "\n".join(parts)


def contains_existing_recommendation_phrase(text: str) -> bool:
    if not text:
        return False
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in RECOMMENDATION_PHRASES)


def boundary_flags(trace: dict[str, Any]) -> dict[str, bool]:
    boundary = recommendation_boundary(trace)
    payload = structured(trace)
    salience = insight_salience(trace)
    worthy = bool(
        boundary.get("recommendation_worthy")
        if "recommendation_worthy" in boundary
        else payload.get("recommendation_worthy")
        if "recommendation_worthy" in payload
        else salience.get("recommendation_worthy")
    )
    authorized = bool(
        boundary.get("recommendation_authorized")
        if "recommendation_authorized" in boundary
        else payload.get("recommendation_authorized")
    )
    allowed = boundary.get("final_recommendation_allowed")
    if allowed is None:
        allowed = payload.get("final_recommendation_allowed")
    if allowed is None:
        allowed = compute_final_recommendation_allowed(
            recommendation_worthy=worthy,
            recommendation_authorized=authorized,
        )
    return {
        "recommendation_worthy": worthy,
        "recommendation_authorized": authorized,
        "final_recommendation_allowed": bool(allowed),
        "insight_worthy": bool(salience.get("insight_worthy")),
    }


def claim_eligibility(trend: dict[str, Any]) -> dict[str, Any]:
    return as_dict(trend.get("claim_eligibility"))


def longitudinal(trend: dict[str, Any]) -> dict[str, Any]:
    nested = as_dict(trend.get("longitudinal"))
    if nested:
        return nested
    return {
        "maintenance_of_gain": bool(trend.get("maintenance_of_gain")),
        "maintenance_of_decline": bool(trend.get("maintenance_of_decline")),
        "longitudinal_context_available": trend.get("longitudinal_context_available"),
    }
