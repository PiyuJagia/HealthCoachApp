"""Combine product salience and evidence-policy authorization for recommendations.

These remain distinct:

- recommendation_worthy: product/salience judgment from F4.6
- recommendation_authorized: evidence-policy judgment
- final_recommendation_allowed: both must agree before a recommendation may be output
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from evals.trace_schema import (
    ORIGIN_EVIDENCE_POLICY,
    ORIGIN_RECOMMENDATION_BOUNDARY,
    ORIGIN_SALIENCE_ANALYTICS,
    sanitize_for_trace,
)

RECOMMENDATION_STATUS = "RECOMMENDATION"
INSIGHT_STATUS = "INSIGHT"
NO_PATTERN_STATUS = "NO_SIGNIFICANT_NEW_PATTERN"


def compute_final_recommendation_allowed(
    *,
    recommendation_worthy: bool,
    recommendation_authorized: bool,
) -> bool:
    """Final output permission: both product worthiness and policy authorization."""
    return bool(recommendation_worthy) and bool(recommendation_authorized)


def _recommendation_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def salience_flags_from_signals(signals: dict[str, Any] | None) -> tuple[bool, bool]:
    summary = (signals or {}).get("insight_salience") or {}
    if not isinstance(summary, dict):
        return False, False
    return bool(summary.get("insight_worthy")), bool(summary.get("recommendation_worthy"))


@dataclass(frozen=True)
class RecommendationBoundaryDecision:
    recommendation_worthy: bool
    recommendation_authorized: bool
    final_recommendation_allowed: bool
    insight_worthy: bool
    recommendation_worthy_origin: str = ORIGIN_SALIENCE_ANALYTICS
    recommendation_authorized_origin: str = ORIGIN_EVIDENCE_POLICY
    final_recommendation_allowed_origin: str = ORIGIN_RECOMMENDATION_BOUNDARY
    model_status: str | None = None
    model_recommendation_present: bool = False
    final_status: str | None = None
    recommendation_field_present: bool = False
    model_respected_boundary: bool = True
    final_output_respects_boundary: bool = True
    violations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_trace(asdict(self))


def apply_recommendation_boundary(
    structured: dict[str, Any],
    *,
    insight_worthy: bool,
    recommendation_worthy: bool,
    recommendation_authorized: bool,
) -> tuple[dict[str, Any], RecommendationBoundaryDecision]:
    """Stamp the combined gate and strip unauthorized recommendation output.

    Does not invent a recommendation when the gate is true. It only blocks when
    the gate is false, and preserves an INSIGHT when insight_worthy is true.
    """
    allowed = compute_final_recommendation_allowed(
        recommendation_worthy=recommendation_worthy,
        recommendation_authorized=recommendation_authorized,
    )
    updated = dict(structured)
    model_status = str(updated.get("status") or "") or None
    model_rec_present = _recommendation_present(updated.get("recommendation"))
    violations: list[str] = []

    if not allowed:
        if model_rec_present:
            violations.append("recommendation_field_without_final_allowance")
            updated["recommendation"] = None
        if model_status == RECOMMENDATION_STATUS:
            violations.append("recommendation_status_without_final_allowance")
            updated["status"] = INSIGHT_STATUS if insight_worthy else NO_PATTERN_STATUS

    rec_present = _recommendation_present(updated.get("recommendation"))
    final_status = str(updated.get("status") or "") or None
    if not allowed and rec_present:
        violations.append("recommendation_field_without_final_allowance")
        updated["recommendation"] = None
        rec_present = False
    if not allowed and final_status == RECOMMENDATION_STATUS:
        violations.append("recommendation_status_without_final_allowance")
        updated["status"] = INSIGHT_STATUS if insight_worthy else NO_PATTERN_STATUS
        final_status = updated["status"]

    updated["recommendation_worthy"] = bool(recommendation_worthy)
    updated["recommendation_authorized"] = bool(recommendation_authorized)
    updated["final_recommendation_allowed"] = allowed

    respected = not violations
    decision = RecommendationBoundaryDecision(
        recommendation_worthy=bool(recommendation_worthy),
        recommendation_authorized=bool(recommendation_authorized),
        final_recommendation_allowed=allowed,
        insight_worthy=bool(insight_worthy),
        model_status=model_status,
        model_recommendation_present=model_rec_present,
        final_status=str(updated.get("status") or "") or None,
        recommendation_field_present=_recommendation_present(updated.get("recommendation")),
        model_respected_boundary=respected,
        final_output_respects_boundary=not _recommendation_present(updated.get("recommendation"))
        and str(updated.get("status") or "") != RECOMMENDATION_STATUS
        if not allowed
        else True,
        violations=tuple(dict.fromkeys(violations)),
    )
    return updated, decision
