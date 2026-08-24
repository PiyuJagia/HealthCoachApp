# F7.1 — Post-remediation evaluation synthesis v1

Analysis only. No product, prompt, analytics, guard, grader, or frozen-label changes. No Gemini rerun.

**Scored run:** `post_remediation_v1`  
**Official traces:** `evals/results/post_remediation_traces_v1/`  
**Sources:** `post_remediation_review_bundle_v1.md`, `post_remediation_comparison_v1.md`, `post_remediation_taxonomy_status_v1.md`, `post_remediation_codify_summary_v1.json`, `post_remediation_run_config_v1.json`

**Readiness decision:** READY WITH ACCEPTED MVP LIMITATIONS

---

## 1. Run integrity

| Check | Result |
|---|---|
| All 15 official scenarios completed | Yes. Official index has A1–A4, B1–B3, C1–C4, D1–D3, E1. |
| One consistent system | Yes. Git HEAD `f6bdc0096939ed29298f289cc66799f4e1b85d4b`, model `gemini-3.6-flash` via ADK `2.7.1`, instruction SHA `ce180727…`, catalog `codify_v1`. No product patch mid-run. |
| Scored run id | `post_remediation_v1` |
| Abandoned B2 503 excluded | Yes. `58f212ef-…` is leftover `TEMPORARY_MODEL_UNAVAILABLE`. Scored B2 is `acd5ca80-…`. |
| Superseded B1 excluded | Yes. Official B1 is `fa304baa-…`, not `ae17a8a3-…`. |
| Frozen baseline labels untouched | Yes. `baseline_human_review_bundle_v1.md` / extract remain 5 PASS / 10 FAIL. F3 taxonomy files not mutated. |

**Integrity notes (not scoring defects):**

1. Working tree was dirty at freeze (expected: F4–F6 remediation not committed). Same dirty tree for the whole run.
2. B2 first attempt 503; resume used the same frozen code and completed a product TRACE. Provider failure ≠ scenario failure.
3. B1 index `run_status=ERROR` is an F1 completeness quirk (`policy` null because no RAG). Product TRACE is valid quiet-path.
4. Run-config timestamp was rewritten on resume (`22:22` first write vs `23:19` current file). HEAD, model, catalog, and scenario set are unchanged.
5. Run-config path list has a cosmetic typo (`gent/display.py`).

No integrity issue requires another Gemini run.

---

## 2. Three scores (do not conflate)

| ID | Layer | Score | Meaning |
|---|---|---|---|
| **A** | Frozen baseline human scenario score | **5 PASS / 10 FAIL (33%)** | Historical F2 labels. Frozen. Not overwritten. |
| **B** | V2 scenario-quality score | **15 PASS / 0 FAIL / 0 NEEDS_REVIEW (100%)** | New review against the *remediated* product philosophy. Not a copy of A. |
| **C** | CODIFY deterministic contract score | **168 PASS / 0 FAIL / 102 NA** of 270 evaluations | Structural contracts held. Not a quality score. |

Improvement is **not** “33% → 100%.” The frozen 5/10 stays the baseline record. V2 quality and contract compliance are separate later measurements.

---

## 3. Baseline vs V2 scenario summary

