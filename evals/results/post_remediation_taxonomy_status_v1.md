# Post-remediation taxonomy status v1

New mapping after `post_remediation_v1`.  
Does **not** mutate `failure_taxonomy_v1.md` or `failure_taxonomy_counts_v1.csv`.

Source of original clusters: frozen F3 taxonomy (T1–T12).  
Evidence: official V2 traces in `evals/results/post_remediation_traces_v1/` plus human semantic review in `post_remediation_review_bundle_v1.md`.

Status vocabulary:

- **CLOSED** — original failure mode did not recur under the remediated contract
- **IMPROVED** — substantially better; residual wording/UX may remain
- **STILL_PRESENT** — same issue observed
- **NOT_MEANINGFULLY_TESTED** — this run did not re-exercise the original failure
- **BASELINE/EVAL DESIGN ISSUE** — original cluster was eval design, not product

---

| ID | Original name | Post-remediation status | Evidence |
|---|---|---|---|
| T1 | Lifestyle context inaccessible to agent | **CLOSED** | C1/C2/C3 all called `get_lifestyle_context`. Caffeine/alcohol/late-work visible. Policy received lifestyle-mapped inputs on C1/C2. C3 saw caffeine and did not manufacture a caffeine problem. |
| T2 | As-of-date measurement provenance gap | **CLOSED** | D1: HRV `as_of_date_available=false`, `gap_caveat_required=true`; subtext notes partial weekly wear. D2: “data for June 10 are missing”; gap flags true. Historical trends still used; silence not required. |
| T3 | `data_sufficient` not enforced | **CLOSED** | Original advisory flag is retired. F4.1 eligibility now governs claims. D3 surfaces activity under current maturity rules and does **not** overclaim VO2. Do not re-apply the old 15-in-30 silence rule. |
| T4 | Longitudinal maintenance blind spot | **CLOSED** | B3 = INSIGHT: RHR/HRV/VO2 `maintenance_of_gain` named. Rec remains F4.7-blocked. |
| T5 | Low-salience insight surfacing | **CLOSED** | B1 = `NO_SIGNIFICANT_NEW_PATTERN`. Steps +6.55% / exercise +3.87% remain analytical, not Directive-worthy. |
| T6 | Control metric excluded from agent contract | **CLOSED** | E1 RR visible, `control_metric`, not primary, not respiratory/cardiorespiratory reassurance. Sleep remains primary. |
| T7 | Directive-first output contract gap | **IMPROVED** | F5.1 fields live: `primary_message` / subtext / rationale / quote / rec / stamped facts. A-family no longer dumps analysis as the only card. Residual: A2/A3 primaries are still named multi-metric lists (Level B, acceptable). Streamlit UI still Theme/Insight (out of this measurement). |
| T8 | Physiological over-generalization | **IMPROVED** | No Level C user-state claims. E1 no longer says “cardiovascular indicators remained stable.” Some quote/theme “recovery / well-being” language remains (accepted quote limitation, not T8 Level C). |
| T9 | Redundant evidence retrieval | **NOT_MEANINGFULLY_TESTED** | Typical V2 path is trends → lifestyle → one evidence call → final. Original “second evidence lookup” pattern was not re-observed. Not scored as a product regression or a formal close. |
| T10 | Eval scenario design mismatch | **BASELINE/EVAL DESIGN ISSUE** | B2 evaluated on merits: exercise increase + VO2 maintenance. Do not manufacture a product failure to preserve a weak recovery rubric. |
| T11 | Eval overlap / ambiguous scenario discrimination | **STILL_PRESENT** | A2 and A3 still share 2026-07-18. Both produced similar Level B multi-metric INSIGHT with rec blocked. Eval-design leftover. |
| T12 | Within-window variability not exposed | **CLOSED** | C4: HRV level improving +5.56%; spread_ratio 2.61; `spread_context` stamped; not inverted to decline/stress; not forced as primary while sleep is stronger. |

---

## Closed vs leftover

**Product root-cause clusters closed:** T1, T2, T3 (replaced), T4, T5, T6, T12.

**Product symptoms improved:** T7, T8.

**Eval-infra leftovers:** T10 (B2 design), T11 (A2/A3 overlap).

**Not re-litigated as a fail:** T9.

---

## What this mapping is not

- Not a mutation of the frozen F3 artifact.
- Not a claim that Assignment 4 is complete.
- Not permission to remediate quote-as-advice or caffeine latch in this run.
