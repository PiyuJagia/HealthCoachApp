# Post-remediation review bundle v1

New V2 review. Does **not** overwrite `baseline_human_review_bundle_v1.md` or the frozen extract.

Run: `post_remediation_v1`  
Model: `gemini-3.6-flash` via ADK  
CODIFY catalog: `codify_v1` (invoked as-is; 0 deterministic fails)

Semantic fields below are **human/LLM-spec review**, not new deterministic graders.

Frozen baseline remains **5 PASS / 10 FAIL**.

---

## Semantic review prompts (9 specs)

Use final output + stamped facts + F4.2-visible context only. No hidden CoT.

| Spec | Question for this run |
|---|---|
| `sem_primary_selects_highest_priority` | Does `primary_message` name the highest-priority eligible/salient observation? |
| `sem_t8_no_level_c` | Any unsupported user-level physiological-state claim? |
| `sem_mixed_signals_preserved` | Are discordant directions distinguishable? |
| `sem_association_not_causation` | Association vs “X caused Y”? |
| `sem_rationale_quality` | Grounded, separate from the notice? |
| `sem_quote_not_hidden_advice` | Mild nudge vs hidden directive? (C4-style leakage accepted for MVP) |
| `sem_c2_confounders_not_collapsed` | Must **not** require all confounders equally. Accepted caffeine selection is not an automatic fail. |
| `sem_t6_no_cardiorespiratory_reassurance` | Stable RR minted as respiratory/cardiorespiratory health? |
| `sem_t12_spread_not_stress` | Spread described as decline / poor recovery / instability? |

---

## HC-EVAL-A1

| | |
|---|---|
| Frozen baseline | **PASS** · INSIGHT · theme “Sleep Duration Shortening Across Recent Week” |
| V2 status | **RECOMMENDATION** |
| V2 primary | Your average sleep duration decreased from 7.1 to 5.8 hours per night over the past week. |
| V2 quote | Small routine shifts can help protect your rest and recovery. |
| V2 rec | Shift caffeine earlier (R-07; both F4.7 gates true) |
| CODIFY | 11 pass / 0 fail |
| Semantic | Primary = sleep. Level A/B. Mixed preserved (exercise/HRV in rationale). Association (“coincided”). Quote mildly advisory / “recovery” wording — accepted MVP quote limitation, not a contract fail. |
| V2 label | **PASS** |
| Change | **IMPROVED** (T7 split). Caffeine latch documented, not a regression. |

---

## HC-EVAL-A2

| | |
|---|---|
| Frozen baseline | **PASS** · RECOMMENDATION · exercise + cardiovascular indicators |
| V2 status | **INSIGHT** (rec blocked: worthy=true, authorized=false) |
| V2 primary | Exercise minutes, HRV, VO2 max, and sleep duration have increased, accompanied by a decrease in resting heart rate. |
| V2 quote | Building consistent activity habits supports steady progress across daily health measurements. |
| V2 rec | null |
| CODIFY | 12 / 0 |
| Semantic | Level B named multi-metric. RR subtext is a metric fact, not reassurance. F4.7 honored. Primary is a bit list-like but correct. |
| V2 label | **PASS** |
| Change | **IMPROVED** structure; rec correctly withheld. T11 overlap with A3 remains. |

---

## HC-EVAL-A3

| | |
|---|---|
| Frozen baseline | **PASS** · RECOMMENDATION · same 2026-07-18 world as A2 |
| V2 status | **INSIGHT** · rec blocked (same gate pattern as A2) |
| V2 primary | Daily exercise minutes, HRV, and VO2 max increased while resting heart rate decreased. |
| V2 quote | Consistency in your regular routines supports long-term progress. |
| CODIFY | 12 / 0 |
| Semantic | Conservative named metrics. No clinical causation. Same-world overlap with A2 (T11). |
| V2 label | **PASS** |
| Change | **IMPROVED** structure. **T11 still present.** |

---

## HC-EVAL-A4

