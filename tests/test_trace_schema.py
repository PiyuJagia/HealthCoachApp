"""Offline tests for trace schema helpers."""

from __future__ import annotations

import json
import unittest

from evals.trace_schema import (
    PolicyTrace,
    ToolCallTrace,
    TraceRecord,
    empty_trace,
    sanitize_for_trace,
)


class TraceSchemaTests(unittest.TestCase):
    def test_trace_serializes_deterministically(self) -> None:
        trace = empty_trace(scenario_id="demo", user_id=1, as_of_date="2026-08-17")
        trace.tool_calls.append(
            ToolCallTrace(
                tool_name="get_trend_signals",
                arguments={"user_id": 1},
                result_summary={"trend_count": 7},
            )
        )
        trace.policy = PolicyTrace(
            overall_verdict="QUALIFY",
            reasons=["qualified_evidence_only"],
            suppressed_relationship_ids=["R-03"],
        )
        first = trace.to_json()
        second = trace.to_json()
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(payload["scenario_id"], "demo")
        self.assertEqual(payload["tool_calls"][0]["tool_name"], "get_trend_signals")
        self.assertEqual(payload["model_calls"], [])

    def test_sanitize_for_trace_redacts_secrets(self) -> None:
        payload = {
            "openai_api_key": "sk-secret",
            "nested": {"pinecone_token": "pc-secret"},
            "safe": "value",
        }
        sanitized = sanitize_for_trace(payload)
        self.assertEqual(sanitized["openai_api_key"], "[REDACTED]")
        self.assertEqual(sanitized["nested"]["pinecone_token"], "[REDACTED]")
        self.assertEqual(sanitized["safe"], "value")
        self.assertEqual(sanitize_for_trace({"max_output_tokens": 2048})["max_output_tokens"], 2048)

    def test_sanitize_does_not_redact_instruction_prose(self) -> None:
        instruction = "Do not make recommendations unless recommendation_authorized=true."
        self.assertEqual(sanitize_for_trace(instruction), instruction)
        self.assertEqual(sanitize_for_trace("Bearer secret-token"), "[REDACTED]")

    def test_empty_partial_trace_state(self) -> None:
        trace = TraceRecord(
            run_id="run-1",
            scenario_id="partial",
            user_id=None,
            as_of_date=None,
            timestamp="2026-08-17T00:00:00+00:00",
        )
        payload = trace.to_dict()
        self.assertIsNone(payload["user_id"])
        self.assertEqual(payload["tool_calls"], [])
        self.assertIsNone(payload["policy"])


if __name__ == "__main__":
    unittest.main()
