"""Persist Health Coach agent run traces."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evals.trace_schema import TraceRecord, sanitize_for_trace

TRACES_DIR = Path(__file__).resolve().parent.parent / "evals" / "traces"


@dataclass
class PersistedAgentRun:
    trace: TraceRecord
    activity_log: list[dict[str, Any]] = field(default_factory=list)
    structured_result: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = self.trace.to_dict()
        payload["activity_log"] = sanitize_for_trace(self.activity_log)
        payload["structured_result"] = sanitize_for_trace(self.structured_result)
        payload["latency_ms"] = self.latency_ms
        payload["model"] = self.model
        return sanitize_for_trace(payload)


def persist_agent_run(record: PersistedAgentRun) -> Path:
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    path = TRACES_DIR / f"{record.trace.run_id}.json"
    path.write_text(json.dumps(record.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path
