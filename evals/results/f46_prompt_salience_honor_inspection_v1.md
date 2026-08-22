# F4.6 prompt/output honor of `insight_worthy`

Deterministic/local contract only. No Gemini. No guard-policy change. No salience-threshold change.

## A. Problem

F4.6 correctly marks B1 as `insight_worthy=false` while leaving steps `improving` (+6.55% / +670) and exercise `improving` (+3.87% / +0.43 min) visible.

That contract reached the model as tool payload + TRACE (`insight_salience_visible`), but **system instructions still allowed INSIGHT for any positive / stable-reassuring pattern “worth surfacing.”** The model could therefore promote weak directional analytics on its own. The output guard does not check salience (by prior design).

F4.6 decided eligibility. The prompt did not consume that authority.

## B. Architecture

```
F4.1 eligibility / maturity / direction
  → F4.5 maintenance_of_gain / maintenance_of_decline
    → F4.6 deterministic salience (insight_worthy, insight_candidate, reasons)
      → get_trend_signals payload (trends remain fully visible)
        → ADK system instruction (now honors insight_worthy)
          → LLM output status INSIGHT | NO_SIGNIFICANT_NEW_PATTERN | RECOMMENDATION
            → evidence policy (recommendation_authorized)
              → output guard (causal / unauthorized rec / suppressed IDs — unchanged)
```

Salience identifies noteworthy evidence. Policy authorizes recommendations. The guard does not re-implement T5.

## C. Exact prompt/output contract changed

**Before:** `Use INSIGHT for positive, negative, recovery, ambiguous/mixed, or stable/reassuring patterns worth surfacing.` Directional `improving` was enough in practice.

**After (system instruction + trend-tool docstring only):**

- `insight_salience.insight_worthy` is deterministic authority for elevating physiological evidence to INSIGHT.
- Detectable direction is not permission to emit INSIGHT.
- When `insight_worthy=false`, return `NO_SIGNIFICANT_NEW_PATTERN`; trends may remain in `reason_not_surfaced` as supporting analytics.
- When `insight_worthy=true`, use only eligible salient evidence (`insight_candidate` / `primary_metrics` / maintenance flags). Do not promote a non-candidate metric.
- INSIGHT may use `maintenance_of_gain` even when recent direction is `stable`.
- Lifestyle cannot manufacture salience.
- `recommendation_worthy` is not recommendation authorization.
- Early-pattern observations may be qualified insights; they must not be described as established personalized trends.
- Do not recompute salience in the prompt.

Not changed: F4.1, F4.5, F4.6 knobs, frozen labels, output guard, evidence-policy principles.

## D. Scenario matrix

| Scenario | Deterministic state | Expected model behavior |
|---|---|---|
| B1 | steps/exercise `improving`, barely_directional, `insight_worthy=false` | No INSIGHT promotion; direction remains visible |
| A1 | sleep −18.0% / −1.28 h, strong, `insight_worthy=true` | INSIGHT allowed from eligible salient evidence |
| B3 | RHR/HRV/VO₂ `stable` + `maintenance_of_gain`, `insight_worthy=true`, `recommendation_worthy=false` | INSIGHT allowed; not a recommendation |
| C3 sleep | sleep `stable`, `insight_candidate=false`, lifestyle caffeine/alcohol present | Lifestyle cannot promote sleep. Payload may still be worthy from real activity movement |
| Early pattern | `direction=unknown`, `trend_allowed=false`, `EARLY_PATTERN`, `insight_candidate=true` | Qualified early observation allowed; mature trend claim blocked |

## E. Recommendation boundary

Confirmed in instructions and tests:

`recommendation_worthy != recommendation_authorized`

B3 remains `recommendation_worthy=false`. A1 may be `recommendation_worthy=true` as a physiology flag only; RECOMMENDATION status still requires policy `recommendation_authorized=true`.

## F. TRACE

- System instruction in `adk_pre_model_request` snapshots now includes the honor contract.
- `insight_salience_visible` origin remains `deterministic_salience_analytics`.
- Thought parts still omitted (`omitted_thought_parts`).
- No hidden CoT added.

## G. Tests

- Focused: `tests/test_salience_prompt_honor.py` (10) + `tests/test_salience.py` (9) + guard/agent/observe — **60 passed**
- Full pytest: **315 passed** (2026-08-21; was 305 before this honor pass)

Guard test documents that B1-style “steps increased” prose still **passes** `check_final_output` — salience is not enforced in the guard.

## H. Files changed

- `agent/instructions.py`
- `agent/tools.py` (get_trend_signals docstring only)
- `tests/test_salience_prompt_honor.py`
- `evals/results/f46_prompt_salience_honor_inspection_v1.md`
- `evals/results/assignment4_tracker_v1.md`

## I. Remaining risks

Local prompt-contract tests do **not** prove live Gemini compliance. The model can still ignore instructions. A targeted B1/A1/B3 Gemini check (not a full 15-scenario rerun) is the next empirical step. Guard enforcement would belong to a later T7/CODIFY discussion if prompt honor fails in live runs; adding it now would collapse T5 contract visibility into output-policy enforcement.
