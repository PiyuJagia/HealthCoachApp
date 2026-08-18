"""Bounded retry helpers for transient Gemini provider failures (503 and 429)."""

from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable, TypeVar

from google.genai.errors import ClientError, ServerError

try:
    from google.adk.workflow._errors import DynamicNodeFailError
except ImportError:  # pragma: no cover - defensive import
    DynamicNodeFailError = None  # type: ignore[misc, assignment]

MAX_PROVIDER_ATTEMPTS = 3
MAX_QUOTA_RETRIES = 1
DEFAULT_BACKOFF_SECONDS = (2.0, 4.0)
TRANSIENT_STATUS_CODE = 503
QUOTA_STATUS_CODE = 429
MAX_SHORT_RETRY_DELAY_SECONDS = 60.0
FAILURE_TEMPORARY_UNAVAILABLE = "temporary_unavailable"
FAILURE_QUOTA_EXHAUSTED = "quota_exhausted"

T = TypeVar("T")
_DURATION_PATTERN = re.compile(r"^(?P<value>\d+(?:\.\d+)?)s$")


@dataclass(frozen=True)
class ProviderRetryTrace:
    provider_error_type: str
    status_code: int
    retry_count: int
    exhausted: bool
    retry_after_seconds: float | None = None
    failure_category: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def iter_exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        if DynamicNodeFailError is not None and isinstance(current, DynamicNodeFailError):
            current = current.error
            continue
        current = current.__cause__ or current.__context__
    return chain


def find_server_error(exc: BaseException) -> ServerError | None:
    for item in iter_exception_chain(exc):
        if isinstance(item, ServerError):
            return item
    return None


def find_client_error(exc: BaseException) -> ClientError | None:
    for item in iter_exception_chain(exc):
        if isinstance(item, ClientError):
            return item
    return None


def _error_message(exc: BaseException) -> str:
    for item in iter_exception_chain(exc):
        message = getattr(item, "message", None)
        if message:
            return str(message)
    return str(exc)


def _parse_duration_seconds(raw: str | None) -> float | None:
    if raw is None:
        return None
    value = raw.strip()
    match = _DURATION_PATTERN.match(value)
    if match:
        return float(match.group("value"))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _details_containers(exc: BaseException) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = []
    for item in iter_exception_chain(exc):
        details = getattr(item, "details", None)
        if isinstance(details, dict):
            containers.append(details)
            error = details.get("error")
            if isinstance(error, dict):
                containers.append(error)
    return containers


def is_transient_gemini_unavailable(exc: BaseException) -> bool:
    if is_gemini_quota_exhausted(exc):
        return False
    server_error = find_server_error(exc)
    if server_error is None:
        return False
    if server_error.code == TRANSIENT_STATUS_CODE:
        return True
    status = (server_error.status or "").upper()
    message = str(server_error).upper()
    return status == "UNAVAILABLE" or "503 UNAVAILABLE" in message


def is_gemini_quota_exhausted(exc: BaseException) -> bool:
    for item in iter_exception_chain(exc):
        if isinstance(item, ClientError) and item.code == QUOTA_STATUS_CODE:
            return True
        status = (getattr(item, "status", None) or "").upper()
        if status == "RESOURCE_EXHAUSTED":
            return True
    message = _error_message(exc).upper()
    return "429" in message and "RESOURCE_EXHAUSTED" in message


def is_clear_quota_exhaustion(exc: BaseException) -> bool:
    message = _error_message(exc).lower()
    delay = extract_quota_retry_delay_seconds(exc)
    if delay is not None and delay <= MAX_SHORT_RETRY_DELAY_SECONDS:
        return False
    quota_markers = (
        "quota",
        "rate limit",
        "resource_exhausted",
        "exceeded your current quota",
        "generate_requests",
    )
    return any(marker in message for marker in quota_markers)


def extract_retry_after_seconds(exc: BaseException) -> float | None:
    for item in iter_exception_chain(exc):
        response = getattr(item, "response", None)
        headers = getattr(response, "headers", None)
        if not headers:
            continue
        raw = headers.get("Retry-After") or headers.get("retry-after")
        parsed = _parse_duration_seconds(str(raw) if raw is not None else None)
        if parsed is not None:
            return parsed
    return None