| scenario_id | baseline human | baseline status | V2 status | V2 primary_message | V2 rec? | CODIFY | V2 assessment | change | remaining issue |
|---|---|---|---|---|---|---|---|---|---|
| A1 | PASS | INSIGHT | RECOMMENDATION | Sleep 7.1→5.8h | Yes (caffeine earlier) | 11/0/7 | PASS | IMPROVED | Accepted caffeine latch + mild quote-as-advice |
| A2 | PASS | RECOMMENDATION | INSIGHT | Exercise, HRV, VO2, sleep up; RHR down | No | 12/0/6 | PASS | IMPROVED | T11 overlap with A3; list-like Level B primary |
| A3 | PASS | RECOMMENDATION | INSIGHT | Exercise, HRV, VO2 up; RHR down | No | 12/0/6 | PASS | IMPROVED | T11 still present (same 2026-07-18 world) |
| A4 | PASS | INSIGHT | RECOMMENDATION | Sleep down alongside late-afternoon caffeine | Yes | 11/0/7 | PASS | IMPROVED | Accepted caffeine latch + mild quote-as-advice |
| B1 | FAIL | INSIGHT | NO_SIGNIFICANT_NEW_PATTERN | null | No | 12/0/6 | PASS | IMPROVED | Index completeness quirk only |
| B2 | PASS | INSIGHT | INSIGHT | Exercise up; VO2 maintained | No | 12/0/6 | PASS | BASELINE_EVAL_ISSUE | Original recovery premise still weak |
| B3 | FAIL | NO_SIGNIFICANT_NEW_PATTERN | INSIGHT | RHR, HRV, VO2 maintain long-term gains | No | 13/0/5 | PASS | IMPROVED | None as contract |
| C1 | FAIL | INSIGHT | RECOMMENDATION | Sleep 5.83h alongside late-afternoon caffeine | Yes | 10/0/8 | PASS | IMPROVED | Accepted caffeine latch |
| C2 | FAIL | INSIGHT | RECOMMENDATION | Sleep 6.0h | Yes | 10/0/8 | PASS | IMPROVED | Unused late-work/alcohol (not required equally) |
| C3 | FAIL | RECOMMENDATION | INSIGHT | Exercise/workouts up; steps down | No | 11/0/7 | PASS | IMPROVED | None required |
| C4 | FAIL | INSIGHT | RECOMMENDATION | Sleep down; exercise up | Yes | 11/0/7 | PASS | IMPROVED | Latch + accepted quote bar; spread not forced primary |
| D1 | FAIL | RECOMMENDATION | INSIGHT | Exercise up; modest sleep/RHR/HRV | No | 11/0/7 | PASS | IMPROVED | None as contract |
| D2 | FAIL | RECOMMENDATION | INSIGHT | Exercise/workouts up; June 10 missing | No | 11/0/7 | PASS | IMPROVED | None as contract |
| D3 | FAIL | INSIGHT | INSIGHT | Exercise, workouts, steps up | No | 10/0/8 | PASS | IMPROVED | VO2 not overclaimed; old 15-in-30 not reapplied |
| E1 | FAIL | INSIGHT | RECOMMENDATION | Sleep −18% to 5.8h | Yes | 11/0/7 | PASS | IMPROVED | Same-world latch as A1; mild quote-as-advice |

Status changes are not the quality verdict. A2/A3 moving RECOMMENDATION → INSIGHT is F4.7 + current policy, not a regression. A1/A4/C1/C2/C4/E1 moving to RECOMMENDATION is lifestyle-enabled R-07 when both gates are true.

**Change counts:** 14 IMPROVED · 0 REGRESSED · 0 UNCHANGED · 1 BASELINE_EVAL_ISSUE (B2) · 0 NEEDS_REVIEW

---

## 4. Taxonomy closure

F3 artifacts were not mutated. This is a new mapping.

| ID | Name | Status | Evidence |
|---|---|---|---|
| T1 | Lifestyle inaccessible | **CLOSED** | C1/C2/C3 called `get_lifestyle_context`. Caffeine/alcohol/late-work visible. C3 did not manufacture a caffeine problem. |
| T2 | As-of provenance | **CLOSED** | D1 HRV `as_of_date_available=false`, `gap_caveat_required=true`; partial-wear subtext. D2 names June 10 missing. History still used. |
| T3 | `data_sufficient` advisory | **CLOSED** | Replaced by F4.1 eligibility. D3 activity insight allowed; VO2 not overclaimed. Old 15-in-30 silence rule retired. |
| T4 | Longitudinal maintenance | **CLOSED** | B3 INSIGHT names RHR/HRV/VO2 `maintenance_of_gain`. Rec F4.7-blocked. |
| T5 | Low-salience insight | **CLOSED** | B1 quiet path. Steps +6.55% / exercise +3.87% remain analytical. |
| T6 | RR control excluded | **CLOSED** | E1 RR visible, control, not primary, not cardiorespiratory reassurance. |
| T7 | Output contract | **IMPROVED** | `primary_message` / subtext / rationale / quote / rec / stamped facts live. Residual: A2/A3 list-like Level B; Streamlit still Theme/Insight. |
| T8 | Physiological over-generalization | **IMPROVED** | No Level C user-state claims. E1 no longer “cardiovascular indicators remained stable.” Quote “recovery / well-being” is accepted MVP wording, not Level C. |
| T9 | Redundant retrieval | **NOT MEANINGFULLY TESTED** | Typical path is trends → lifestyle → one evidence call. Original second-lookup pattern not re-observed. |
| T10 | Eval design mismatch | **EVAL DESIGN ISSUE** | B2 still a weak recovery premise. V2 judged on merits. |
| T11 | Eval overlap | **STILL PRESENT** | A2 and A3 share 2026-07-18 and produce similar cards. Eval leftover. |
| T12 | Within-window spread | **CLOSED** | C4 HRV improving +5.56%, spread 2.61, `spread_context` stamped, not inverted to stress/decline. |

**Genuinely closed product root causes:** T1, T2, T3 (replaced), T4, T5, T6, T12.  
**Improved symptoms:** T7, T8.  
**Eval leftovers:** T10, T11.

---

