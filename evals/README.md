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
| `model_calls` | F4.2 ADK pre-model `LlmRequest` snapshots (optional on frozen F1 traces) |
| `provider_retry` | Optional provider failure metadata (503/429 retries) |

Trace helpers sanitize likely secret keys before persistence.

**Provider failure categories:** `temporary_unavailable` (503) and `quota_exhausted` (429). These are
operational reliability controls discovered during real Assignment 3 live testing; they fail closed and
do not return partial health guidance.

**Structured result statuses (E3.1.1):** `INSIGHT`, `RECOMMENDATION`, `NO_SIGNIFICANT_NEW_PATTERN`,
`BOUNDED_FAILURE`, `GUARD_BLOCKED`. Older E3.1 trace archives may contain the retired status
`NO_MEANINGFUL_INSIGHT`.

**Assignment 4 status:** F1–F5.2 complete. CODIFY v1 complete (`evals/codify/`). Frozen human PASS/FAIL labels unchanged. Full 15-scenario Gemini baseline has **not** been rerun.

Tracker: `evals/results/assignment4_tracker_v1.md`

## Phase F1 — Baseline trace collection (Assignment 4)

**Concepts (kept separate on purpose):**

| Concept | Meaning |
|---------|---------|
| **Scenario** | Situation we deliberately test (`evals/datasets/healthcoach_trace_baseline_v1.jsonl`) |
| **Trace** | What actually happened during an agent run (`evals/traces/{run_id}.json`) |
| **Human note** | Free-text observation added only after manual review |
| **Failure taxonomy** | Clusters discovered **after** reading traces — not pre-built |
| **Eval / grader** | CODIFY v1 TRACE graders in `evals/codify/`; semantic T8/quote judges are spec-only |

**Artifacts:**

| Artifact | Path |
|----------|------|
| Baseline manifest (15 scenarios) | `evals/datasets/healthcoach_trace_baseline_v1.jsonl` |
| Data-support inspection | `python scripts/inspect_eval_baseline.py` |
| Baseline runner | `python scripts/run_eval_baseline.py --all` |
| Resume partial runs | `python scripts/run_eval_baseline.py --all --resume` |
| Manual review index | `evals/results/baseline_trace_index_v1.csv` |
| System integrity metadata | `evals/results/baseline_metadata_v1.json` |

Provider failures (`TEMPORARY_MODEL_UNAVAILABLE`, `MODEL_QUOTA_EXHAUSTED`) are recorded as
`PROVIDER_FAILURE` in the index — not product failures during F1.

## Generating traces (Assignment 3 demo scenarios)

```bash
python scripts/run_health_agent_scenarios.py --all
```

Or via Streamlit:

```bash
streamlit run streamlit_agent_demo.py
```

## Generating baseline traces (Assignment 4 F1)

```bash
python scripts/run_eval_baseline.py --all
```