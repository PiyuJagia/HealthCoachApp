"""Run the Google ADK Health Coach agent with trace capture and output guard."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent.agent import (
    AGENT_NAME,
    MAX_LLM_CALLS,
    MODEL,
    build_health_coach_agent,
    build_review_prompt,
)
from agent.events import extract_final_text
from agent.instructions import OUTPUT_JSON_REMINDER
from agent.schemas import (
    HealthCoachStatus,
    bounded_failure_result,
    guard_blocked_result,
    health_coach_result_from_payload,
    parse_agent_json_payload,
)
from agent.tools import RunContext
from agent.trace import PersistedAgentRun, persist_agent_run
from app.output_guard import check_final_output
from evals.trace_schema import FinalGuardTrace, GenerationTrace, TraceRecord, empty_trace
from rag.evidence_policy import AuthorizationVerdict, EvidencePolicyDecision

load_dotenv()


@dataclass
class HealthCoachRunResult:
    structured: dict[str, Any]
    activity_log: list[dict[str, Any]]
    trace_path: Path
    latency_ms: int
    raw_final_text: str | None = None
    guard_passed: bool = True
    guard_violations: list[str] | None = None

    @property
    def status(self) -> str:
        return str(self.structured.get("status") or "")


def _empty_policy_decision() -> EvidencePolicyDecision:
    return EvidencePolicyDecision(
        overall_verdict=AuthorizationVerdict.SURFACE,
        evidence_authorized=False,
        recommendation_authorized=False,
        reasons=tuple(),
        relationship_decisions=tuple(),
        general_evidence=tuple(),
        authorized_results=tuple(),
        suppressed_relationship_ids=tuple(),
    )


def _guard_text(result_payload: dict[str, Any]) -> str:
    parts = [
        str(result_payload.get("theme") or ""),
        str(result_payload.get("insight") or ""),
        str(result_payload.get("recommendation") or ""),
        str(result_payload.get("reason_not_surfaced") or ""),
    ]
    return "\n".join(part for part in parts if part.strip())


def _apply_output_guard(
    *,
    context: RunContext,
    structured: dict[str, Any],
    scenario_id: str,
    user_id: int,
    as_of_date: str,
) -> dict[str, Any]:
    decision = context.last_policy_decision or _empty_policy_decision()
    guard = check_final_output(_guard_text(structured), decision=decision)
    context.final_guard = FinalGuardTrace(
        passed=guard.passed,
        violations=list(guard.violations),
    )
    if guard.passed:
        return structured
    blocked = guard_blocked_result(
        scenario_id=scenario_id,
        user_id=user_id,
        as_of_date=as_of_date,
        violations=list(guard.violations),
    )
    return blocked.to_dict()


async def _run_agent_async(
    *,
    scenario_id: str,
    user_id: int,
    as_of_date: date,
) -> HealthCoachRunResult:
    context = RunContext(scenario_id=scenario_id, user_id=user_id, as_of_date=as_of_date)
    trace = empty_trace(
        scenario_id=scenario_id,
        user_id=user_id,
        as_of_date=as_of_date.isoformat(),
    )
    agent = build_health_coach_agent(context)
    service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="health_coach", session_service=service)
    session = await service.create_session(app_name="health_coach", user_id=str(user_id))
    prompt = build_review_prompt(scenario_id=scenario_id, user_id=user_id, as_of_date=as_of_date)
    message = types.Content(role="user", parts=[types.Part(text=f"{prompt}\n\n{OUTPUT_JSON_REMINDER}")])
    run_config = RunConfig(max_llm_calls=MAX_LLM_CALLS)

    raw_final_text: str | None = None
    started = time.perf_counter()
    try:
        async for event in runner.run_async(
            user_id=str(user_id),
            session_id=session.id,
            new_message=message,
            run_config=run_config,
        ):
            final = extract_final_text(event)
            if final:
                raw_final_text = final
    except LlmCallsLimitExceededError:
        latency_ms = round((time.perf_counter() - started) * 1000)
        blocked = bounded_failure_result(
            scenario_id=scenario_id,
            user_id=user_id,
            as_of_date=as_of_date.isoformat(),
            reason="Max LLM call limit reached before a final response was produced.",
        )
        trace.final_output = blocked.user_facing_summary()
        trace.final_guard = FinalGuardTrace(passed=True, violations=[])
        persisted = PersistedAgentRun(
            trace=trace,
            activity_log=context.activity_log,
            structured_result=blocked.to_dict(),
            latency_ms=latency_ms,
            model=MODEL,
        )
        path = persist_agent_run(persisted)
        return HealthCoachRunResult(
            structured=blocked.to_dict(),
            activity_log=context.activity_log,
            trace_path=path,
            latency_ms=latency_ms,
            raw_final_text=None,
            guard_passed=True,
            guard_violations=[],
        )

    latency_ms = round((time.perf_counter() - started) * 1000)
    structured: dict[str, Any]
    if raw_final_text:
        try:
            payload = parse_agent_json_payload(raw_final_text)
            result = health_coach_result_from_payload(
                payload,
                scenario_id=scenario_id,
                user_id=user_id,
                as_of_date=as_of_date.isoformat(),
            )
            structured = _apply_output_guard(
                context=context,
                structured=result.to_dict(),
                scenario_id=scenario_id,
                user_id=user_id,
                as_of_date=as_of_date.isoformat(),
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            structured = guard_blocked_result(
                scenario_id=scenario_id,
                user_id=user_id,
                as_of_date=as_of_date.isoformat(),
                violations=["invalid_agent_json"],
            ).to_dict()
            context.final_guard = FinalGuardTrace(passed=False, violations=["invalid_agent_json"])
    else:
        structured = bounded_failure_result(
            scenario_id=scenario_id,
            user_id=user_id,
            as_of_date=as_of_date.isoformat(),
            reason="Agent produced no final response.",
        ).to_dict()
        context.final_guard = FinalGuardTrace(passed=True, violations=[])

    insight_text = structured.get("insight") or structured.get("reason_not_surfaced") or ""
    context.generation = GenerationTrace(model_name=MODEL, final_insight=str(insight_text))
    context.record_final(f"Completed with status={structured.get('status')}.")

    trace.candidate_signals = context.candidate_signals
    trace.tool_calls = context.tool_calls
    trace.retrieval = context.retrieval
    trace.policy = context.policy
    trace.generation = context.generation
    trace.final_guard = context.final_guard
    trace.final_output = json.dumps(structured, sort_keys=True)

    persisted = PersistedAgentRun(
        trace=trace,
        activity_log=context.activity_log,
        structured_result=structured,
        latency_ms=latency_ms,
        model=MODEL,
    )
    path = persist_agent_run(persisted)
    return HealthCoachRunResult(
        structured=structured,
        activity_log=context.activity_log,
        trace_path=path,
        latency_ms=latency_ms,
        raw_final_text=raw_final_text,
        guard_passed=bool(context.final_guard.passed if context.final_guard else True),
        guard_violations=list(context.final_guard.violations if context.final_guard else []),
    )


def run_health_review(
    *,
    scenario_id: str,
    user_id: int,
    as_of_date: date,
) -> HealthCoachRunResult:
    return asyncio.run(
        _run_agent_async(
            scenario_id=scenario_id,
            user_id=user_id,
            as_of_date=as_of_date,
        )
    )
