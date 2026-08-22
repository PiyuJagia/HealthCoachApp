"""F4.2 LLM-visible input / TRACE observability inspection helpers."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from agent.agent import MODEL, build_review_prompt
from agent.instructions import HEALTH_COACH_INSTRUCTIONS
from agent.model_observe import assess_weekly_summary_bypass, observe_llm_request
from app.health_tools import get_health_trends_for_agent
from evals.trace_schema import CAPTURE_FIDELITY_ADK_PRE_MODEL

RESULTS_DIR = Path(__file__).resolve().parent / "results"
OBSERVABILITY_MD = RESULTS_DIR / "f42_llm_observability_v1.md"
OBSERVABILITY_JSON = RESULTS_DIR / "f42_llm_observability_v1.json"

D1_AS_OF = date(2026, 7, 13)


def inspect_weekly_bypass_from_tool(user_id: int, as_of_date: date = D1_AS_OF) -> dict[str, Any]:
    payload = get_health_trends_for_agent(user_id, as_of_date=as_of_date, include_weekly_summaries=True)
    bypass = assess_weekly_summary_bypass(payload)
    latest = (payload.get("weekly_summaries") or [None])[-1]
    hrv_trend = next(
        (item for item in payload.get("trends") or [] if item.get("metric") == "hrv_sdnn_ms"),
        None,
    )
    return {
        "as_of_date": as_of_date.isoformat(),
        "tool": "get_trend_signals",
        "trends_have_claim_eligibility": bool(hrv_trend and hrv_trend.get("claim_eligibility")),
        "hrv_trend_allowed": (hrv_trend or {}).get("claim_eligibility", {}).get("trend_allowed"),
        "hrv_as_of_date_available": (hrv_trend or {}).get("as_of_date_available"),
        "latest_week": {
            "week_start": (latest or {}).get("week_start"),
            "week_end": (latest or {}).get("week_end"),
            "average_hrv_sdnn_ms": (latest or {}).get("average_hrv_sdnn_ms"),
            "has_claim_eligibility": "claim_eligibility" in (latest or {}),
            "hrv_coverage": ((latest or {}).get("coverage") or {}).get("hrv_sdnn_ms"),
        },
        "bypass": bypass,
    }


def example_model_call(user_id: int, as_of_date: date = D1_AS_OF) -> dict[str, Any]:
    from google.adk.models.llm_request import LlmRequest
    from google.genai import types

    payload = get_health_trends_for_agent(user_id, as_of_date=as_of_date, include_weekly_summaries=True)
    prompt = build_review_prompt(scenario_id="HC-EVAL-D1", user_id=user_id, as_of_date=as_of_date)
    request = LlmRequest(
        model=MODEL,
        contents=[
            types.Content(role="user", parts=[types.Part(text=prompt)]),
            types.Content(
                role="model",
                parts=[types.Part(function_call=types.FunctionCall(name="get_trend_signals", args={}))],
            ),
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name="get_trend_signals",
                            response=payload,
                        )
                    )
                ],
            ),
        ],
        config=types.GenerateContentConfig(system_instruction=HEALTH_COACH_INSTRUCTIONS, temperature=None),
    )
    return observe_llm_request(request, call_index=1).to_dict()


def render_observability_markdown(*, weekly: dict[str, Any], example: dict[str, Any]) -> str:
    latest = weekly["latest_week"]
    bypass = weekly["bypass"]
    example_compact = {
        "call_index": example.get("call_index"),
        "model": example.get("model"),
        "provider": example.get("provider"),
        "capture_fidelity": example.get("capture_fidelity"),
        "capture_point": example.get("capture_point"),
        "system_instruction_present": bool(example.get("system_instruction")),
        "user_scenario_input_preview": (example.get("user_scenario_input") or "")[:180],
        "conversation_kinds": [item.get("kind") for item in example.get("conversation_messages") or []],
        "tool_results_origins": [
            {"tool_name": item.get("tool_name"), "origin": item.get("origin")}
            for item in example.get("tool_results_visible") or []
        ],
        "trend_metrics_visible": [
            {
                "metric": item.get("metric"),
                "data_maturity_state": item.get("data_maturity_state"),
                "trend_allowed": (item.get("claim_eligibility") or {}).get("trend_allowed"),
            }
            for item in ((example.get("trend_maturity_visible") or {}).get("metrics") or [])
        ],
        "weekly_bypass_possible": (example.get("weekly_summary_bypass_risk") or {}).get("bypass_possible"),
        "provenance_present": [
            item.get("component")
            for item in example.get("provenance") or []
            if item.get("present")
        ],
    }
    return f"""# F4.2 LLM-visible input / TRACE observability

Inspection + instrumentation. No Gemini baseline rerun. No prompt/policy/maturity changes.

**Capture fidelity:** `{CAPTURE_FIDELITY_ADK_PRE_MODEL}` (not exact HTTPS provider request)

## 1. ADK / model invocation path

1. `run_health_review` → `_execute_adk_run_once`
2. `build_health_coach_agent` + `Runner.run_async` with user review prompt
3. Tools (`get_trend_signals`, `retrieve_authorized_evidence`) execute; ADK appends function_call / function_response contents
4. ADK `AutoFlow` / `BaseLlmFlow` builds `LlmRequest` (system_instruction, contents, tools, GenerateContentConfig)
5. **`LlmAgent.before_model_callback(callback_context, llm_request)`** ← interception
6. `Gemini.generate_content_async(llm_request)` then `_preprocess_request`, tracking headers, generate_content
7. Visible model output (non-thought parts) returns; `after_model_callback` records kinds only

