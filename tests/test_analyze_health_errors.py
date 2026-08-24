"""Offline tests for Analyze Health provider-error translation. No Gemini."""

from __future__ import annotations

import unittest

from google.genai.errors import ClientError, ServerError

from agent.display import (
    ANALYSIS_FAILED_UI_MESSAGE,
    EVIDENCE_UNAVAILABLE_UI_MESSAGE,
    GEMINI_BUSY_UI_MESSAGE,
    GEMINI_UNAVAILABLE_UI_MESSAGE,
    analyze_health_status_message,
    format_health_coach_output,
    is_safe_analyze_error_message,
    user_facing_analyze_error,
)
from agent.schemas import (
    HealthCoachStatus,
    model_quota_exhausted_result,
    temporary_model_unavailable_result,
)


def _server_error_503() -> ServerError:
    return ServerError(
        503,
        {"error": {"code": 503, "status": "UNAVAILABLE", "message": "high demand"}},
        None,
    )


def _quota_error_429() -> ClientError:
    return ClientError(
        429,
        {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded"}},
        None,
    )


class AnalyzeHealthErrorTranslationTests(unittest.TestCase):
    def test_successful_insight_output_unchanged(self) -> None:
        structured = {
            "status": HealthCoachStatus.INSIGHT.value,
            "primary_message": "Sleep duration decreased this week.",
            "subtext": "Exercise minutes increased.",
            "insight": "Sleep is the higher-priority observation.",
            "recommendation": None,
            "supporting_metric_facts": [],
        }
        text = format_health_coach_output(structured)
        self.assertIn("PRIMARY MESSAGE", text)
        self.assertIn("Sleep duration decreased this week.", text)
        self.assertIn("RATIONALE", text)
        self.assertNotIn(GEMINI_BUSY_UI_MESSAGE, text)
        self.assertNotIn(ANALYSIS_FAILED_UI_MESSAGE, text)

    def test_gemini_503_unavailable_maps_to_busy_copy(self) -> None:
        message = user_facing_analyze_error(_server_error_503())
        self.assertEqual(message, GEMINI_BUSY_UI_MESSAGE)
        self.assertNotIn("503", message)
        self.assertNotIn("UNAVAILABLE", message)
        self.assertNotIn("high demand", message)

    def test_wrapped_503_still_maps_to_busy_copy(self) -> None:
        wrapped = RuntimeError("ADK node failed")
        wrapped.__cause__ = _server_error_503()
        message = user_facing_analyze_error(wrapped)
        self.assertEqual(message, GEMINI_BUSY_UI_MESSAGE)

    def test_generic_exception_does_not_leak_details(self) -> None:
        secret = "sk-secret-value bearer token traceback"
        message = user_facing_analyze_error(RuntimeError(secret))
        self.assertEqual(message, ANALYSIS_FAILED_UI_MESSAGE)
        self.assertNotIn("sk-secret", message)
        self.assertNotIn("bearer", message.lower())
        self.assertNotIn("traceback", message.lower())
        self.assertTrue(is_safe_analyze_error_message(message))

    def test_openai_style_runtime_error_is_evidence_message(self) -> None:
        message = user_facing_analyze_error(RuntimeError("OpenAI embedding request failed: timeout"))
        self.assertEqual(message, EVIDENCE_UNAVAILABLE_UI_MESSAGE)
        self.assertNotIn("timeout", message)
        self.assertNotIn("OpenAI", message)

    def test_pinecone_style_runtime_error_is_evidence_message(self) -> None:
        message = user_facing_analyze_error(RuntimeError("Pinecone query failed: 503"))
        self.assertEqual(message, EVIDENCE_UNAVAILABLE_UI_MESSAGE)
        self.assertNotIn("503", message)
        self.assertNotIn("Pinecone", message)

    def test_generic_gemini_error_is_not_labeled_as_evidence(self) -> None:
        exc = ClientError(
            400,
            {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "bad request"}},
            None,
        )
        message = user_facing_analyze_error(exc)
        self.assertEqual(message, GEMINI_UNAVAILABLE_UI_MESSAGE)
        self.assertNotEqual(message, EVIDENCE_UNAVAILABLE_UI_MESSAGE)
        self.assertNotIn("bad request", message)

    def test_quota_error_keeps_quota_copy(self) -> None:
        message = user_facing_analyze_error(_quota_error_429())
        self.assertIn("usage limit", message.lower())
        self.assertNotIn("429", message)
        self.assertNotEqual(message, GEMINI_BUSY_UI_MESSAGE)

    def test_runner_translated_503_status_uses_busy_copy(self) -> None:
        structured = temporary_model_unavailable_result(
            scenario_id="day30",
            user_id=1,
            as_of_date="2026-06-18",
        ).to_dict()
        self.assertEqual(analyze_health_status_message(structured), GEMINI_BUSY_UI_MESSAGE)
        # TRACE/schema sentence stays on the structured result itself.
        self.assertIn("temporarily busy", structured["reason_not_surfaced"].lower())

    def test_runner_translated_quota_status_unchanged(self) -> None:
        structured = model_quota_exhausted_result(
            scenario_id="day30",
            user_id=1,
            as_of_date="2026-06-18",
        ).to_dict()
        message = analyze_health_status_message(structured)
        self.assertIsNotNone(message)
        self.assertIn("usage limit", message.lower())


if __name__ == "__main__":
    unittest.main()
