"""Offline tests for transient Gemini 503 and quota 429 provider handling."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

from google.genai.errors import ClientError, ServerError

from agent.display import (
    is_model_quota_exhausted,
    is_temporary_model_unavailable,
    model_quota_exhausted_message,
    temporary_unavailable_message,
)
from agent.provider_retry import (
    FAILURE_QUOTA_EXHAUSTED,
    FAILURE_TEMPORARY_UNAVAILABLE,
    MAX_PROVIDER_ATTEMPTS,
    MAX_SHORT_RETRY_DELAY_SECONDS,
    backoff_seconds,
    build_provider_retry_trace,
    extract_quota_retry_delay_seconds,
    is_gemini_quota_exhausted,
    is_transient_gemini_unavailable,
    run_with_provider_reliability,
    run_with_transient_retry,
)
from agent.runner import _run_agent_async
from agent.schemas import (
    HealthCoachStatus,
    model_quota_exhausted_result,
    temporary_model_unavailable_result,
)
from agent.trace import PersistedAgentRun, persist_agent_run
from evals.trace_schema import empty_trace


def _server_error_503() -> ServerError:
    return ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE", "message": "high demand"}}, None)


def _quota_error_429(*, retry_delay: str | None = "2s", message: str = "Quota exceeded") -> ClientError:
    details: list[dict[str, str]] = []
    if retry_delay is not None:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay})
    return ClientError(
        429,
        {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": message,
                "details": details,
            }
        },
        None,
    )


class ProviderRetryDetectionTests(unittest.TestCase):
    def test_detects_transient_503_server_error(self) -> None:
        self.assertTrue(is_transient_gemini_unavailable(_server_error_503()))

    def test_detects_quota_429_client_error(self) -> None:
        self.assertTrue(is_gemini_quota_exhausted(_quota_error_429()))

    def test_429_is_not_classified_as_503(self) -> None:
        exc = _quota_error_429()
        self.assertTrue(is_gemini_quota_exhausted(exc))
        self.assertFalse(is_transient_gemini_unavailable(exc))

    def test_does_not_retry_non_provider_client_error(self) -> None:
        client_error = ClientError(401, {"error": {"code": 401, "message": "unauthorized"}}, None)
        self.assertFalse(is_transient_gemini_unavailable(client_error))
        self.assertFalse(is_gemini_quota_exhausted(client_error))

    def test_respects_retry_after_header_for_503(self) -> None:
        class _Response:
            headers = {"Retry-After": "6"}

        exc = ServerError(503, {"error": {"status": "UNAVAILABLE"}}, _Response())
        self.assertEqual(backoff_seconds(0, exc), 6.0)

    def test_extracts_retryinfo_delay_for_429(self) -> None:
        exc = _quota_error_429(retry_delay="3s")
        self.assertEqual(extract_quota_retry_delay_seconds(exc), 3.0)


class RunWithTransientRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_503_then_success_retries_and_succeeds(self) -> None:
        calls = {"count": 0}

        async def operation() -> str:
            calls["count"] += 1
            if calls["count"] == 1:
                raise _server_error_503()
            return "ok"

        with patch("agent.provider_retry.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            result = await run_with_transient_retry(operation)

        self.assertEqual(result, "ok")
        self.assertEqual(calls["count"], 2)
        sleep_mock.assert_awaited_once()

    async def test_repeated_503_fails_after_max_attempts(self) -> None:
        async def operation() -> str:
            raise _server_error_503()

        with patch("agent.provider_retry.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(ServerError):
                await run_with_transient_retry(operation)


class QuotaRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_429_with_short_retry_delay_retries_once_then_succeeds(self) -> None:
        calls = {"count": 0}

        async def operation() -> str:
            calls["count"] += 1
            if calls["count"] == 1:
                raise _quota_error_429(retry_delay="2s")
            return "ok"

        with patch("agent.provider_retry.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            result = await run_with_provider_reliability(operation)

        self.assertEqual(result, "ok")
        self.assertEqual(calls["count"], 2)
        sleep_mock.assert_awaited_once()

    async def test_429_followed_by_429_raises_without_503_backoff(self) -> None:
        calls = {"count": 0}

        async def operation() -> str:
            calls["count"] += 1
            raise _quota_error_429(retry_delay="2s")

        with patch("agent.provider_retry.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            with self.assertRaises(ClientError):
                await run_with_provider_reliability(operation)

        self.assertEqual(calls["count"], 2)
        sleep_mock.assert_awaited_once()

    async def test_clear_quota_exhaustion_without_short_delay_fails_immediately(self) -> None:
        calls = {"count": 0}

        async def operation() -> str:
            calls["count"] += 1
            raise _quota_error_429(
                retry_delay=None,
                message="You exceeded your current quota, please check your plan and billing details.",
            )

        with patch("agent.provider_retry.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            with self.assertRaises(ClientError):
                await run_with_provider_reliability(operation)

        self.assertEqual(calls["count"], 1)
        sleep_mock.assert_not_awaited()

    async def test_429_does_not_use_503_backoff_semantics(self) -> None:
        calls = {"count": 0}

        async def operation() -> str:
            calls["count"] += 1
            if calls["count"] == 1:
                raise _quota_error_429(retry_delay="2s")
            return "ok"

        with patch("agent.provider_retry.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            await run_with_provider_reliability(operation)

        sleep_mock.assert_awaited_once_with(2.0)


class RunnerProviderFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_exhausted_503_returns_temporary_model_unavailable(self) -> None:
        with patch("agent.runner.run_with_provider_reliability", new=AsyncMock(side_effect=_server_error_503())):
            with patch("agent.runner.persist_agent_run") as persist_mock:
                persist_mock.return_value = Path("evals/traces/test-run.json")
                result = await _run_agent_async(
                    scenario_id="day30",
                    user_id=1,
                    as_of_date=date(2026, 6, 18),
                )

        self.assertEqual(result.status, HealthCoachStatus.TEMPORARY_MODEL_UNAVAILABLE.value)
        assert result.provider_retry is not None
        self.assertEqual(result.provider_retry["status_code"], 503)
        self.assertEqual(result.provider_retry["failure_category"], FAILURE_TEMPORARY_UNAVAILABLE)

    async def test_exhausted_429_returns_model_quota_exhausted(self) -> None:
        with patch(
            "agent.runner.run_with_provider_reliability",
            new=AsyncMock(side_effect=_quota_error_429(retry_delay="2s")),
        ):
            with patch("agent.runner.persist_agent_run") as persist_mock:
                persist_mock.return_value = Path("evals/traces/test-run.json")
                result = await _run_agent_async(
                    scenario_id="day30",
                    user_id=1,
                    as_of_date=date(2026, 6, 18),
                )

        self.assertEqual(result.status, HealthCoachStatus.MODEL_QUOTA_EXHAUSTED.value)
        self.assertIsNone(result.structured.get("insight"))
        self.assertIsNone(result.structured.get("recommendation"))
        assert result.provider_retry is not None
        self.assertEqual(result.provider_retry["status_code"], 429)
        self.assertEqual(result.provider_retry["failure_category"], FAILURE_QUOTA_EXHAUSTED)
        self.assertTrue(result.provider_retry["exhausted"])

    async def test_trace_records_quota_retry_metadata(self) -> None:
        trace = empty_trace(scenario_id="day30", user_id=1, as_of_date="2026-06-18")
        provider_retry = build_provider_retry_trace(
            exc=_quota_error_429(retry_delay="2s"),
            attempts=2,
            exhausted=True,
            failure_category=FAILURE_QUOTA_EXHAUSTED,
        ).to_dict()
        record = PersistedAgentRun(
            trace=trace,
            structured_result=model_quota_exhausted_result(
                scenario_id="day30",
                user_id=1,
                as_of_date="2026-06-18",
            ).to_dict(),
            provider_retry=provider_retry,
            model="gemini-3.6-flash",
        )
        payload = record.to_dict()
        self.assertEqual(payload["provider_retry"]["status_code"], 429)
        self.assertEqual(payload["provider_retry"]["failure_category"], FAILURE_QUOTA_EXHAUSTED)
        self.assertEqual(payload["provider_retry"]["retry_after_seconds"], 2.0)


class DisplayHelperTests(unittest.TestCase):
    def test_streamlit_helper_renders_temporary_unavailable_state(self) -> None:
        structured = temporary_model_unavailable_result(
            scenario_id="day30",
            user_id=1,
            as_of_date="2026-06-18",
        ).to_dict()
        self.assertTrue(is_temporary_model_unavailable(structured))
        self.assertIn("temporarily busy", temporary_unavailable_message(structured).lower())

    def test_streamlit_helper_renders_model_quota_exhausted_state(self) -> None:
        structured = model_quota_exhausted_result(
            scenario_id="day30",
            user_id=1,
            as_of_date="2026-06-18",
        ).to_dict()
        self.assertTrue(is_model_quota_exhausted(structured))
        self.assertIn("usage limit", model_quota_exhausted_message(structured).lower())


if __name__ == "__main__":
    unittest.main()