## 2. Interception point

`adk.LlmAgent.before_model_callback` on the assembled `LlmRequest`, immediately before `generate_content_async`.

Returning `None` does not skip or mutate the model call.

## 3. Fidelity

| Label | Used? | Meaning |
|---|---|---|
| exact_provider_request | no | HTTPS wire payload including headers/API key |
| adk_pre_model_request | **yes** | ADK `LlmRequest` Gemini actually consumes as contents/config |
| reconstructed_approximation | no | rebuilt from tool summaries after the fact |

Post-callback adapter deltas we deliberately do **not** call "exact": tracking headers, Gemini API label stripping, inline/file display-name preprocess. Contents, system instruction, and tool results are already present at callback time.

## 4. Trace schema additions

`TraceRecord.model_calls[]` (`ModelCallContextTrace`):

- call_index, model, provider, capture_fidelity, capture_point
- system_instruction, user_scenario_input, conversation_messages
- tool_calls_preceding, tool_results_visible (with origin)
- trend_maturity_visible, weekly_summaries_visible, rag_evidence_visible
- lifestyle_context_visible (reserved)
- generation_config (no http_options/headers)
- provenance[], weekly_summary_bypass_risk, omitted_thought_parts
- visible_response (non-thought kinds only)

Existing F1 traces remain valid: `model_calls` is optional for completeness checks.

## 5. Example model-call structure (D1-shaped, offline)

```json
{json.dumps(example_compact, indent=2)}
```

## 6. What we can and cannot observe

**Can:** system/agent instructions; user/scenario prompt; conversation contents; tool names/args; full sanitized tool results including F4.1 maturity/eligibility; weekly summaries; RAG policy/ids; generation config scalars; provenance of each major component; count of omitted thought parts.

**Cannot:** HTTPS wire request; API keys/headers; hidden chain-of-thought (`part.thought=True`); provider billing internals; Gemini private reasoning.

## 7. Weekly-summary bypass (D1 2026-07-13)

Gemini receives **one** `get_trend_signals` function_response containing both:

- `trends[]` with `claim_eligibility`, `data_maturity_state`, `gap_caveat_required`
- `weekly_summaries[]` with numeric averages/totals + `coverage`, **no `claim_eligibility`**

D1 latest week: {latest.get("week_start")} → {latest.get("week_end")}; average_hrv_sdnn_ms={latest.get("average_hrv_sdnn_ms")}; week has_claim_eligibility={latest.get("has_claim_eligibility")}; HRV coverage={latest.get("hrv_coverage")}.

Trend side: hrv trend_allowed={weekly.get("hrv_trend_allowed")}; hrv as_of_available={weekly.get("hrv_as_of_date_available")}.

**bypass_possible={bypass.get("bypass_possible")}.** Coverage is attached, but the week average still looks like a complete-week number. Gemini can cite weekly HRV while ignoring eligibility/gap fields.

**Do not fix in F4.2.** Recommended next product change: **enrich weekly summaries with claim_eligibility / maturity-aware fields**. Do not remove them (Family B / T4 still needs week-over-week context). Leaving unchanged leaves a bypass.

## 8. Privacy / redaction

- `sanitize_for_trace` on all persisted model-call objects
- drop `http_options` / headers from generation_config
- redact credential-like keys (`api_key`, `_token` suffix, password, secret, authorization, openai, pinecone) and credential-like values (`sk-`, `Bearer `, …)
- do not redact instruction prose that merely mentions `recommendation_authorized`
- skip `part.thought` content; record omitted_thought_parts only
- callbacks return None and do not mutate `LlmRequest`

## 9. Recommended next remediation

1. Finish accepting F4.2 observability.
2. Enrich weekly summaries with claim eligibility (close the bypass) — do not rerun Gemini until that lands if the goal is a clean D-family rerun.
3. Lifestyle context tool remains P0 product (T1) but is a separate contract.
4. Then Gemini rerun → CODIFY. Not now.
"""


def write_observability_artifacts(user_id: int, results_dir: Path | None = None) -> dict[str, Path]:
    weekly = inspect_weekly_bypass_from_tool(user_id)
    example = example_model_call(user_id)
    out_dir = results_dir or RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / OBSERVABILITY_JSON.name
    md_path = out_dir / OBSERVABILITY_MD.name
    payload = {
        "inspection_id": "f42_llm_observability_v1",
        "capture_fidelity": CAPTURE_FIDELITY_ADK_PRE_MODEL,
        "interception_point": "adk.LlmAgent.before_model_callback",
        "weekly_bypass": weekly,
        "example_model_call": {
            "call_index": example.get("call_index"),
            "capture_fidelity": example.get("capture_fidelity"),
            "capture_point": example.get("capture_point"),
            "provenance": example.get("provenance"),
            "weekly_summary_bypass_risk": example.get("weekly_summary_bypass_risk"),
            "trend_maturity_visible": example.get("trend_maturity_visible"),
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_observability_markdown(weekly=weekly, example=example), encoding="utf-8")
    return {"md": md_path, "json": json_path}
