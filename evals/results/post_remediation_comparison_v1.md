# Post-remediation comparison v1

Run: `post_remediation_v1`  
Frozen human baseline: **5 PASS / 10 FAIL** (unchanged)  
V2 scenario-quality labels below are **new**. They are not copies of the frozen labels.

Contract compliance is separate: **0 deterministic CODIFY fails** across 15 scenarios (168 pass / 102 NA). That is not the scenario-quality score.

Official traces: latest product TRACE per scenario. Leftover B2 `58f212ef-…` is the first-pass 503 and is **not** scored. Leftover B1 `ae17a8a3-…` is superseded by `fa304baa-…`.

---

## 15-row comparison

| scenario_id | family | baseline_human_label | baseline_status | baseline_theme / core output | V2_status | V2_primary_message | V2_recommendation? | det_pass | det_fail | det_NA | semantic_review_status | overall_change | remaining_issue |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | A | PASS | INSIGHT | Sleep Duration Shortening Across Recent Week (report-like; rec blocked) | RECOMMENDATION | Sleep 7.1→5.8h | Yes — shift caffeine earlier (R-07, both F4.7 gates true) | 11 | 0 | 7 | REVIEWED — primary sleep; Level A/B; quote mildly advisory | IMPROVED | Accepted caffeine latch + quote-as-advice |
| A2 | A | PASS | RECOMMENDATION | Exercise Consistency and Cardiovascular Indicators | INSIGHT | Exercise, HRV, VO2, sleep up; RHR down | No — authorized=false | 12 | 0 | 6 | REVIEWED — Level B named multi-metric; F4.7 honored | IMPROVED | T11 overlap with A3; rec correctly withheld |
| A3 | A | PASS | RECOMMENDATION | Cardiovascular metrics improving with exercise (same 2026-07-18 world as A2) | INSIGHT | Exercise, HRV, VO2 up; RHR down | No — authorized=false | 12 | 0 | 6 | REVIEWED — conservative Level B | IMPROVED | **T11 still present** (same as-of as A2) |
| A4 | A | PASS | INSIGHT | Sleep Duration Decline (report-like; rec blocked) | RECOMMENDATION | Sleep down alongside late-afternoon caffeine | Yes — move caffeine earlier | 11 | 0 | 7 | REVIEWED — association language; quote mildly advisory | IMPROVED | Accepted caffeine latch + quote-as-advice |
| B1 | B | FAIL | INSIGHT | Modest steps/exercise elevated as insight | NO_SIGNIFICANT_NEW_PATTERN | null | No | 12 | 0 | 6 | REVIEWED — quiet path correct | IMPROVED | Index ERROR is F1 completeness quirk (`policy` null; no RAG). Product TRACE valid |
| B2 | B | PASS | INSIGHT | Weak “recovery” premise; exercise/cardio stability | INSIGHT | Exercise minutes up; VO2 maintained | No — authorized=false | 12 | 0 | 6 | REVIEWED — evaluated on merits, not old recovery rubric | BASELINE_EVAL_ISSUE | Original scenario still weak; first attempt 503 then resume succeeded |
| B3 | B | FAIL | NO_SIGNIFICANT_NEW_PATTERN | Missed maintenance of prior gains | INSIGHT | RHR, HRV, VO2 maintain gains vs long-term reference | No — F4.7 blocked | 13 | 0 | 5 | REVIEWED — maintenance as INSIGHT | IMPROVED | None as contract; quote is generic encouragement |
| C1 | C | FAIL | INSIGHT | Sleep decline; lifestyle inaccessible | RECOMMENDATION | Sleep 5.83h alongside late-afternoon caffeine | Yes — move afternoon caffeine earlier | 10 | 0 | 8 | REVIEWED — lifestyle visible; “co-occurrence does not prove causation” | IMPROVED | Accepted caffeine latch |
| C2 | C | FAIL | INSIGHT | Sleep decline; caffeine/late-work inaccessible | RECOMMENDATION | Sleep 6.0h | Yes — shift caffeine earlier | 10 | 0 | 8 | REVIEWED — access closed; equal confounder coverage **not** required | IMPROVED | Unused late-work/alcohol (accepted MVP UX); quote mildly advisory |
| C3 | C | FAIL | RECOMMENDATION | Could not observe caffeine vs stable sleep | INSIGHT | Exercise/workouts up; steps down | No | 11 | 0 | 7 | REVIEWED — caffeine visible, not minted as a problem; sleep stable | IMPROVED | None required |
| C4 | C | FAIL | INSIGHT | Sleep decline; HRV spread invisible | RECOMMENDATION | Sleep down; exercise up | Yes — caffeine earlier (latch) | 11 | 0 | 7 | REVIEWED — HRV improving + spread 2.61 distinct; quote safer than F5.2 | IMPROVED | Accepted quote-as-advice bar; caffeine latch; spread not required as primary |
| D1 | D | FAIL | RECOMMENDATION | Improving HRV without as-of missing flag | INSIGHT | Exercise up; modest sleep/RHR/HRV | No | 11 | 0 | 7 | REVIEWED — partial wear / missing same-day HRV visible; historical trend used | IMPROVED | None as contract |
| D2 | D | FAIL | RECOMMENDATION | Full sync gap invisible; HIGH-confidence rec | INSIGHT | Exercise/workouts up; June 10 missing | No | 11 | 0 | 7 | REVIEWED — gap acknowledged; old `data_sufficient` binary not applied | IMPROVED | None as contract |
| D3 | D | FAIL | INSIGHT | All metrics `data_sufficient=false` but insight still surfaced | INSIGHT | Exercise, workouts, steps up | No | 10 | 0 | 8 | REVIEWED — F4.1 eligibility; VO2 not overclaimed; insight not blocked by retired 15-in-30 | IMPROVED | Lifestyle tool not called (NA for f44; not required) |
| E1 | E | FAIL | INSIGHT | Sleep decline; RR invisible; “cardiovascular indicators stable” | RECOMMENDATION | Sleep −18% to 5.8h | Yes — afternoon caffeine earlier | 11 | 0 | 7 | REVIEWED — RR control, not reassurance; sleep primary | IMPROVED | Same-world caffeine latch as A1; quote mildly advisory |

---

## Change counts (scenario quality, not contract %)

| overall_change | n | scenarios |
|---|---|---|
| IMPROVED | 14 | A1–A4, B1, B3, C1–C4, D1–D3, E1 |
| REGRESSED | 0 | — |
| UNCHANGED | 0 | — |
| BASELINE_EVAL_ISSUE | 1 | B2 |
| NEEDS_REVIEW | 0 | — |

V2 scenario-quality: **15 PASS** under the remediated product philosophy.  
Frozen baseline labels remain **5 PASS / 10 FAIL**.

---

## Contract vs quality

| Layer | Result |
|---|---|
| Deterministic contract compliance | 270 evaluations; 168 PASS; 0 FAIL; 102 NOT_APPLICABLE |
| Semantic / product quality | Reviewed in `post_remediation_review_bundle_v1.md`; no new Level C; T6/T12 prose held |
| User-facing remaining issues | Accepted MVP: caffeine latch (A1/A4/C1/C2/C4/E1), C2 unused confounders, quote-as-advice, T11 overlap, Streamlit Theme/Insight UI |

Do not treat 0 contract fails as “the product is finished.” The cards are now correctly structured and the original root-cause failures are closed or improved; remaining items are UX / eval-design / accepted quote limitations.
