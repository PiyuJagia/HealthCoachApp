# Evaluation artifacts

Future Assignment 4 traces and eval results live here.

## Trace format (Phase E2 + E3.1)

- **Format:** one JSON file per run at `evals/traces/{run_id}.json`
- **Why JSON:** human-readable, diff-friendly, no extra dependencies
- **Location:** `evals/traces/` (runtime-generated; gitignored except `.gitignore`)
- **Schema base:** `evals/trace_schema.py` (`TraceRecord`)
- **E3.1 extensions:** persisted runs also include `activity_log`, `structured_result`, `latency_ms`, `model`

Each archived run contains:

| Field | Content |
|-------|---------|
| `run_id`, `scenario_id`, `user_id`, `as_of_date`, `timestamp` | Run metadata |
| `candidate_signals` | Output from `get_trend_signals` |
| `tool_calls` | ACT/OBSERVE summaries (sanitized) |
| `retrieval` | Vector/document/relationship identifiers + policy metadata |
| `policy` | Deterministic verdict, reasons, suppressed IDs |
| `generation` | Final candidate insight text |
| `final_guard` | Pass/fail + violations |
| `final_output` | Structured JSON result string |
| `activity_log` | User-safe DECISION/ACT/OBSERVE/FINAL steps (no hidden CoT) |
| `provider_retry` | Optional provider failure metadata (503/429 retries) |

Trace helpers sanitize likely secret keys before persistence.

**Provider failure categories:** `temporary_unavailable` (503) and `quota_exhausted` (429). These are
operational reliability controls discovered during real Assignment 3 live testing; they fail closed and
do not return partial health guidance.

**Structured result statuses (E3.1.1):** `INSIGHT`, `RECOMMENDATION`, `NO_SIGNIFICANT_NEW_PATTERN`,
`BOUNDED_FAILURE`, `GUARD_BLOCKED`. Older E3.1 trace archives may contain the retired status
`NO_MEANINGFUL_INSIGHT`.

**Assignment 4 status:** TRACE capture is **partial** — runs are archived, but eval runner, failure taxonomy, and before/after assertions are not implemented yet.

## Generating traces

```bash
python scripts/run_health_agent_scenarios.py --all
```

Or via Streamlit:

```bash
streamlit run streamlit_agent_demo.py
```