| | |
|---|---|
| Frozen baseline | **PASS** · INSIGHT · Sleep Duration Decline |
| V2 status | **RECOMMENDATION** (sleep −15.42%; R-07 allowed) |
| V2 primary | Sleep duration decreased over the past week alongside recurring late-afternoon caffeine intake. |
| V2 quote | Small adjustments to afternoon habits can help protect your rest and restore energy. |
| CODIFY | 11 / 0 |
| Semantic | Sleep prioritized. “Alongside” association. Quote mildly advisory (accepted). Mixed: RR in subtext; exercise/HRV omitted from card — partial, not collapsed. |
| V2 label | **PASS** |
| Change | **IMPROVED** T7. Caffeine latch documented. |

---

## HC-EVAL-B1

| | |
|---|---|
| Frozen baseline | **FAIL** (T5) · INSIGHT · modest steps/exercise |
| V2 status | **NO_SIGNIFICANT_NEW_PATTERN** |
| V2 primary / quote / rec | all null |
| Internal | steps +6.55% / exercise +3.87% still visible; `insight_worthy=false` |
| CODIFY | 12 / 0 including `scenario_b1_quiet_path` |
| Index note | F1 completeness flagged ERROR because `policy` is null (no RAG). Product TRACE is valid. Not a product fail. |
| V2 label | **PASS** |
| Change | **IMPROVED** — T5 closed. |

---

## HC-EVAL-B2

| | |
|---|---|
| Frozen baseline | **PASS** (T10 weak eval design) · INSIGHT |
| V2 status | **INSIGHT** after a first-pass 503; resume produced a product TRACE |
| V2 primary | Daily exercise minutes have increased … while VO2 max levels remain maintained above earlier reference levels. |
| V2 rec | null (`authorized=false`) |
| Semantic | Legitimate exercise + VO2 `maintenance_of_gain`. Sleep −6.47% not in `primary_metrics` — omitted, not inverted. Do **not** manufacture a product failure to preserve old taxonomy. |
| V2 label | **PASS** |
| Change | **BASELINE_EVAL_ISSUE** / behavior reasonable on merits. |

---

## HC-EVAL-B3

| | |
|---|---|
| Frozen baseline | **FAIL** (T4) · NO_SIGNIFICANT_NEW_PATTERN |
| V2 status | **INSIGHT** |
| V2 primary | Your resting heart rate, HRV, and VO2 max continue to maintain gains over your longer-term reference levels. |
| V2 rec | null · `final_recommendation_allowed=false` |
| Semantic | Level B maintenance. Recent stability not treated as “nothing happened.” Quote generic encouragement. F4.7 intact. |
| V2 label | **PASS** |
| Change | **IMPROVED** — T4 closed. |

---

## HC-EVAL-C1

| | |
|---|---|
| Frozen baseline | **FAIL** (T1 lifestyle inaccessible) |
| V2 status | **RECOMMENDATION** |
| V2 primary | Average sleep duration decreased to 5.83 hours … alongside late-afternoon caffeine intake. |
| Lifestyle | caffeine, alcohol, mood visible; late-work=7; `caffeine_mg` in policy inputs |
| Semantic | Explicit “co-occurrence does not prove causation.” Rec permitted by F4.7. |
| V2 label | **PASS** |
| Change | **IMPROVED** — T1 access closed. Caffeine latch documented. |

---

## HC-EVAL-C2

| | |
|---|---|
| Frozen baseline | **FAIL** (T1) |
| V2 status | **RECOMMENDATION** |
| V2 primary | Nightly sleep duration decreased to an average of 6.0 hours this week. |
| Lifestyle | caffeine + alcohol + late-work=6 visible. Prose discusses caffeine. |
| Semantic | Do not require equal confounder coverage. Accepted MVP caffeine selection. Association language. Quote mildly advisory (accepted). |
| V2 label | **PASS** |
| Change | **IMPROVED** (access). Remaining UX: unused late-work/alcohol. |

---

## HC-EVAL-C3

| | |
|---|---|
| Frozen baseline | **FAIL** (T1; also manufactured lifestyle story in frozen run) |
| V2 status | **INSIGHT** |
| V2 primary | Exercise minutes and workout count increased, while daily step count decreased. |
| Sleep | stable +2.06%. Caffeine visible in TRACE, **not** minted as a problem. |
| Semantic | Negative control held. Mixed activity directions preserved. Rec blocked. |
| V2 label | **PASS** |
| Change | **IMPROVED**. |

