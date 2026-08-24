"""Minimal deterministic guard for future agent-generated insights."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rag.evidence_policy import AuthorizationVerdict, EvidencePolicyDecision
from app.recommendation_boundary import (
    INSIGHT_STATUS,
    NO_PATTERN_STATUS,
    RECOMMENDATION_STATUS,
    compute_final_recommendation_allowed,
)

CAUSAL_PHRASES = (
    r"\bcaused\b",
    r"\bcauses\b",
    r"\bled to\b",
    r"\bresults? in\b",
    r"\bproves\b",
    r"\bproof that\b",
)

UNSUPPORTED_METHOD_PHRASES = (
    r"changepoint analysis",
    r"change-point analysis",
    r"z-score analysis",
    r"z score analysis",
    r"robust rolling statistics",
    r"robust rolling average",
)

RECOMMENDATION_PHRASES = (
    r"\byou should\b",
    r"\bi recommend\b",
    r"\brecommend(?:ation)?(?:s)?\b",
    r"\bmaintain your\b.+\broutine\b",
)


@dataclass(frozen=True)
class GuardResult:
    passed: bool
    violations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {"passed": self.passed, "violations": list(self.violations)}


def _contains_any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _text_present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def check_final_output(
    output: str,
    *,
    decision: EvidencePolicyDecision,
    executed_analytical_methods: set[str] | None = None,
    recommendation_worthy: bool = False,
    structured: dict | None = None,
) -> GuardResult:
    """
    Deterministically validate a candidate final insight against policy decisions.

    This is not an NLP classifier. It applies explicit, testable checks only.
    Recommendation output requires both policy authorization and product worthiness.
    """
    violations: list[str] = []
    normalized = (output or "").strip()
    payload = structured or {}
    allowed = compute_final_recommendation_allowed(
        recommendation_worthy=recommendation_worthy,
        recommendation_authorized=decision.recommendation_authorized,
    )

    if not normalized and not payload:
        return GuardResult(passed=True, violations=())

    for relationship_id in decision.suppressed_relationship_ids:
        if relationship_id and relationship_id.lower() in normalized.lower():
            violations.append(f"suppressed_relationship_referenced:{relationship_id}")

    if decision.overall_verdict == AuthorizationVerdict.SUPPRESS and normalized:
        violations.append("output_present_while_policy_suppressed")

    status = str(payload.get("status") or "")
    rec_text = payload.get("recommendation")
    rec_present = _text_present(rec_text)
    primary_present = _text_present(payload.get("primary_message"))
    if status in {INSIGHT_STATUS, RECOMMENDATION_STATUS} and not primary_present:
        violations.append("elevated_status_without_primary_message")
    if status == NO_PATTERN_STATUS and primary_present:
        violations.append("primary_message_on_quiet_path")
    quote_present = _text_present(payload.get("motivational_quote"))
    if (status == NO_PATTERN_STATUS or not primary_present) and quote_present:
        violations.append("motivational_quote_on_quiet_path")
    if status == RECOMMENDATION_STATUS and not allowed:
        violations.append("recommendation_status_without_final_allowance")
    if rec_present and not allowed:
        violations.append("recommendation_field_without_final_allowance")

    if _contains_any(RECOMMENDATION_PHRASES, normalized) and not allowed:
        violations.append("unauthorized_recommendation_language")

    if _contains_any(CAUSAL_PHRASES, normalized):
        violations.append("association_only_causal_wording")

    executed = {method.lower() for method in (executed_analytical_methods or set())}
    for pattern in UNSUPPORTED_METHOD_PHRASES:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            method_key = pattern.replace("\\b", "").replace(" ", "_")
            if method_key not in executed:
                violations.append(f"unsupported_analytical_method_claim:{pattern}")

    for item in decision.relationship_decisions:
        if item.modifier_suppressor_only and item.relationship_id.lower() in normalized.lower():
            violations.append(f"modifier_only_relationship_surfaced:{item.relationship_id}")

    return GuardResult(passed=not violations, violations=tuple(violations))
