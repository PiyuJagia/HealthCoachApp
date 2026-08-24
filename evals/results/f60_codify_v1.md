# F6.0 — CODIFY v1

Convert validated F4/F5 remediation behavior into repeatable evaluators. No product behavior change. No Gemini invocation. Frozen human labels and taxonomy were not rewritten.

F5.1A is **accepted for MVP** with the F5.2 C4 motivational-quote limitation. That issue is catalogued as a semantic/human gap, not a new deterministic classifier.

---

## 1. Audit (what existed before CODIFY)

| Layer | Already present | What it did | What it was not |
|---|---|---|---|
| Baseline dataset | `evals/datasets/healthcoach_trace_baseline_v1.jsonl` + `evals/baseline_dataset.py` | 15 scenarios, must_do/must_not_do, data-support inspection | Not machine-graded against TRACE |
| Frozen human review | `baseline_human_review_bundle_v1.md` + extract JSON | 5 PASS / 10 FAIL historical labels | Historical baseline only |
| Failure taxonomy | `failure_taxonomy_v1.md` / counts CSV | T1–T12 clusters | No executable assertions |
| TRACE schema | `evals/trace_schema.py` | Persist signals, tools, F4.2 model_calls, output_contract, boundary | Capture, not grade |
| Deterministic inspection utilities | `evals/*_inspection.py`, `scripts/inspect_eval_baseline.py` | One-off F4.1–F4.9 inspections vs SQLite | Not a TRACE grader suite |
| Scenario runners | `scripts/run_eval_baseline.py`, targeted F4.4/F4.7/F4.8.1/F5.2 scripts | Produce traces | No post-run contract matrix |
| Product unit tests | `tests/test_maturity.py`, salience, spread, boundary, output_interpretation, … | Protect implementation internals | Do not score an archived TRACE |
| Graders | **None** | README said graders come after discovery | CODIFY had not started |

**Already codified (implementation tests):** maturity/eligibility, weekly claim_semantics, lifestyle lookup, longitudinal flags, salience, F4.7 gate, RR control, HRV spread, output-contract stamping, quiet-path quote null.

**Depended on manual review:** primary-message quality, T8 Level C, mixed-signal collapse, causal overstatement paraphrases, rationale quality, quote-as-advice, C2 confounder collapse, cardiorespiratory reassurance wording.

CODIFY adds TRACE-level graders on top of those unit tests. It does not replace frozen labels.

---

## 2. Result schema

Each grader emit (`evals/codify/schema.py`):

| Field | Meaning |
|---|---|
| `scenario_id` | Baseline scenario |
| `grader_id` | Stable id |
| `grader_type` | `DETERMINISTIC` / `LLM_AS_JUDGE` / `HUMAN_REVIEW` / `HYBRID` |
| `contract` | F4.x / F5.x |
| `taxonomy` | T1–T12 when linked |
| `outcome` | `pass` / `fail` / `not_applicable` |
| `observed_value` | Structured observation |
| `expected_behavior` | Contract sentence |
| `evidence` | TRACE provenance |
| `reason` | Why |
| `trace_run_id` | Link to TRACE |
| `frozen_human_pass_fail` | Historical label, metadata only |

---

## 3. Deterministic graders created

18 executable TRACE graders in `evals/codify/deterministic.py`:

| grader_id | Contract | Protects |
|---|---|---|
| `f41_established_trend_requires_trend_allowed` | F4.1 | Established ≠ immature |
| `f41_gap_and_as_of_flags_present` | F4.1 | as-of / gap flags remain on every trend |
| `f43_weekly_cannot_bypass_trend_eligibility` | F4.3 | Weekly comparison/rec support cannot exceed trend gates |
| `f44_lifestyle_inputs_require_lookup` | F4.4 | `caffeine_mg` / `alcohol_units` require `get_lifestyle_context` |
| `f45_maintenance_of_gain_may_surface` | F4.5 | Insight-worthy maintenance cannot be quieted |
| `f46_t5_unworthy_not_elevated` | F4.6 / T5 | `insight_worthy=false` ≠ INSIGHT/RECOMMENDATION |
| `f47_recommendation_requires_both_gates` | F4.7 | worthy AND authorized; blocked rec is null |
| `f47_rec_phrase_leak_when_blocked` | F4.7 | Existing product rec-phrase list only; no new blacklist |
| `f48_t6_control_not_primary` | F4.8 / T6 | Control metrics not primary; cannot authorize recs alone |
| `f49_t12_spread_distinct_from_level` | F4.9 / T12 | Spread ≠ level; HRV spread cannot become decline/primary |
| `f51_output_contract_shape` | F5.1 / T7 | Elevated status needs primary; quiet path has none |
| `f51_facts_are_system_stamped` | F5.1 | Facts origin `deterministic_output_contract` |
| `f51a_quote_null_on_quiet_path` | F5.1A | Quote separate; null on quiet path |
| `scenario_b1_quiet_path` | T5 | B1 regression control |
| `scenario_b3_maintenance_without_rec` | T4 / F4.7 | B3 INSIGHT, rec blocked |
| `scenario_e1_rr_control` | T6 | E1 RR control, sleep may stay primary |
| `scenario_c4_spread_distinct` | T12 | C4 HRV level vs spread_context |
| `scenario_a_family_mature_data` | F4.1 | A-family keeps an established allowed trend |

C2 has **no** deterministic single-cause rule. Lifestyle access is graded; confounder collapse is semantic/human only.

---

## 4. Semantic graders proposed (not executed)

Gemini was not called. Specs live in `evals/codify/catalog.py` / `semantic.py`.

