"""Structured Health Coach agent output schema."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class HealthCoachStatus(str, Enum):
    INSIGHT = "INSIGHT"
    RECOMMENDATION = "RECOMMENDATION"
    NO_SIGNIFICANT_NEW_PATTERN = "NO_SIGNIFICANT_NEW_PATTERN"
    BOUNDED_FAILURE = "BOUNDED_FAILURE"
    GUARD_BLOCKED = "GUARD_BLOCKED"
    TEMPORARY_MODEL_UNAVAILABLE = "TEMPORARY_MODEL_UNAVAILABLE"
    MODEL_QUOTA_EXHAUSTED = "MODEL_QUOTA_EXHAUSTED"


DEFAULT_NO_PATTERN_MESSAGE = (
    "No significant new pattern in the current comparison window "
    "requires further investigation."
)
TEMPORARY_MODEL_UNAVAILABLE_MESSAGE = (
    "The Health Coach model is temporarily busy. Please try again shortly."
)
MODEL_QUOTA_EXHAUSTED_MESSAGE = (
    "The Health Coach has reached its current model usage limit. Please try again later."
)


@dataclass
class HealthCoachResult:
    scenario_id: str
    user_id: int
    as_of_date: str
    status: str
    theme: str | None = None
    primary_message: str | None = None
    subtext: str | None = None
    motivational_quote: str | None = None
    insight: str | None = None
    recommendation: str | None = None
    policy_verdict: str | None = None
    recommendation_authorized: bool = False
    recommendation_worthy: bool = False
    final_recommendation_allowed: bool = False
    confidence_language: str | None = None
    source_refs: list[str] = field(default_factory=list)
    reason_not_surfaced: str | None = None
    supporting_metric_facts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def user_facing_summary(self) -> str:
        from agent.display import format_health_coach_output

        return format_health_coach_output(self.to_dict())


def bounded_failure_result(
    *,
    scenario_id: str,
    user_id: int,
    as_of_date: str,
    reason: str,
) -> HealthCoachResult:
    return HealthCoachResult(
        scenario_id=scenario_id,
        user_id=user_id,
        as_of_date=as_of_date,
        status=HealthCoachStatus.BOUNDED_FAILURE.value,
        reason_not_surfaced=reason,
    )


def temporary_model_unavailable_result(
    *,
    scenario_id: str,
    user_id: int,
    as_of_date: str,
) -> HealthCoachResult:
    return HealthCoachResult(
        scenario_id=scenario_id,
        user_id=user_id,
        as_of_date=as_of_date,
        status=HealthCoachStatus.TEMPORARY_MODEL_UNAVAILABLE.value,
        reason_not_surfaced=TEMPORARY_MODEL_UNAVAILABLE_MESSAGE,
    )


def model_quota_exhausted_result(
    *,
    scenario_id: str,
    user_id: int,
    as_of_date: str,
) -> HealthCoachResult:
    return HealthCoachResult(
        scenario_id=scenario_id,
        user_id=user_id,
        as_of_date=as_of_date,
        status=HealthCoachStatus.MODEL_QUOTA_EXHAUSTED.value,
        reason_not_surfaced=MODEL_QUOTA_EXHAUSTED_MESSAGE,
    )


def guard_blocked_result(
    *,
    scenario_id: str,
    user_id: int,
    as_of_date: str,
    violations: list[str],
) -> HealthCoachResult:
    return HealthCoachResult(
        scenario_id=scenario_id,
        user_id=user_id,
        as_of_date=as_of_date,
        status=HealthCoachStatus.GUARD_BLOCKED.value,
        reason_not_surfaced="; ".join(violations) if violations else "output_guard_blocked",
    )


def parse_agent_json_payload(text: str) -> dict[str, Any]:
    """Extract JSON object from agent final text."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


def health_coach_result_from_payload(
    payload: dict[str, Any],
    *,
    scenario_id: str,
    user_id: int,
    as_of_date: str,
) -> HealthCoachResult:
    return HealthCoachResult(
        scenario_id=str(payload.get("scenario_id") or scenario_id),
        user_id=int(payload.get("user_id") or user_id),
        as_of_date=str(payload.get("as_of_date") or as_of_date),
        status=str(payload.get("status") or HealthCoachStatus.NO_SIGNIFICANT_NEW_PATTERN.value),
        theme=payload.get("theme"),
        primary_message=payload.get("primary_message"),
        subtext=payload.get("subtext"),
        motivational_quote=payload.get("motivational_quote"),
        insight=payload.get("insight"),
        recommendation=payload.get("recommendation"),
        policy_verdict=payload.get("policy_verdict"),
        recommendation_authorized=bool(payload.get("recommendation_authorized", False)),
        recommendation_worthy=bool(payload.get("recommendation_worthy", False)),
        final_recommendation_allowed=bool(payload.get("final_recommendation_allowed", False)),
        confidence_language=payload.get("confidence_language"),
        source_refs=[str(item) for item in payload.get("source_refs") or []],
        reason_not_surfaced=payload.get("reason_not_surfaced"),
        supporting_metric_facts=[
            dict(item) for item in (payload.get("supporting_metric_facts") or []) if isinstance(item, dict)
        ],
    )