---

## HC-EVAL-C4

| | |
|---|---|
| Frozen baseline | **FAIL** (T12 spread invisible) |
| V2 status | **RECOMMENDATION** |
| V2 primary | Sleep duration decreased over the past week while exercise minutes increased. |
| HRV | level **improving +5.56%**; spread ratio **2.61**; not primary; `spread_context` stamped |
| V2 quote | Consistent daily habits support both your workout goals and restful sleep. |
| Semantic | Spread not inverted to decline/stress. Sleep+exercise primary is allowed. Quote safer than F5.2 C4; still habit-framed. Accepted MVP quote bar. |
| V2 label | **PASS** |
| Change | **IMPROVED** — T12 closed. Caffeine rec is the known latch. |

---

## HC-EVAL-D1

| | |
|---|---|
| Frozen baseline | **FAIL** (T2 as-of provenance) |
| V2 status | **INSIGHT** |
| V2 primary | Exercise minutes increased … modest improvements in sleep, RHR, HRV. |
| V2 subtext | Recent HRV measurements reflect partial weekly wear time. |
| HRV | `as_of_date_available=false`, `gap_caveat_required=true`, direction improving (historical window) |
| Semantic | Missing same-day HRV visible. Did not require silence. Rec blocked. No fabricated same-day HRV. |
| V2 label | **PASS** |
| Change | **IMPROVED**. |

---

## HC-EVAL-D2

| | |
|---|---|
| Frozen baseline | **FAIL** (T2 full sync gap) |
| V2 status | **INSIGHT** |
| V2 primary | Daily exercise minutes and workout frequency increased … though data for June 10 are missing. |
| Sleep/RR | `as_of_date_available=false`, `gap_caveat_required=true` |
| Semantic | Gap acknowledged. Recent history used as qualified context. Old `data_sufficient` binary not applied. Rec blocked. |
| V2 label | **PASS** |
| Change | **IMPROVED**. |

---

## HC-EVAL-D3

| | |
|---|---|
| Frozen baseline | **FAIL** (T3 `data_sufficient` advisory) |
| V2 status | **INSIGHT** on activity (exercise/workouts/steps) |
| VO2 | F4.1 `ESTABLISHED_TREND` / `trend_allowed` on this as-of; **not** the user-facing primary |
| Semantic | Did not block all insight because of the retired 15-in-30 rule. Did not overclaim VO2. |
| V2 label | **PASS** |
| Change | **IMPROVED**. |

---

## HC-EVAL-E1

| | |
|---|---|
| Frozen baseline | **FAIL** (T6 RR invisible; “cardiovascular indicators remained stable”) |
| V2 status | **RECOMMENDATION** (same world as A1; caffeine latch) |
| V2 primary | Average sleep duration declined by 18% over the past week to 5.8 hours. |
| RR | visible, control, not primary, not reassurance |
| V2 quote | Small adjustments to timing can help restore your rest. |
| Semantic | T6 held. Mixed: exercise/HRV improving named in rationale. Quote mildly advisory (accepted). |
| V2 label | **PASS** |
| Change | **IMPROVED**. |

---

## Semantic-review status summary

| Spec | Run finding |
|---|---|
| Primary selection | Held on A1/A4/B3/C1–C4/D2/D3/E1. A2/A3 are broad Level B lists (acceptable). |
| T8 Level C | **No user-state Level C.** Some quote/theme “recovery / well-being” language. |
| Mixed signals | Generally preserved. B2 omits sleep decline (not a primary). |
| Causation | Association language; C1 explicit non-causal. |
| Rationale quality | Grounded in stamped numbers. |
| Quote as advice | Recurring habit-shift nudge on sleep+caffeine worlds. **Accepted MVP limitation.** This C4 quote was milder than F5.2. |
| C2 confounders | Access yes; equal discussion not required. |
| T6 reassurance | Absent. |
| T12 stress wording | Absent. |
