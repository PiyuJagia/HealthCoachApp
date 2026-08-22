"""Offline tests for F4.2 ADK pre-model TRACE observability."""

from __future__ import annotations

import json
import unittest
from datetime import date
from unittest.mock import patch

from google.adk.models.llm_request import LlmRequest
from google.genai import types

from agent.agent import AGENT_NAME, MODEL, build_health_coach_agent, build_review_prompt
from agent.instructions import HEALTH_COACH_INSTRUCTIONS
from agent.model_observe import (
    assess_weekly_summary_bypass,
    bind_model_observation_callbacks,
    capture_after_model,
    capture_before_model,
    observe_llm_request,
)
from agent.tools import RunContext
from agent.trace import PersistedAgentRun, persist_agent_run
from evals.trace_schema import (
    CAPTURE_FIDELITY_ADK_PRE_MODEL,
    CAPTURE_FIDELITY_EXACT_PROVIDER,
    ORIGIN_DETERMINISTIC_ANALYTICS,
    ORIGIN_EVIDENCE_RAG,
    ORIGIN_HEALTH_TREND_TOOL,
    ORIGIN_SYSTEM_INSTRUCTIONS,
    ORIGIN_USER_SCENARIO_INPUT,
    ORIGIN_WEEKLY_SUMMARY,
    empty_trace,
    sanitize_for_trace,
)


def _trend_payload() -> dict:
    return {
        "as_of_date": "2026-07-13",
        "gap_caveat_required": True,
        "as_of_any_daily_metric_available": True,
        "trends": [
            {
                "metric": "hrv_sdnn_ms",
                "cadence": "daily",
                "direction": "improving",
                "percent_change": 6.05,
                "as_of_date_available": False,
                "coverage_ratio": 0.7143,
                "data_maturity_state": "ESTABLISHED_TREND",
                "gap_caveat_required": True,
                "claim_eligibility": {
                    "snapshot_allowed": True,
                    "early_pattern_allowed": True,
                    "trend_allowed": True,
                    "recommendation_support_allowed": True,
                    "recommendation_basis": "established_trend",
                },
            }
        ],
        "weekly_summaries": [
            {
                "week_start": "2026-07-07",
                "week_end": "2026-07-13",
                "average_hrv_sdnn_ms": 32.1,
                "average_sleep_hours": 7.1,
                "coverage": {
                    "hrv_sdnn_ms": {
                        "observation_count": 5,
                        "expected_observation_count": 7,
                        "coverage_ratio": 0.7143,
                        "as_of_date_available": False,
                        "gap_caveat_required": True,
                    }
                },
            }
        ],
        "openai_api_key": "sk-secret-should-redact",
    }


def _evidence_payload() -> dict:
    return {
        "query": "sleep decline",
        "retrieval_count": 1,
        "authorized_count": 1,
        "overall_verdict": "QUALIFY",
        "evidence_authorized": True,
        "recommendation_authorized": False,
        "policy": {"reasons": ["qualified_evidence_only"]},
        "retrieval": [{"relationship_id": "R-01", "vector_id": "vec-1"}],
    }


def _sample_request() -> LlmRequest:
    prompt = build_review_prompt(scenario_id="HC-EVAL-D1", user_id=1, as_of_date=date(2026, 7, 13))
    return LlmRequest(
        model=MODEL,
        contents=[
            types.Content(role="user", parts=[types.Part(text=prompt)]),
            types.Content(
                role="model",
                parts=[
                    types.Part(text="hidden chain of thought", thought=True),
                    types.Part(function_call=types.FunctionCall(name="get_trend_signals", args={})),
                ],
            ),
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name="get_trend_signals",
                            response=_trend_payload(),
                        )
                    )
                ],
            ),
            types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            name="retrieve_authorized_evidence",
                            args={"query": "sleep decline"},
                        )
                    )
                ],
            ),
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name="retrieve_authorized_evidence",
                            response=_evidence_payload(),
                        )
                    )
                ],
            ),
        ],
        config=types.GenerateContentConfig(
            system_instruction=HEALTH_COACH_INSTRUCTIONS,
            temperature=0.2,
            max_output_tokens=2048,
            http_options=types.HttpOptions(
                headers={
                    "Authorization": "Bearer secret-token",
                    "x-goog-api-key": "abc123",
                }
            ),
        ),
    )