## 5. Remediation impact (failure → root cause → fix → V2)

### T5 / B1 low-salience

- **Problem:** Modest steps/exercise became INSIGHT.
- **Remediation:** F4.6 salience (`insight_worthy`).
- **V2:** B1 → `NO_SIGNIFICANT_NEW_PATTERN`; user fields null.
- **Outcome:** CLOSED.

### T4 / B3 maintenance blind spot

- **Problem:** Recent stability treated as “nothing happened.”
- **Remediation:** F4.5 `maintenance_of_gain`.
- **V2:** B3 INSIGHT names RHR/HRV/VO2 maintenance; rec null.
- **Outcome:** CLOSED.

### T1 / C-family lifestyle access

- **Problem:** Caffeine/alcohol/late-work existed in SQLite but no tool.
- **Remediation:** F4.4 `get_lifestyle_context` + policy `available_inputs`.
- **V2:** C1/C2/C3 lifestyle visible. C1 non-causal. C3 no manufactured caffeine story.
- **Outcome:** CLOSED (access). Residual UX: C2 unused confounders — accepted, not a reopen of T1.

### T2 / D1–D2 provenance

- **Problem:** Missing same-day wear invisible; HIGH-confidence recs.
- **Remediation:** F4.1 as-of / gap flags + F4.2-visible provenance.
- **V2:** D1 partial-wear language; D2 names June 10 missing; recs blocked.
- **Outcome:** CLOSED.

### T3 / D3 maturity

- **Problem:** `data_sufficient=false` ignored; insight still surfaced.
- **Remediation:** F4.1 claim eligibility; retire advisory binary.
- **V2:** Activity insight under current eligibility; VO2 not overclaimed.
- **Outcome:** CLOSED (contract replaced, not “all insight blocked”).

### T6 / E1 respiratory control

- **Problem:** RR excluded; “cardiovascular indicators remained stable.”
- **Remediation:** F4.8 control metric.
- **V2:** RR visible, not primary, not reassurance; sleep primary.
- **Outcome:** CLOSED.

### T12 / C4 spread

- **Problem:** HRV volatility invisible; mean hid day-to-day swing.
- **Remediation:** F4.9 `within_window_spread`.
- **V2:** Level improving vs spread 2.61; not inverted; not forced primary.
- **Outcome:** CLOSED.

### T7–T8 / A-family + interpretation

- **Problem:** Report-like cards; mixed-signal collapse / Level C risk.
- **Remediation:** F5.1 output contract + A/B ceiling + stamped facts.
- **V2:** Concise primaries; facts overwrite model lists; no Level C.
- **Outcome:** IMPROVED. Residual list-like A2/A3 primaries acceptable Level B.

### F4.7 recommendation boundary

- **Problem:** Authorized evidence treated as permission to recommend (live B3).
- **Remediation:** `final_recommendation_allowed = worthy AND authorized`.
- **V2:** B3/A2/A3/C3/D1–D3 rec null when either gate false. A1/C1/C2/C4/E1 rec only when both true.
- **Outcome:** CLOSED as a contract. Caffeine rec on dual-true worlds is permitted architecture, not a gate leak.

---

## 6. CODIFY result

| Metric | Value |
|---|---|
| Catalog | 18 deterministic graders (unchanged) |
| Scenario coverage | 15 / 15 |
| Evaluations | 270 |
| PASS | 168 |
| FAIL | **0** |
| NOT_APPLICABLE | 102 |
| Failed grader IDs | none |

**0 deterministic FAIL means:** validated structural contracts held (maturity, lifestyle wiring, salience quiet path, F4.7 gates, RR control, spread vs level, output-contract shape, stamped facts, quiet-path quote null).

**0 deterministic FAIL does not mean:** every card is the best possible prioritization, every confounder is discussed, or quotes never sound advisory. Those are semantic / product-quality judgments (score B), not contract grades (score C).

---

## 7. Semantic residuals

### A. Submission-blocking

**None.** No safety leak, no Level C physiological-state claim, no hidden CoT, no fabricated same-day values, no rec when F4.7 is false.

### B. Worth improving later (not blocking)

- C2 unused late-work/alcohol in prose (access exists; selection is caffeine).
- A2/A3 list-like multi-metric primaries.
- Streamlit still Theme/Insight (display lag, not TRACE contract).
- Optional later LLM-as-judge on the 9 semantic specs.

### C. Accepted MVP limitation

- Motivational quote as mild habit-shift advice on sleep+caffeine worlds (A1/A4/C2/E1; C4 milder than F5.2). Catalogued in F5.1A / `sem_quote_not_hidden_advice`.
- Caffeine recommendation latch once `caffeine_mg` is visible and both F4.7 gates are true (A1/A4/C1/C2/C4/E1). Association language held; C1 explicit non-causal.
- Equal confounder discussion is **not** a product requirement.

