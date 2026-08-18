"""Parse observable ADK events without logging hidden thoughts."""

from __future__ import annotations

from typing import Any

from google.genai import types


def classify_part(part: types.Part, *, is_final: bool) -> dict[str, Any] | None:
    function_call = getattr(part, "function_call", None)
    function_response = getattr(part, "function_response", None)
    text = getattr(part, "text", None)
    is_thought = bool(getattr(part, "thought", False))

    if function_call:
        return {
            "phase": "ACT",
            "tool": function_call.name,
            "args": dict(function_call.args or {}),
        }
    if function_response:
        return {
            "phase": "OBSERVE",
            "tool": function_response.name,
            "result": str(function_response.response)[:500],
        }
    if text and not is_thought:
        return {
            "phase": "FINAL" if is_final else "TEXT",
            "text": text[:500],
        }
    if is_thought:
        return None
    return None


def extract_final_text(event: Any) -> str | None:
    if not event.is_final_response() or not event.content or not event.content.parts:
        return None
    for part in event.content.parts:
        text = getattr(part, "text", None)
        if text and not getattr(part, "thought", False):
            return text
    return None