class ModelCallObservationTests(unittest.TestCase):
    def test_model_call_structure_is_generated(self) -> None:
        captured = observe_llm_request(_sample_request(), call_index=1)
        payload = captured.to_dict()
        self.assertEqual(payload["call_index"], 1)
        self.assertEqual(payload["model"], MODEL)
        self.assertEqual(payload["capture_fidelity"], CAPTURE_FIDELITY_ADK_PRE_MODEL)
        self.assertNotEqual(payload["capture_fidelity"], CAPTURE_FIDELITY_EXACT_PROVIDER)
        self.assertIn("conversation_messages", payload)
        self.assertIn("provenance", payload)
        self.assertTrue(payload["conversation_messages"])

    def test_major_context_sources_are_identifiable(self) -> None:
        captured = observe_llm_request(_sample_request(), call_index=0)
        origins = {item.origin for item in captured.provenance if item.present}
        self.assertIn(ORIGIN_SYSTEM_INSTRUCTIONS, origins)
        self.assertIn(ORIGIN_USER_SCENARIO_INPUT, origins)
        self.assertIn(ORIGIN_DETERMINISTIC_ANALYTICS, origins)
        self.assertIn(ORIGIN_WEEKLY_SUMMARY, origins)
        self.assertIn(ORIGIN_EVIDENCE_RAG, origins)
        lifestyle = next(item for item in captured.provenance if item.component == "lifestyle_context")
        self.assertFalse(lifestyle.present)
        self.assertIn("HC-EVAL-D1", captured.user_scenario_input or "")
        self.assertIn("Health Coach", captured.system_instruction or "")
        self.assertIn("recommendation_authorized", captured.to_dict()["system_instruction"])

    def test_maturity_fields_survive_into_observable_context(self) -> None:
        captured = observe_llm_request(_sample_request(), call_index=0)
        assert captured.trend_maturity_visible is not None
        hrv = captured.trend_maturity_visible["metrics"][0]
        self.assertEqual(hrv["data_maturity_state"], "ESTABLISHED_TREND")
        self.assertTrue(hrv["claim_eligibility"]["trend_allowed"])
        self.assertFalse(hrv["as_of_date_available"])
        self.assertTrue(hrv["gap_caveat_required"])

    def test_tool_result_provenance_is_preserved(self) -> None:
        captured = observe_llm_request(_sample_request(), call_index=0)
        names = [item["tool_name"] for item in captured.tool_results_visible]
        self.assertEqual(names, ["get_trend_signals", "retrieve_authorized_evidence"])
        self.assertEqual(captured.tool_results_visible[0]["origin"], ORIGIN_HEALTH_TREND_TOOL)
        self.assertEqual(captured.tool_results_visible[1]["origin"], ORIGIN_EVIDENCE_RAG)
        self.assertEqual(captured.rag_evidence_visible["overall_verdict"], "QUALIFY")

    def test_secrets_and_headers_are_not_captured(self) -> None:
        captured = observe_llm_request(_sample_request(), call_index=0)
        serialized = json.dumps(captured.to_dict())
        self.assertNotIn("Bearer secret-token", serialized)
        self.assertNotIn("abc123", serialized)
        self.assertNotIn("sk-secret-should-redact", serialized)
        self.assertEqual(captured.generation_config, {"temperature": 0.2, "max_output_tokens": 2048})
        self.assertNotIn("http_options", captured.to_dict())
        tool_payload = captured.tool_results_visible[0]["payload"]
        self.assertEqual(tool_payload["openai_api_key"], "[REDACTED]")

    def test_hidden_thoughts_are_not_captured(self) -> None:
        captured = observe_llm_request(_sample_request(), call_index=0)
        self.assertGreaterEqual(captured.omitted_thought_parts, 1)
        serialized = json.dumps(captured.to_dict())
        self.assertNotIn("hidden chain of thought", serialized)

    def test_callback_does_not_alter_request_or_skip_model(self) -> None:
        context = RunContext(scenario_id="HC-EVAL-D1", user_id=1, as_of_date=date(2026, 7, 13))
        request = _sample_request()
        original_len = len(request.contents)
        original_instruction = request.config.system_instruction
        result = capture_before_model(callback_context=None, llm_request=request, context=context)
        self.assertIsNone(result)
        self.assertEqual(len(request.contents), original_len)
        self.assertEqual(request.config.system_instruction, original_instruction)
        self.assertEqual(len(context.model_calls), 1)

    def test_after_model_skips_thoughts_and_returns_none(self) -> None:
        context = RunContext(scenario_id="HC-EVAL-D1", user_id=1, as_of_date=date(2026, 7, 13))
        capture_before_model(callback_context=None, llm_request=_sample_request(), context=context)

        class _Response:
            content = types.Content(
                role="model",
                parts=[
                    types.Part(text="private reasoning", thought=True),
                    types.Part(function_call=types.FunctionCall(name="get_trend_signals", args={})),
                ],
            )

        result = capture_after_model(callback_context=None, llm_response=_Response(), context=context)
        self.assertIsNone(result)
        visible = context.model_calls[0].visible_response
        assert visible is not None
        self.assertEqual(visible["function_calls"], ["get_trend_signals"])
        self.assertNotIn("private reasoning", json.dumps(visible))

    def test_agent_behavior_contract_unchanged(self) -> None:
        context = RunContext(scenario_id="day30", user_id=1, as_of_date=date(2026, 6, 18))
        agent = build_health_coach_agent(context)
        self.assertEqual(agent.name, AGENT_NAME)
        self.assertEqual(agent.model, MODEL)
        self.assertEqual(agent.instruction, HEALTH_COACH_INSTRUCTIONS)
        self.assertIsNotNone(agent.before_model_callback)
        self.assertIsNotNone(agent.after_model_callback)
        self.assertEqual(
            {getattr(tool, "name", getattr(tool, "__name__", "")) for tool in agent.tools},
            {"get_trend_signals", "get_lifestyle_context", "retrieve_authorized_evidence"},
        )

    def test_weekly_summaries_without_semantics_are_bypass_capable(self) -> None:
        risk = assess_weekly_summary_bypass(_trend_payload())
        self.assertTrue(risk["present"])
        self.assertTrue(risk["bypass_possible"])
        self.assertFalse(risk["has_claim_semantics"])
        self.assertEqual(risk["recommended_remediation"], "align_weekly_claim_semantics")

    def test_weekly_summaries_with_aligned_semantics_close_bypass(self) -> None:
        payload = _trend_payload()
        payload["weekly_summaries"][0]["as_of_aligned"] = True
        payload["weekly_summaries"][0]["coverage"]["hrv_sdnn_ms"]["claim_semantics"] = {
            "summary_value_allowed": True,
            "summary_comparison_allowed": True,
            "summary_recommendation_support_allowed": True,
        }
        risk = assess_weekly_summary_bypass(payload)
        self.assertFalse(risk["bypass_possible"])
        self.assertTrue(risk["has_claim_semantics"])

    def test_model_call_preserves_weekly_summary_provenance(self) -> None:
        payload = _trend_payload()
        payload["weekly_summaries"][0]["as_of_aligned"] = True
        payload["weekly_summaries"][0]["coverage"]["hrv_sdnn_ms"]["claim_semantics"] = {
            "summary_value_allowed": True,
            "summary_comparison_allowed": True,
            "summary_recommendation_support_allowed": False,
        }
        request = _sample_request()
        request.contents[-3] = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name="get_trend_signals",
                        response=payload,
                    )
                )
            ],
        )
        captured = observe_llm_request(request, call_index=0)
        assert captured.weekly_summaries_visible is not None
        self.assertEqual(captured.weekly_summaries_visible["origin"], ORIGIN_WEEKLY_SUMMARY)
        self.assertIn("hrv_sdnn_ms", captured.weekly_summaries_visible["claim_semantics_by_metric"])

    def test_persisted_trace_includes_model_calls(self) -> None:
        import tempfile
        from pathlib import Path

        context = RunContext(scenario_id="HC-EVAL-D1", user_id=1, as_of_date=date(2026, 7, 13))
        capture_before_model(callback_context=None, llm_request=_sample_request(), context=context)
        trace = empty_trace(scenario_id="HC-EVAL-D1", user_id=1, as_of_date="2026-07-13")
        trace.model_calls = list(context.model_calls)
        record = PersistedAgentRun(trace=trace, structured_result={"status": "INSIGHT"}, model=MODEL)
        with tempfile.TemporaryDirectory() as tmp:
            with patch("agent.trace.TRACES_DIR", Path(tmp)):
                path = persist_agent_run(record)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["model_calls"]), 1)
        self.assertEqual(payload["model_calls"][0]["capture_fidelity"], CAPTURE_FIDELITY_ADK_PRE_MODEL)
        self.assertNotIn("sk-secret", json.dumps(payload))

    def test_bind_callbacks_are_keyword_only(self) -> None:
        context = RunContext(scenario_id="day30", user_id=1, as_of_date=date(2026, 6, 18))
        callbacks = bind_model_observation_callbacks(context)
        result = callbacks["before_model_callback"](callback_context=None, llm_request=_sample_request())
        self.assertIsNone(result)
        self.assertEqual(len(context.model_calls), 1)

    @patch("evals.llm_observability.get_health_trends_for_agent")
    def test_write_observability_artifacts(self, mock_trends) -> None:
        import tempfile
        from pathlib import Path

        from evals.llm_observability import write_observability_artifacts

        mock_trends.return_value = _trend_payload()
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_observability_artifacts(1, results_dir=Path(tmp))
            self.assertTrue(paths["md"].exists())
            text = paths["md"].read_text(encoding="utf-8")
            self.assertIn("adk_pre_model_request", text)
            self.assertIn("bypass_possible=True", text)


class SanitizeRegressionTests(unittest.TestCase):
    def test_sanitize_still_redacts_nested_secrets(self) -> None:
        sanitized = sanitize_for_trace({"nested": {"authorization": "Bearer x"}})
        self.assertEqual(sanitized["nested"]["authorization"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
