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

SECRET_VALUE_PREFIXES = (
    "sk-",
    "pk-",
    "bearer ",
    "ghp_",
    "pc-",
    "api_key=",
    "token=",
    "password=",
)


def new_run_id() -> str:
    return str(uuid4())


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    if any(
        fragment in lowered
        for fragment in ("api_key", "apikey", "password", "secret", "authorization", "openai", "pinecone")
    ):
        return True
    return lowered == "token" or lowered.endswith("_token") or "_token_" in lowered


def _looks_like_secret_value(value: str) -> bool:
    lowered = value.lower().strip()
    return any(lowered.startswith(prefix) or prefix in lowered[:40] for prefix in SECRET_VALUE_PREFIXES)


def sanitize_for_trace(value: Any) -> Any:
    """Recursively remove likely secret-bearing keys/values from trace payloads.

    Dict keys matching credential-like names are always redacted. String values
    are redacted only when they look like credentials, so instruction prose that
    mentions authorization is preserved. Keys such as max_output_tokens are kept.
    """
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_for_trace(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_trace(item) for item in value]
    if isinstance(value, str) and _looks_like_secret_value(value):
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


CAPTURE_FIDELITY_ADK_PRE_MODEL = "adk_pre_model_request"
CAPTURE_FIDELITY_RECONSTRUCTED = "reconstructed_approximation"
CAPTURE_FIDELITY_EXACT_PROVIDER = "exact_provider_request"

CAPTURE_POINT_BEFORE_MODEL = "adk.LlmAgent.before_model_callback"

ORIGIN_SYSTEM_INSTRUCTIONS = "system_agent_instructions"
ORIGIN_USER_SCENARIO_INPUT = "user_scenario_input"
ORIGIN_DETERMINISTIC_ANALYTICS = "deterministic_analytics"
ORIGIN_LONGITUDINAL_ANALYTICS = "deterministic_longitudinal_analytics"
ORIGIN_SALIENCE_ANALYTICS = "deterministic_salience_analytics"
ORIGIN_SPREAD_ANALYTICS = "deterministic_spread_analytics"
ORIGIN_HEALTH_TREND_TOOL = "health_trend_tool"
ORIGIN_WEEKLY_SUMMARY = "weekly_summary"
ORIGIN_EVIDENCE_RAG = "evidence_rag_retrieval"
ORIGIN_EVIDENCE_POLICY = "evidence_policy"
ORIGIN_RECOMMENDATION_BOUNDARY = "deterministic_recommendation_boundary"
ORIGIN_OUTPUT_CONTRACT = "deterministic_output_contract"
ORIGIN_LIFESTYLE_TOOL = "lifestyle_context"
ORIGIN_PRIOR_MODEL_TOOL = "prior_model_tool_interaction"
ORIGIN_GENERATION_CONFIG = "generation_config"

TOOL_ORIGIN_BY_NAME = {
    "get_trend_signals": ORIGIN_HEALTH_TREND_TOOL,
    "retrieve_authorized_evidence": ORIGIN_EVIDENCE_RAG,
    "get_lifestyle_context": ORIGIN_LIFESTYLE_TOOL,
}

GENERATION_CONFIG_KEEP = (
    "temperature",
    "top_p",
    "top_k",
    "max_output_tokens",
    "candidate_count",
    "response_mime_type",
    "response_schema",
    "stop_sequences",
    "presence_penalty",
    "frequency_penalty",
    "seed",
)


@dataclass
class ContextComponentProvenance:
    component: str
    origin: str
    present: bool = True
    source_id: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_trace(asdict(self))


@dataclass
class ObservableMessage:
    role: str
    kind: str
    origin: str
    tool_name: str | None = None
    text: str | None = None
    structured: Any = None

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_trace(asdict(self))


