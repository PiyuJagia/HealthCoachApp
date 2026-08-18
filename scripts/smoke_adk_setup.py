"""Minimal ADK + Gemini smoke test (Phase E3.0). Not part of the offline test suite.

Demonstrates:
  user message -> model tool call -> tool result -> final response

Observable ADK event fields (for future evals/trace_schema.py mapping):
  - event.author            agent name
  - event.id                unique event id
  - event.timestamp         float epoch seconds
  - event.invocation_id     run-scoped invocation id
  - part.function_call      ACT: {name, args}
  - part.function_response  OBSERVE: {name, response}
  - part.text               user-visible model text (FINAL when is_final_response())
  - event.is_final_response() marks a complete user-facing answer

Thought parts (part.thought=True) are omitted here; they are not captured as traces.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

MODEL = "gemini-3.6-flash"
MAX_LLM_CALLS = 8


def ping_setup(value: str) -> dict:
    """Return a deterministic setup ping for ADK smoke testing only."""
    return {"echo": value, "status": "ok"}


setup_agent = Agent(
    name="setup_smoke_agent",
    model=MODEL,
    instruction=(
        "You are a setup verification agent. When asked to verify ADK, "
        "call ping_setup with value 'ADK_SETUP_OK', then respond with exactly: ADK_SETUP_OK"
    ),
    tools=[ping_setup],
)


def _classify_part(part: types.Part, *, is_final: bool) -> dict | None:
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
            "text": text[:300],
        }
    if is_thought:
        return {"phase": "DECISION", "note": "model_turn (thought content omitted)"}
    return None


async def run_smoke() -> dict:
    service = InMemorySessionService()
    runner = Runner(agent=setup_agent, app_name="setup_smoke", session_service=service)
    session = await service.create_session(app_name="setup_smoke", user_id="smoke")
    message = types.Content(
        role="user",
        parts=[types.Part(text="Verify ADK setup with the ping_setup tool.")],
    )
    run_config = RunConfig(max_llm_calls=MAX_LLM_CALLS)

    trace: list[dict] = []
    final_text: str | None = None
    started = time.perf_counter()

    async for event in runner.run_async(
        user_id="smoke",
        session_id=session.id,
        new_message=message,
        run_config=run_config,
    ):
        author = getattr(event, "author", "unknown")
        is_final = event.is_final_response()
        if event.content and event.content.parts:
            for part in event.content.parts:
                step = _classify_part(part, is_final=is_final)
                if step:
                    trace.append({"author": author, **step})
        if is_final and event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None) and not getattr(part, "thought", False):
                    final_text = part.text

    latency_ms = round((time.perf_counter() - started) * 1000)
    success = bool(final_text and "ADK_SETUP_OK" in final_text)
    saw_tool_call = any(item.get("phase") == "ACT" for item in trace)
    saw_tool_result = any(item.get("phase") == "OBSERVE" for item in trace)

    return {
        "model": MODEL,
        "max_llm_calls": MAX_LLM_CALLS,
        "success": success and saw_tool_call and saw_tool_result,
        "final_text": final_text,
        "latency_ms": latency_ms,
        "trace": trace,
    }


def main() -> int:
    if not os.getenv("GOOGLE_API_KEY", "").strip():
        print("FAIL: GOOGLE_API_KEY is not set in the environment.")
        return 1

    try:
        result = asyncio.run(run_smoke())
    except Exception as exc:  # noqa: BLE001 — smoke test must surface full errors
        print("FAIL: ADK smoke run raised an exception.")
        print(repr(exc))
        return 1

    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
