# F4.2 LLM-visible input / TRACE observability

Inspection + instrumentation. No Gemini baseline rerun. No prompt/policy/maturity changes.

**Capture fidelity:** `adk_pre_model_request` (not exact HTTPS provider request)

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
{
  "call_index": 1,
  "model": "gemini-3.6-flash",
  "provider": "google_gemini_via_adk",
  "capture_fidelity": "adk_pre_model_request",
  "capture_point": "adk.LlmAgent.before_model_callback",
  "system_instruction_present": true,
  "user_scenario_input_preview": "Perform a bounded health review.\nscenario_id=HC-EVAL-D1\nuser_id=1\nas_of_date=2026-07-13\nInspect deterministic signals, investigate only meaningful patterns, use authorized evidence",
  "conversation_kinds": [
    "text",
    "function_call",
    "function_response"
  ],
  "tool_results_origins": [
    {
      "tool_name": "get_trend_signals",
      "origin": "health_trend_tool"
    }
  ],
  "trend_metrics_visible": [
    {
      "metric": "sleep_duration_hours",
      "data_maturity_state": "ESTABLISHED_TREND",
      "trend_allowed": true
    },
    {
      "metric": "resting_hr_bpm",
      "data_maturity_state": "ESTABLISHED_TREND",
      "trend_allowed": true
    },
    {
      "metric": "hrv_sdnn_ms",
      "data_maturity_state": "ESTABLISHED_TREND",
      "trend_allowed": true
    },
    {
      "metric": "exercise_minutes",
      "data_maturity_state": "ESTABLISHED_TREND",
      "trend_allowed": true
    },
    {
      "metric": "workout_count",
      "data_maturity_state": "ESTABLISHED_TREND",
      "trend_allowed": true
    },
    {
      "metric": "steps",
      "data_maturity_state": "ESTABLISHED_TREND",
      "trend_allowed": true
    },
    {
      "metric": "vo2_max",
      "data_maturity_state": "ESTABLISHED_TREND",
      "trend_allowed": true
    }
  ],
  "weekly_bypass_possible": true,
  "provenance_present": [
    "system_instruction",
    "user_scenario_input",
    "trend_maturity",
    "weekly_summaries"
  ]
}
```

## 6. What we can and cannot observe

**Can:** system/agent instructions; user/scenario prompt; conversation contents; tool names/args; full sanitized tool results including F4.1 maturity/eligibility; weekly summaries; RAG policy/ids; generation config scalars; provenance of each major component; count of omitted thought parts.

**Cannot:** HTTPS wire request; API keys/headers; hidden chain-of-thought (`part.thought=True`); provider billing internals; Gemini private reasoning.

## 7. Weekly-summary bypass (D1 2026-07-13)

Gemini receives **one** `get_trend_signals` function_response containing both:

- `trends[]` with `claim_eligibility`, `data_maturity_state`, `gap_caveat_required`
- `weekly_summaries[]` with numeric averages/totals + `coverage`, **no `claim_eligibility`**

D1 latest week: 2026-07-07 → 2026-07-13; average_hrv_sdnn_ms=34.32; week has_claim_eligibility=False; HRV coverage={'observation_count': 5, 'expected_observation_count': 7, 'coverage_ratio': 0.7143, 'latest_valid_observation_date': '2026-07-11', 'as_of_date_available': False, 'gap_caveat_required': True}.

Trend side: hrv trend_allowed=True; hrv as_of_available=False.

**bypass_possible=True.** Coverage is attached, but the week average still looks like a complete-week number. Gemini can cite weekly HRV while ignoring eligibility/gap fields.

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
