"""Offline tests for Health Coach ADK agent wiring."""

from __future__ import annotations

import json
import unittest
from datetime import date
from unittest.mock import AsyncMock, patch

from agent.agent import AGENT_NAME, MAX_LLM_CALLS, MODEL, build_health_coach_agent, build_review_prompt
from agent.display import format_activity_lines, summarize_trend_signals
from agent.events import classify_part
from agent.runner import _apply_output_guard, _empty_policy_decision, _guard_text
from agent.schemas import (
    HealthCoachResult,
    HealthCoachStatus,
    bounded_failure_result,
    guard_blocked_result,
    health_coach_result_from_payload,
    parse_agent_json_payload,
)
from agent.tools import RunContext, build_tools
from agent.trace import PersistedAgentRun, persist_agent_run
from evals.trace_schema import empty_trace, sanitize_for_trace
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.genai import types
from rag.evidence_policy import AuthorizationVerdict, EvidencePolicyDecision


class _FakePart:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class AgentBuildTests(unittest.TestCase):
    def test_build_health_coach_agent_without_network(self) -> None:
        context = RunContext(scenario_id="day30", user_id=1, as_of_date=date(2026, 6, 18))
        agent = build_health_coach_agent(context)
        self.assertEqual(agent.name, AGENT_NAME)
        self.assertEqual(agent.model, MODEL)

    def test_review_prompt_includes_scenario_context(self) -> None:
        prompt = build_review_prompt(scenario_id="day60", user_id=7, as_of_date=date(2026, 7, 17))
        self.assertIn("day60", prompt)
        self.assertIn("user_id=7", prompt)


class EventMappingTests(unittest.TestCase):
    def test_maps_act_event(self) -> None:
        part = _FakePart(function_call=types.FunctionCall(name="get_trend_signals", args={"x": 1}))
        mapped = classify_part(part, is_final=False)
        self.assertIsNotNone(mapped)
        assert mapped is not None
        self.assertEqual(mapped["phase"], "ACT")
        self.assertEqual(mapped["tool"], "get_trend_signals")

    def test_maps_observe_event(self) -> None:
        part = _FakePart(function_response=types.FunctionResponse(name="retrieve_authorized_evidence", response={"ok": True}))
        mapped = classify_part(part, is_final=False)
        self.assertIsNotNone(mapped)
        assert mapped is not None
        self.assertEqual(mapped["phase"], "OBSERVE")

    def test_hidden_thought_parts_are_not_persisted(self) -> None:
        part = _FakePart(text="secret reasoning", thought=True)
        self.assertIsNone(classify_part(part, is_final=False))


class ToolContextTests(unittest.TestCase):
    @patch("agent.tools.agent_tools.get_trend_signals")
    def test_get_trend_signals_records_act_and_observe(self, mock_trends) -> None:
        mock_trends.return_value = {
            "as_of_date": "2026-06-18",
            "trends": [
                {
                    "metric": "sleep_duration_hours",
                    "direction": "decreasing",
                    "data_sufficient": True,
                    "percent_change": -5.0,
                }
            ],
        }
        context = RunContext(scenario_id="day30", user_id=1, as_of_date=date(2026, 6, 18))
        get_trend_signals, _ = build_tools(context)
        payload = get_trend_signals()
        self.assertIn("trends", payload)
        phases = [step["phase"] for step in context.activity_log]
        self.assertIn("ACT", phases)
        self.assertIn("OBSERVE", phases)
        self.assertIn("DECISION", phases)
        self.assertEqual(context.tool_calls[0].tool_name, "get_trend_signals")

    @patch("agent.tools.agent_tools.evaluate_evidence_policy")
    @patch("agent.tools.agent_tools.retrieve_evidence")
    def test_retrieve_authorized_evidence_records_policy(self, mock_retrieve, mock_policy) -> None:
        mock_retrieve.return_value = []
        mock_policy.return_value = EvidencePolicyDecision(
            overall_verdict=AuthorizationVerdict.QUALIFY,
            evidence_authorized=True,
            recommendation_authorized=False,
            reasons=("qualified",),
            relationship_decisions=tuple(),
            general_evidence=tuple(),
            authorized_results=tuple(),
            suppressed_relationship_ids=tuple(),
        )
        context = RunContext(scenario_id="day60", user_id=1, as_of_date=date(2026, 7, 17))
        _, retrieve_authorized_evidence = build_tools(context)
        result = retrieve_authorized_evidence("exercise and resting heart rate")
        self.assertEqual(result["overall_verdict"], "QUALIFY")
        self.assertIsNotNone(context.policy)
        self.assertEqual(context.policy.overall_verdict, "QUALIFY")