def extract_quota_retry_delay_seconds(exc: BaseException) -> float | None:
    delay = extract_retry_after_seconds(exc)
    if delay is not None:
        return delay
    for container in _details_containers(exc):
        for detail in container.get("details") or []:
            if not isinstance(detail, dict):
                continue
            retry_delay = detail.get("retryDelay")
            if retry_delay is None:
                continue
            parsed = _parse_duration_seconds(str(retry_delay))
            if parsed is not None:
                return parsed
    return None


def is_short_quota_retry_delay(delay: float | None) -> bool:
    return delay is not None and 0 < delay <= MAX_SHORT_RETRY_DELAY_SECONDS


def backoff_seconds(retry_index: int, exc: BaseException) -> float:
    default = DEFAULT_BACKOFF_SECONDS[retry_index] if retry_index < len(DEFAULT_BACKOFF_SECONDS) else DEFAULT_BACKOFF_SECONDS[-1]
    retry_after = extract_retry_after_seconds(exc)
    if retry_after is not None:
        return max(default, retry_after)
    return default


async def run_with_transient_retry(operation: Callable[[], Awaitable[T]]) -> T:
    """Run an async operation with bounded 503 retries only."""
    last_exc: BaseException | None = None
    for attempt in range(1, MAX_PROVIDER_ATTEMPTS + 1):
        try:
            return await operation()
        except Exception as exc:  # noqa: BLE001 — retry wrapper inspects provider errors
            last_exc = exc
            if not is_transient_gemini_unavailable(exc):
                raise
            if attempt >= MAX_PROVIDER_ATTEMPTS:
                break
            await asyncio.sleep(backoff_seconds(attempt - 1, exc))
    assert last_exc is not None
    raise last_exc


async def run_with_provider_reliability(operation: Callable[[], Awaitable[T]]) -> T:
    """Run an async operation with separate 429 and 503 handling."""
    last_exc: BaseException | None = None
    unavailable_attempt = 0
    quota_retries_used = 0

    while True:
        try:
            return await operation()
        except Exception as exc:  # noqa: BLE001 — provider reliability inspects error types
            last_exc = exc

            if is_gemini_quota_exhausted(exc):
                delay = extract_quota_retry_delay_seconds(exc)
                if (
                    quota_retries_used < MAX_QUOTA_RETRIES
                    and is_short_quota_retry_delay(delay)
                    and not is_clear_quota_exhaustion(exc)
                ):
                    quota_retries_used += 1
                    await asyncio.sleep(delay)  # type: ignore[arg-type]
                    continue
                raise

            if is_transient_gemini_unavailable(exc):
                unavailable_attempt += 1
                if unavailable_attempt >= MAX_PROVIDER_ATTEMPTS:
                    raise
                await asyncio.sleep(backoff_seconds(unavailable_attempt - 1, exc))
                continue

            raise

    assert last_exc is not None
    raise last_exc


def build_provider_retry_trace(
    *,
    exc: BaseException,
    attempts: int,
    exhausted: bool,
    failure_category: str,
) -> ProviderRetryTrace:
    client_error = find_client_error(exc)
    server_error = find_server_error(exc)
    if failure_category == FAILURE_QUOTA_EXHAUSTED:
        status_code = client_error.code if client_error is not None else QUOTA_STATUS_CODE
        provider_error_type = type(client_error or exc).__name__
        retry_after = extract_quota_retry_delay_seconds(exc)
    else:
        status_code = server_error.code if server_error is not None else TRANSIENT_STATUS_CODE
        provider_error_type = type(server_error or exc).__name__
        retry_after = extract_retry_after_seconds(exc)

    return ProviderRetryTrace(
        provider_error_type=provider_error_type,
        status_code=status_code,
        retry_count=max(0, attempts - 1),
        exhausted=exhausted,
        retry_after_seconds=retry_after,
        failure_category=failure_category,
    )