| grader_id | Type | Why not deterministic |
|---|---|---|
| `sem_primary_selects_highest_priority` | LLM-AS-JUDGE | Right notice ≠ field exists |
| `sem_t8_no_level_c` | LLM-AS-JUDGE | No phrase dictionary for T8 |
| `sem_mixed_signals_preserved` | LLM-AS-JUDGE | Omission vs collapse is judgment |
| `sem_association_not_causation` | HYBRID | Guard has a small causal list; paraphrase is human/LLM |
| `sem_rationale_quality` | HUMAN_REVIEW | Voice / grounding quality |
| `sem_quote_not_hidden_advice` | LLM-AS-JUDGE | C4 accepted MVP limitation; no new classifier |
| `sem_c2_confounders_not_collapsed` | HUMAN_REVIEW | Accepted MVP caffeine selection |
| `sem_t6_no_cardiorespiratory_reassurance` | LLM-AS-JUDGE | Structured control is deterministic; prose is not |
| `sem_t12_spread_not_stress` | LLM-AS-JUDGE | Stress/recovery wording is semantic |

---

## 5. Coverage matrix

| Taxonomy / Contract | Deterministic | LLM Judge | Human | Current coverage | Remaining gap |
|---|---|---|---|---|---|
| T1 / F4.4 lifestyle access | yes | — | — | implemented | Causation paraphrase |
| T1 / C2 confounders | no (by design) | optional | yes | spec_only | Accepted MVP caffeine selection |
| T2 / F4.1 as-of + gap | yes | — | — | implemented | Prose caveat honor |
| T2–T3 / F4.3 weekly bypass | yes | — | — | implemented | Model treating a week as a trend in prose |
| T3 / F4.1 eligibility | yes | — | — | implemented | — |
| T4 / F4.5 maintenance | yes | — | — | implemented | Level C “cardiovascular health” wording |
| T5 / F4.6 / B1 | yes | — | — | implemented | — |
| F4.7 rec boundary | yes | — | — | implemented | Novel advice wording beyond existing phrases |
| T6 / F4.8 control role | yes | yes (spec) | yes | structured implemented | Cardiorespiratory reassurance prose |
| T7 / F5.1 shape + facts | yes | yes (spec) | yes | shape implemented | Primary selection / rationale quality |
| T7 / F5.1A quote quiet-path | yes | yes (spec) | yes | quiet-path implemented | Quote-as-advice (C4 accepted) |
| T8 Level C | no | yes (spec) | yes | spec_only | Needs judge; no keyword ban |
| T12 / F4.9 spread vs level | yes | yes (spec) | yes | structured implemented | Stress/recovery wording |
| T9 redundant retrieval | no | — | optional | not in v1 | Out of F6 MVP |
| T10 / T11 eval infra | no | — | historical | frozen only | Not product graders |

Structured JSON/CSV: `evals/results/f60_codify_coverage_v1.json` / `.csv`.

---

## 6. Scenarios protected

| Scenario | Deterministic protection | Not forced |
|---|---|---|
| B1 | quiet path / T5 | — |
| B3 | maintenance INSIGHT, rec blocked | — |
| C2 | lifestyle lookup if inputs present | no single-cause rule |
| E1 | RR control, not primary | reassurance prose = judge |
| C4 | HRV level vs spread | quote-as-advice accepted |
| A-family | mature established+allowed trend | primary quality = judge |

---

## 7. F5.2 smoke (offline, existing traces)

`scripts/run_codify.py` graded the six F5.2 traces. No Gemini.

| | |
|---|---|
| scenarios | 6 |
| deterministic results | 108 |
| pass | 68 |
| fail | **0** |
| not_applicable | 40 |

Artifact: `evals/results/f60_codify_f52_smoke_v1.json`.

---

## 8. Frozen labels

Extract remains **5 PASS / 10 FAIL**. CODIFY outcomes are a separate layer. `frozen_human_pass_fail` is attached as metadata and is never used as the grader verdict.

F5.1A accepted MVP limitation: C4 quote-as-hidden-advice is documented, not remediated, and not turned into a brittle keyword rule.

---

## 9. Tests

- `tests/test_codify.py` — schema, pass/fail/NA for each contract family, regression controls, frozen-label integrity, F5.2 smoke
- Focused: **21 passed**
- Full pytest: **415 passed** (was 394)

---

## 10. Files

Added:

- `evals/codify/schema.py`
- `evals/codify/trace_access.py`
- `evals/codify/catalog.py`
- `evals/codify/deterministic.py`
- `evals/codify/semantic.py`
- `evals/codify/runner.py`
- `evals/codify/__init__.py`
- `tests/test_codify.py`
- `scripts/run_codify.py`
- `evals/results/f60_codify_v1.md`
- `evals/results/f60_codify_coverage_v1.json`
- `evals/results/f60_codify_coverage_v1.csv`
- `evals/results/f60_codify_f52_smoke_v1.json`

Product code, prompts, schemas, analytics, guard, frozen labels, and taxonomy were not changed.

---

## 11. Known gaps

1. LLM-as-judge and human specs are registered, not executed.
2. T8, mixed signals, quote-as-advice, C2 confounder collapse remain judgment.
3. T9 redundant retrieval is not in v1.
4. Pre-F5 traces without `output_contract` yield `not_applicable` on F5.1 fact/shape graders.
5. F5.1A C4 quote FAIL is an accepted MVP limitation.

---

## 12. Decisions

| Question | Answer |
|---|---|
| Is CODIFY complete? | **YES for v1** — deterministic graders exist, are tested, and coverage/gaps are documented. |
| Ready for full 15-scenario post-remediation Gemini evaluation? | **YES.** Run measurement only. Score with these graders. Do not treat semantic gaps or the accepted C4 quote limitation as new product defects to fix mid-rerun. |

STOP. No full 15-scenario Gemini run. No remediation. No commit.
