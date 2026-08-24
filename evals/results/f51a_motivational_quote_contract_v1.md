# F5.1A — Optional motivational quote

Small product-presentation addition on the F5.1 output contract. No Gemini. No CODIFY. Frozen labels unchanged. F4 analytics, salience, evidence policy, F4.7 gate logic, and the T8 A/B ceiling were not redesigned.

## 1. Schema change

`HealthCoachResult.motivational_quote: str | None`

Separate from `primary_message`, `subtext`, `insight`, `recommendation`, and `supporting_metric_facts`. No `author` field. Legacy payloads default to `null`.

It does not change `status`, salience, or any F4.7 flag.

## 2. Prompt change

Smallest honor block in `HEALTH_COACH_INSTRUCTIONS`:

- optional one-line unattributed encouragement relevant to `primary_message`
- not evidence, rationale, a metric claim, medical advice, or a recommendation
- no hidden action when `final_recommendation_allowed=false`
- no physiological-state interpretation
- no invented attribution
- target one sentence / ~15 words (guideline, not a hard fail)
- null on the quiet path

Examples in the product brief are style only. No quote catalog.

## 3. Quiet-path behavior

If `status=NO_SIGNIFICANT_NEW_PATTERN` or `primary_message` is null:

- sanitizer sets `motivational_quote=null`
- TRACE `motivational_quote_removed_on_quiet_path=true` when the model had sent one
- guard fails if a leftover quote remains

No encouragement card when nothing was surfaced.

## 4. Recommendation-boundary behavior

F4.7 is unchanged. The quote is not an authorization path and must not be written into `recommendation`.

When `final_recommendation_allowed=false`:

- generic encouragement may remain (`Consistency is what turns progress into habit.`)
- rec-like language in the quote still fails the existing phrase scan (`You should take a 45-minute walk today.`)

## 5. T8 interaction

The quote stays motivational, not analytical. Prompt forbids body/nervous-system/heart-health interpretations. MVP does not add a T8 quote blacklist. Quality of that rule is later CODIFY / LLM-as-judge.

## 6. Guard changes

- quiet path / missing primary → `motivational_quote` must be null
- `_guard_text` now includes the quote so F4.7 leak checks cover it
- no inspirational-quality check
- no large quote/phrase dictionary

## 7. Display change

Backend/demo order:

```
PRIMARY MESSAGE
SUBTEXT
MOTIVATIONAL QUOTE
RATIONALE
RECOMMENDATION
SUPPORTING FACTS
```

No frontend implementation.

## 8. TRACE change

F4.2 unchanged. No CoT.

Visible:

- `raw_model_output.motivational_quote`
- final `structured_result.motivational_quote`
- `output_contract.model_motivational_quote_present`
- `output_contract.motivational_quote_present`
- `output_contract.motivational_quote_removed_on_quiet_path`
- `generation.motivational_quote`

## 9. Offline A1 / B1 / B3 / E1 / C4 examples

Illustrative quotes only. Not hardcoded product copy.

| Case | Quote allowed? | Example shape | Must not |
|---|---|---|---|
| **A1** | yes, optional | sleep-relevant encouragement | new health claim; rec unless F4.7 allows |
| **B1** | **no** | sanitizer nulls model quote | any encouragement card |
| **B3** | yes, generic | “Consistency is what turns progress into habit.” | hidden “maintain your routine” action |
| **E1** | yes, sleep-relevant | rest/performance encouragement | respiratory / cardiovascular interpretation |
| **C4** | yes, sleep-relevant | rest encouragement | stress / recovery / HRV-spread reading |

## 10. Tests

Added in `tests/test_output_interpretation.py`:

- legacy payload defaults quote to null
- A1 quote may exist and stays separate from insight/rec
- B1 quiet path removes quote; TRACE records the removal
- B3 generic encouragement survives; rec still blocked
- E1/C4 example quotes contain no system-health / spread language
- guard rejects leftover quiet-path quote
- existing rec-phrase leak scan catches action language in the quote
- display order includes MOTIVATIONAL QUOTE

Focused related suite passed. Full pytest **394 passed**.

## 11. Full pytest

**394 passed** (2026-08-22). Prior F5.1 baseline was 387.

## 12. Files changed

- `agent/schemas.py`
- `agent/instructions.py`
- `agent/display.py`
- `agent/runner.py`
- `app/output_contract.py`
- `app/output_guard.py`
- `evals/trace_schema.py`
- `tests/test_output_interpretation.py`
- `tests/test_recommendation_boundary.py` (prompt-string fixture)
- `evals/results/assignment4_tracker_v1.md`
- `evals/results/f51a_motivational_quote_contract_v1.md`

## 13. Remaining risks

1. **Relevance / tone** are not deterministic. A sleep card can still get an off-theme quote until CODIFY.
2. **Hidden actions** that do not match the small existing rec-phrase list can still sneak through (`Do a 45-minute walk today` without “you should”).
3. **T8 in quotes** is prompt-only.
4. **Length** is a guideline. 16–18 words will not fail the guard.
5. Streamlit still prints Theme / Insight (UI out of scope).

### Future CODIFY (not implemented)

| Grader | Class |
|---|---|
| quiet-path quote is null | deterministic |
| quote relevance to `primary_message` | LLM-as-judge |
| brevity / tone | LLM-as-judge + human |
| no unsupported health claim | LLM-as-judge + human |
| no hidden recommendation | deterministic phrases + human |

## Stop

No Gemini. No CODIFY. No directive categories. No frozen-eval edits. No commit.
