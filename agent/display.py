"""Shared formatting helpers for CLI and Streamlit demo views."""

from __future__ import annotations

from typing import Any

from agent.provider_retry import (
    is_gemini_quota_exhausted,
    is_transient_gemini_unavailable,
    iter_exception_chain,
)


ANALYZE_HEALTH_SPINNER = "Analyzing health signals…"
GEMINI_BUSY_UI_MESSAGE = (
    "Gemini is temporarily busy. Please try Analyze Health again in a moment."
)
GEMINI_UNAVAILABLE_UI_MESSAGE = (
    "Gemini is temporarily unavailable. Please try again shortly."
)
EVIDENCE_UNAVAILABLE_UI_MESSAGE = (
    "Health evidence retrieval is temporarily unavailable. Please try again shortly."
)
ANALYSIS_FAILED_UI_MESSAGE = "Health analysis could not be completed. Please try again."

_SAFE_ANALYZE_MESSAGES = frozenset(
    {
        GEMINI_BUSY_UI_MESSAGE,
        GEMINI_UNAVAILABLE_UI_MESSAGE,
        EVIDENCE_UNAVAILABLE_UI_MESSAGE,
        ANALYSIS_FAILED_UI_MESSAGE,
    }
)


def summarize_trend_signals(candidate_signals: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in candidate_signals.get("trends") or []:
        rows.append(
            {
                "metric": item.get("metric"),
                "direction": item.get("direction"),
                "data_maturity_state": item.get("data_maturity_state"),
                "percent_change": item.get("percent_change"),
                "current_value": item.get("current_value"),
                "baseline_value": item.get("baseline_value"),
                "as_of_date_available": item.get("as_of_date_available"),
                "gap_caveat_required": item.get("gap_caveat_required"),
                "claim_eligibility": item.get("claim_eligibility"),
            }
        )
    return rows


def format_activity_lines(activity_log: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for step in activity_log:
        phase = step.get("phase")
        if phase == "DECISION":
            lines.append(f"DECISION: {step.get('label', '')}")
        elif phase == "ACT":
            lines.append(f"ACT: {step.get('tool')}({step.get('arguments', {})})")
        elif phase == "OBSERVE":
            summary = step.get("summary") or step.get("result") or {}
            lines.append(f"OBSERVE: {step.get('tool')} -> {summary}")
        elif phase == "FINAL":
            lines.append(f"FINAL: {step.get('label', '')}")
    return lines


def policy_summary(structured: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_verdict": structured.get("policy_verdict"),
        "recommendation_authorized": structured.get("recommendation_authorized"),
        "source_refs": structured.get("source_refs") or [],
    }


def is_temporary_model_unavailable(structured: dict[str, Any]) -> bool:
    return structured.get("status") == "TEMPORARY_MODEL_UNAVAILABLE"


def temporary_unavailable_message(structured: dict[str, Any]) -> str:
    return str(
        structured.get("reason_not_surfaced")
        or "The Health Coach model is temporarily busy. Please try again shortly."
    )


def is_model_quota_exhausted(structured: dict[str, Any]) -> bool:
    return structured.get("status") == "MODEL_QUOTA_EXHAUSTED"


def model_quota_exhausted_message(structured: dict[str, Any]) -> str:
    return str(
        structured.get("reason_not_surfaced")
        or "The Health Coach has reached its current model usage limit. Please try again later."
    )


def _exception_type_name(item: BaseException) -> str:
    module = type(item).__module__ or ""
    return f"{module}.{type(item).__name__}".lower()


def _is_evidence_provider_error(exc: BaseException) -> bool:
    openai_types: tuple[type, ...] = ()
    pinecone_types: tuple[type, ...] = ()
    try:
        from openai import OpenAIError

        openai_types = (OpenAIError,)
    except ImportError:  # pragma: no cover
        pass
    try:
        from pinecone.exceptions import PineconeException

        pinecone_types = (PineconeException,)
    except ImportError:  # pragma: no cover
        pass

    for item in iter_exception_chain(exc):
        if openai_types and isinstance(item, openai_types):
            return True
        if pinecone_types and isinstance(item, pinecone_types):
            return True
        type_name = _exception_type_name(item)
        if "openai" in type_name or "pinecone" in type_name:
            return True
        if isinstance(item, RuntimeError):
            message = str(item).lower()
            if (
                "pinecone" in message
                or "openai embedding" in message
                or "embedding request failed" in message
            ):
                return True
    return False


def _is_gemini_provider_error(exc: BaseException) -> bool:
    try:
        from google.genai.errors import APIError, ClientError, ServerError
    except ImportError:  # pragma: no cover
        APIError = ClientError = ServerError = ()  # type: ignore[misc, assignment]
    for item in iter_exception_chain(exc):
        if APIError and isinstance(item, (APIError, ClientError, ServerError)):
            return True
        type_name = _exception_type_name(item)
        if "google.genai" in type_name or "google.adk" in type_name:
            return True
    return False


def user_facing_analyze_error(exc: BaseException) -> str:
    """Map a provider exception to a fixed UI sentence. Never returns str(exc)."""
    if is_transient_gemini_unavailable(exc):
        return GEMINI_BUSY_UI_MESSAGE
    if is_gemini_quota_exhausted(exc):
        return "The Health Coach has reached its current model usage limit. Please try again later."
    if _is_evidence_provider_error(exc):
        return EVIDENCE_UNAVAILABLE_UI_MESSAGE
    if _is_gemini_provider_error(exc):
        return GEMINI_UNAVAILABLE_UI_MESSAGE
    return ANALYSIS_FAILED_UI_MESSAGE


def analyze_health_status_message(structured: dict[str, Any]) -> str | None:
    """User-facing copy for already-translated runner statuses. TRACE text is unchanged."""
    if is_temporary_model_unavailable(structured):
        return GEMINI_BUSY_UI_MESSAGE
    if is_model_quota_exhausted(structured):
        return model_quota_exhausted_message(structured)
    return None


def is_safe_analyze_error_message(message: str) -> bool:
    return message in _SAFE_ANALYZE_MESSAGES or message.startswith(
        "The Health Coach has reached its current model usage limit."
    )


def _format_fact_line(fact: dict[str, Any]) -> str:
    metric = fact.get("metric") or "unknown"
    role = fact.get("role") or "supporting"
    direction = fact.get("direction")
    percent = fact.get("percent_change")
    parts = [f"- {metric} [{role}]"]
    if direction:
        parts.append(str(direction))
    if percent is not None and role != "spread_context":
        parts.append(f"{percent}%")
    if role == "spread_context":
        ratio = fact.get("spread_ratio")
        spread_min = fact.get("min")
        spread_max = fact.get("max")
        if ratio is not None:
            parts.append(f"spread_ratio={ratio}")
        if spread_min is not None and spread_max is not None:
            parts.append(f"{spread_min}–{spread_max}")
    return " ".join(parts)


def format_health_coach_output(structured: dict[str, Any]) -> str:
    """Backend/demo formatting: primary → subtext → quote → rationale → rec → facts."""
    status = str(structured.get("status") or "")
    if status == "NO_SIGNIFICANT_NEW_PATTERN":
        return str(
            structured.get("reason_not_surfaced")
            or structured.get("insight")
            or "No significant new pattern in the current comparison window "
            "requires further investigation."
        )
    if status == "BOUNDED_FAILURE":
        return "Analysis stopped after reaching the bounded step limit. No health guidance was returned."
    if status == "GUARD_BLOCKED":
        return "A safety guard blocked the candidate response. No health guidance was returned."
    if is_temporary_model_unavailable(structured):
        return temporary_unavailable_message(structured)
    if is_model_quota_exhausted(structured):
        return model_quota_exhausted_message(structured)

    sections: list[str] = []
    primary = structured.get("primary_message")
    if isinstance(primary, str) and primary.strip():
        sections.append(f"PRIMARY MESSAGE\n{primary.strip()}")
    subtext = structured.get("subtext")
    if isinstance(subtext, str) and subtext.strip():
        sections.append(f"SUBTEXT\n{subtext.strip()}")
    quote = structured.get("motivational_quote")
    if isinstance(quote, str) and quote.strip():
        sections.append(f"MOTIVATIONAL QUOTE\n{quote.strip()}")
    insight = structured.get("insight")
    if isinstance(insight, str) and insight.strip():
        sections.append(f"RATIONALE\n{insight.strip()}")
    recommendation = structured.get("recommendation")
    if isinstance(recommendation, str) and recommendation.strip():
        sections.append(f"RECOMMENDATION\n{recommendation.strip()}")
    facts = structured.get("supporting_metric_facts") or []
    if facts:
        lines = ["SUPPORTING FACTS"]
        lines.extend(_format_fact_line(item) for item in facts if isinstance(item, dict))
        sections.append("\n".join(lines))
    return "\n\n".join(sections) if sections else (
        "No significant new pattern in the current comparison window "
        "requires further investigation."
    )
