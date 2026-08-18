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
    insight: str | None = None
    recommendation: str | None = None
    policy_verdict: str | None = None
    recommendation_authorized: bool = False
    confidence_language: str | None = None
    source_refs: list[str] = field(default_factory=list)
    reason_not_surfaced: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def user_facing_summary(self) -> str:
        if self.status == HealthCoachStatus.NO_SIGNIFICANT_NEW_PATTERN.value:
            return (
                self.insight
                or self.reason_not_surfaced
                or DEFAULT_NO_PATTERN_MESSAGE
            )
        if self.status == HealthCoachStatus.BOUNDED_FAILURE.value:
            return "Analysis stopped after reaching the bounded step limit. No health guidance was returned."
        if self.status == HealthCoachStatus.GUARD_BLOCKED.value:
            return "A safety guard blocked the candidate response. No health guidance was returned."
        if self.status == HealthCoachStatus.TEMPORARY_MODEL_UNAVAILABLE.value:
            return self.reason_not_surfaced or TEMPORARY_MODEL_UNAVAILABLE_MESSAGE
        if self.status == HealthCoachStatus.MODEL_QUOTA_EXHAUSTED.value:
            return self.reason_not_surfaced or MODEL_QUOTA_EXHAUSTED_MESSAGE
        parts: list[str] = []
        if self.theme:
            parts.append(f"Theme: {self.theme}")
        if self.insight:
            parts.append(f"Insight: {self.insight}")
        if self.recommendation:
            parts.append(f"Recommendation: {self.recommendation}")
        return "\n".join(parts) if parts else DEFAULT_NO_PATTERN_MESSAGE


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
        insight=payload.get("insight"),
        recommendation=payload.get("recommendation"),
        policy_verdict=payload.get("policy_verdict"),
        recommendation_authorized=bool(payload.get("recommendation_authorized", False)),
        confidence_language=payload.get("confidence_language"),
        source_refs=[str(item) for item in payload.get("source_refs") or []],
        reason_not_surfaced=payload.get("reason_not_surfaced"),
    )
