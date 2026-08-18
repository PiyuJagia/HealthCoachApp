# Evaluation artifacts

Future Assignment 4 traces and eval results live here.

## Trace format (Phase E2)

- **Format:** JSON (pretty-printed via `TraceRecord.to_json()`)
- **Why JSON:** human-readable, diff-friendly, no extra dependencies
- **Location:** `evals/traces/` (created at runtime — do not commit fabricated runs)
- **Schema:** `evals/trace_schema.py`

Trace helpers sanitize likely secret keys before persistence.