@dataclass
class ModelCallContextTrace:
    """LLM-visible context for one ADK model invocation.

    capture_fidelity is adk_pre_model_request: the ADK LlmRequest immediately
    before Gemini.generate_content_async. This is not the HTTPS wire payload
    and must not be labeled exact_provider_request.
    """

    call_index: int
    model: str
    provider: str = "google_gemini_via_adk"
    capture_fidelity: str = CAPTURE_FIDELITY_ADK_PRE_MODEL
    capture_point: str = CAPTURE_POINT_BEFORE_MODEL
    capture_notes: str = (
        "ADK LlmRequest snapshot at before_model_callback. Adapter may still "
        "add tracking headers, strip labels for Gemini API, and preprocess "
        "inline/file parts after this point. Not the HTTPS wire request."
    )
    system_instruction: str | None = None
    user_scenario_input: str | None = None
    conversation_messages: list[ObservableMessage] = field(default_factory=list)
    tool_calls_preceding: list[dict[str, Any]] = field(default_factory=list)
    tool_results_visible: list[dict[str, Any]] = field(default_factory=list)
    trend_maturity_visible: dict[str, Any] | None = None
    weekly_summaries_visible: dict[str, Any] | None = None
    rag_evidence_visible: dict[str, Any] | None = None
    lifestyle_context_visible: dict[str, Any] | None = None
    longitudinal_context_visible: dict[str, Any] | None = None
    insight_salience_visible: dict[str, Any] | None = None
    within_window_spread_visible: dict[str, Any] | None = None
    recommendation_boundary_visible: dict[str, Any] | None = None
    generation_config: dict[str, Any] | None = None
    provenance: list[ContextComponentProvenance] = field(default_factory=list)
    weekly_summary_bypass_risk: dict[str, Any] | None = None
    omitted_thought_parts: int = 0
    visible_response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["conversation_messages"] = [message.to_dict() for message in self.conversation_messages]
        payload["provenance"] = [item.to_dict() for item in self.provenance]
        payload["tool_calls_preceding"] = sanitize_for_trace(self.tool_calls_preceding)
        payload["tool_results_visible"] = sanitize_for_trace(self.tool_results_visible)
        payload["trend_maturity_visible"] = sanitize_for_trace(self.trend_maturity_visible)
        payload["weekly_summaries_visible"] = sanitize_for_trace(self.weekly_summaries_visible)
        payload["rag_evidence_visible"] = sanitize_for_trace(self.rag_evidence_visible)
        payload["lifestyle_context_visible"] = sanitize_for_trace(self.lifestyle_context_visible)
        payload["longitudinal_context_visible"] = sanitize_for_trace(self.longitudinal_context_visible)
        payload["insight_salience_visible"] = sanitize_for_trace(self.insight_salience_visible)
        payload["within_window_spread_visible"] = sanitize_for_trace(
            self.within_window_spread_visible
        )
        payload["recommendation_boundary_visible"] = sanitize_for_trace(
            self.recommendation_boundary_visible
        )
        payload["generation_config"] = sanitize_for_trace(self.generation_config)
        payload["weekly_summary_bypass_risk"] = sanitize_for_trace(self.weekly_summary_bypass_risk)
        payload["visible_response"] = sanitize_for_trace(self.visible_response)
        return sanitize_for_trace(payload)


@dataclass
class RecommendationBoundaryTrace:
    recommendation_worthy: bool = False
    recommendation_authorized: bool = False
    final_recommendation_allowed: bool = False
    insight_worthy: bool = False
    recommendation_worthy_origin: str = ORIGIN_SALIENCE_ANALYTICS
    recommendation_authorized_origin: str = ORIGIN_EVIDENCE_POLICY
    final_recommendation_allowed_origin: str = ORIGIN_RECOMMENDATION_BOUNDARY
    model_status: str | None = None
    model_recommendation_present: bool = False
    final_status: str | None = None
    recommendation_field_present: bool = False
    model_respected_boundary: bool = True
    final_output_respects_boundary: bool = True
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_trace(asdict(self))


@dataclass
class GenerationTrace:
    model_name: str = ""
    final_insight: str = ""
    primary_message: str | None = None
    subtext: str | None = None
    motivational_quote: str | None = None
    recommendation: str | None = None

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
    recommendation_boundary: RecommendationBoundaryTrace | None = None
    output_contract: dict[str, Any] | None = None
    raw_model_output: dict[str, Any] | None = None
    final_guard: FinalGuardTrace | None = None
    final_output: str = ""
    model_calls: list[ModelCallContextTrace] = field(default_factory=list)

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
            "recommendation_boundary": (
                self.recommendation_boundary.to_dict() if self.recommendation_boundary else None
            ),
            "output_contract": sanitize_for_trace(self.output_contract),
            "raw_model_output": sanitize_for_trace(self.raw_model_output),
            "final_guard": self.final_guard.to_dict() if self.final_guard else None,
            "final_output": self.final_output,
            "model_calls": [call.to_dict() for call in self.model_calls],
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
