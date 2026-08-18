"""Shared formatting helpers for CLI and Streamlit demo views."""

from __future__ import annotations

from typing import Any


def summarize_trend_signals(candidate_signals: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in candidate_signals.get("trends") or []:
        rows.append(
            {
                "metric": item.get("metric"),
                "direction": item.get("direction"),
                "data_sufficient": item.get("data_sufficient"),
                "percent_change": item.get("percent_change"),
                "current_value": item.get("current_value"),
                "baseline_value": item.get("baseline_value"),
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
