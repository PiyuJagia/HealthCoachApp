"""Structured trace schemas for future Assignment 4 evaluation artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

SECRET_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "openai",
    "pinecone",
)


def new_run_id() -> str:
    return str(uuid4())


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sanitize_for_trace(value: Any) -> Any:
    """Recursively remove likely secret-bearing keys/values from trace payloads."""
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if any(fragment in key.lower() for fragment in SECRET_KEY_FRAGMENTS):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_for_trace(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_trace(item) for item in value]
    if isinstance(value, str) and any(fragment in value.lower() for fragment in SECRET_KEY_FRAGMENTS):
        return "[REDACTED]"
    return value


@dataclass
class ToolCallTrace:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    result_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_trace(
            {
                "tool_name": self.tool_name,
                "arguments": self.arguments,
                "result_summary": self.result_summary,
            }
        )


@dataclass
class RetrievalTraceItem:
    query: str
    score: float
    document_id: str
    vector_id: str
    chunk_index: int
    relationship_id: str = ""
    policy_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_trace(asdict(self))


@dataclass
class PolicyTrace:
    overall_verdict: str
    reasons: list[str] = field(default_factory=list)
    relationship_decisions: list[dict[str, Any]] = field(default_factory=list)
    suppressed_relationship_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_trace(asdict(self))


@dataclass
class GenerationTrace:
    model_name: str = ""
    final_insight: str = ""

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_trace(asdict(self))


@dataclass
class FinalGuardTrace:
    passed: bool
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_trace(asdict(self))


@dataclass
class TraceRecord:
    run_id: str
    scenario_id: str
    user_id: int | None
    as_of_date: str | None
    timestamp: str
    candidate_signals: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    retrieval: list[RetrievalTraceItem] = field(default_factory=list)
    policy: PolicyTrace | None = None
    generation: GenerationTrace | None = None
    final_guard: FinalGuardTrace | None = None
    final_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "user_id": self.user_id,
            "as_of_date": self.as_of_date,
            "timestamp": self.timestamp,
            "candidate_signals": sanitize_for_trace(self.candidate_signals),
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "retrieval": [item.to_dict() for item in self.retrieval],
            "policy": self.policy.to_dict() if self.policy else None,
            "generation": self.generation.to_dict() if self.generation else None,
            "final_guard": self.final_guard.to_dict() if self.final_guard else None,
            "final_output": self.final_output,
        }
        return sanitize_for_trace(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def empty_trace(
    *,
    scenario_id: str = "unspecified",
    user_id: int | None = None,
    as_of_date: str | None = None,
) -> TraceRecord:
    """Create a safe empty trace shell for partial future runs."""
    return TraceRecord(
        run_id=new_run_id(),
        scenario_id=scenario_id,
        user_id=user_id,
        as_of_date=as_of_date,
        timestamp=utc_timestamp(),
    )