### D. Eval / infrastructure issue

- T10: B2 recovery premise remains weak.
- T11: A2/A3 share one as-of world.
- B1 F1 completeness checker requires `policy.overall_verdict` on a valid no-RAG quiet path.
- Provider 503 on first B2 attempt (transient; resume scored).

Do not invent new issues. Mixed-signal compression: A4 omits some improving metrics from the card (partial, not collapse). B2 omits non-primary sleep −6.47%. Neither is a T8 Level C failure.

---

## 8. Regressions

**No meaningful product regressions.**

Items that look like status flips but are not worse:

| Observation | Why it is not a regression |
|---|---|
| A2/A3 RECOMMENDATION → INSIGHT | Rec correctly withheld (`authorized=false`). Structure improved. |
| A1/A4/C1/C2/C4/E1 INSIGHT → RECOMMENDATION | Lifestyle now supplies R-07 inputs; both F4.7 gates true. Documented latch, not a sneak-in rec. |
| B2 first-pass 503 | Provider; scored TRACE is healthy INSIGHT. |

Remediating quote-as-advice or caffeine latch now would touch prompt/policy after a clean 15-scenario freeze and would destablize already validated F4.7 / F5.1 contracts. Not warranted before submission.

---

## 9. Assignment 4 readiness decision

**READY WITH ACCEPTED MVP LIMITATIONS**

The project demonstrates a rigorous TRACE loop:

baseline traces → human review → taxonomy → contract remediation → observability → CODIFY → full post-remediation measurement → synthesis with known residuals.

That is the Assignment 4 bar. Perfection is not the bar.

Why not “ONE MORE TARGETED REMEDIATION”: remaining issues are accepted MVP or eval-design. None are safety/contract failures. Another product pass would reopen a frozen measured system without a blocking defect.

Why not unqualified “READY TO FREEZE” without the MVP clause: quote-as-advice and caffeine latch are real user-facing limitations and should be named in the writeup, not hidden.

---

## 10. Final validation recommendation

**A. No more Gemini runs.** Use `post_remediation_v1` as the final measured run.

A second frozen run would only be justified by a product change or a lost/corrupt official TRACE. Neither is true. Cosmetic confidence is not a reason.

Final validation = writeup + evidence packaging from this run, not another live call.

---

## 11. Assignment 4 evidence map

| TRACE stage | Artifact(s) | What it proves |
|---|---|---|
| Target scenarios | `healthcoach_trace_baseline_v1` / F1 scenario set A1–E1 | Fixed 15-scenario evaluation world |
| Baseline traces | `evals/traces/`, `baseline_trace_index_v1.csv` | Pre-remediation Gemini behavior |
| Human review | `baseline_human_review_bundle_v1.md`, `baseline_human_review_extract_v1.json` | Frozen **5 PASS / 10 FAIL** |
| Failure taxonomy | `failure_taxonomy_v1.md`, `failure_taxonomy_counts_v1.csv` | T1–T12 historical clusters (not mutated) |
| Remediation | F4.1–F4.9 + F5.1/F5.1A inspection artifacts | Root-cause contracts implemented |
| Enhanced observability | `f42_llm_observability_v1.*`; V2 `adk_pre_model_request` | LLM-visible TRACE, no hidden CoT |
| CODIFY | `evals/codify/`, `f60_codify_v1.md`, V2 CODIFY JSON | Repeatable contract graders |
| Post-remediation V2 | `post_remediation_traces_v1/`, review bundle, index, run config | Full 15-scenario measurement on frozen remediated system |
| Baseline-vs-V2 comparison | `post_remediation_comparison_v1.md`, this synthesis | 14 IMPROVED, 0 REGRESSED, B2 eval-design |
| Taxonomy remapping | `post_remediation_taxonomy_status_v1.md` | Closed vs leftover classes |
| Final conclusions | this file | Ready with accepted MVP limitations; no extra Gemini |

---

## 12. Recommended submission / final-validation steps

1. Write the Assignment 4 narrative as: failure → root cause → remediation → `post_remediation_v1` measurement.
2. Keep the three scores distinct (A frozen 5/10, B V2 15/0, C 168/0/102).
3. Name accepted limitations: quote-as-advice, caffeine latch, C2 unused confounders, T11 overlap.
4. Package the evidence map above. Do not overwrite F1–F3.
5. Do not remediate. Do not rerun Gemini. Do not mark Assignment 4 SUBMITTED until the writeup is packaged.

---

## STOP

No remediation. No Gemini. No grader changes. No product changes. No commit.