class SchemaAndGuardTests(unittest.TestCase):
    def test_structured_result_schema_validates(self) -> None:
        payload = {
            "scenario_id": "day90",
            "user_id": 1,
            "as_of_date": "2026-08-17",
            "status": "NO_SIGNIFICANT_NEW_PATTERN",
            "reason_not_surfaced": "Major tracked metrics remain relatively stable.",
        }
        result = health_coach_result_from_payload(payload, scenario_id="day90", user_id=1, as_of_date="2026-08-17")
        self.assertEqual(result.status, HealthCoachStatus.NO_SIGNIFICANT_NEW_PATTERN.value)

    def test_no_significant_new_pattern_is_valid_status(self) -> None:
        self.assertIn("NO_SIGNIFICANT_NEW_PATTERN", {item.value for item in HealthCoachStatus})

    def test_no_meaningful_insight_is_not_current_status(self) -> None:
        self.assertNotIn("NO_MEANINGFUL_INSIGHT", {item.value for item in HealthCoachStatus})

    def test_parse_agent_json_payload_strips_markdown_fence(self) -> None:
        text = "```json\n{\"status\": \"INSIGHT\"}\n```"
        payload = parse_agent_json_payload(text)
        self.assertEqual(payload["status"], "INSIGHT")

    def test_guard_is_applied_before_success_return(self) -> None:
        context = RunContext(scenario_id="day30", user_id=1, as_of_date=date(2026, 6, 18))
        structured = HealthCoachResult(
            scenario_id="day30",
            user_id=1,
            as_of_date="2026-06-18",
            status="RECOMMENDATION",
            insight="You should overhaul your routine immediately.",
            recommendation="You should overhaul your routine immediately.",
            recommendation_authorized=False,
        ).to_dict()
        guarded = _apply_output_guard(
            context=context,
            structured=structured,
            scenario_id="day30",
            user_id=1,
            as_of_date="2026-06-18",
        )
        self.assertEqual(guarded["status"], HealthCoachStatus.GUARD_BLOCKED.value)
        self.assertIsNotNone(context.final_guard)
        assert context.final_guard is not None
        self.assertFalse(context.final_guard.passed)

    def test_guard_text_concatenates_user_facing_fields(self) -> None:
        text = _guard_text({"theme": "Sleep", "insight": "Sleep declined.", "recommendation": None})
        self.assertIn("Sleep declined.", text)


class TracePersistenceTests(unittest.TestCase):
    def test_trace_file_sanitization(self) -> None:
        trace = empty_trace(scenario_id="day30", user_id=1, as_of_date="2026-06-18")
        record = PersistedAgentRun(
            trace=trace,
            activity_log=[{"phase": "ACT", "tool": "get_trend_signals", "openai_api_key": "secret"}],
            structured_result={"status": "NO_SIGNIFICANT_NEW_PATTERN"},
            latency_ms=10,
            model=MODEL,
        )
        payload = record.to_dict()
        sanitized = sanitize_for_trace(payload)
        self.assertEqual(sanitized["activity_log"][0]["openai_api_key"], "[REDACTED]")

    def test_persist_agent_run_writes_json(self) -> None:
        import tempfile
        from pathlib import Path

        trace = empty_trace(scenario_id="day30", user_id=1, as_of_date="2026-06-18")
        record = PersistedAgentRun(
            trace=trace,
            structured_result={"status": "NO_SIGNIFICANT_NEW_PATTERN"},
            latency_ms=5,
            model=MODEL,
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch("agent.trace.TRACES_DIR", Path(tmp)):
                path = persist_agent_run(record)
            self.assertTrue(path.exists())
            self.assertTrue(str(path).endswith(".json"))


class BoundedFailureTests(unittest.TestCase):
    def test_bounded_failure_result_status(self) -> None:
        result = bounded_failure_result(
            scenario_id="day75",
            user_id=1,
            as_of_date="2026-08-01",
            reason="limit hit",
        )
        self.assertEqual(result.status, HealthCoachStatus.BOUNDED_FAILURE.value)

    def test_llm_limit_error_type_available(self) -> None:
        self.assertTrue(issubclass(LlmCallsLimitExceededError, Exception))


class DisplayHelperTests(unittest.TestCase):
    def test_summarize_trend_signals(self) -> None:
        rows = summarize_trend_signals(
            {"trends": [{"metric": "hrv_sdnn_ms", "direction": "stable", "data_sufficient": True}]}
        )
        self.assertEqual(rows[0]["metric"], "hrv_sdnn_ms")

    def test_format_activity_lines(self) -> None:
        lines = format_activity_lines(
            [
                {"phase": "ACT", "tool": "get_trend_signals", "arguments": {}},
                {"phase": "OBSERVE", "tool": "get_trend_signals", "summary": {"trend_count": 5}},
            ]
        )
        self.assertTrue(any(line.startswith("ACT:") for line in lines))
        self.assertTrue(any(line.startswith("OBSERVE:") for line in lines))


class RunnerAsyncTests(unittest.IsolatedAsyncioTestCase):
    @patch("agent.runner.Runner")
    @patch("agent.runner.InMemorySessionService")
    async def test_runner_fails_closed_on_empty_final_response(self, _service, mock_runner_cls) -> None:
        from agent.runner import _run_agent_async

        class _Event:
            def is_final_response(self) -> bool:
                return False

        async def _empty_events(*args, **kwargs):
            if False:  # pragma: no cover - async generator stub
                yield _Event()

        service_instance = _service.return_value
        service_instance.create_session = AsyncMock(return_value=type("S", (), {"id": "sess"})())
        runner_instance = mock_runner_cls.return_value
        runner_instance.run_async = _empty_events

        with patch("agent.runner.persist_agent_run") as mock_persist:
            mock_persist.return_value = type("P", (), {"stem": "run"})()
            result = await _run_agent_async(
                scenario_id="day30",
                user_id=1,
                as_of_date=date(2026, 6, 18),
            )
        self.assertEqual(result.status, HealthCoachStatus.BOUNDED_FAILURE.value)


if __name__ == "__main__":
    unittest.main()
