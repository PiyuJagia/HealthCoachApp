# Assignment 4 TRACE Tracker

Progression: **Baseline → Human Review → Failure Taxonomy → Remediation → Improved Observability → Rerun → CODIFY → Final Validation → Submission**

Human eval labels, PASS/FAIL, and taxonomy remain frozen until a later Gemini rerun. CODIFY is not started.

| Phase | Status | Notes |
|---|---|---|
| F1 Baseline traces | COMPLETE | 15-scenario frozen baseline; `evals/traces/` |
| F2 Human review | COMPLETE | `evals/results/baseline_human_review_bundle_v1.md` — 5 PASS / 10 FAIL |
| F3 Failure taxonomy | COMPLETE | `failure_taxonomy_v1.md`, counts CSV, `remediation_priority_v1.md` |
| F4.0 Maturity design | COMPLETE | Design only; missing data weakens claims, does not silence the coach |
| F4.1 Data-maturity / claim-eligibility contract | COMPLETE | Retired `data_sufficient`; deterministic eligibility/provenance |
| F4.1.1 Deterministic contract inspection | COMPLETE | `f41_contract_inspection_v1.*`; 33 tests (2026-08-21) |
| F4.2 LLM-visible TRACE observability | COMPLETE | ADK `before_model_callback`; `adk_pre_model_request` |
| F4.3 Weekly-summary maturity/coverage alignment | COMPLETE | Weekly claim_semantics distinct from trend eligibility; bypass closed |
| F4.4 T1 Lifestyle context | COMPLETE | Deterministic `get_lifestyle_context`; policy `available_inputs` wiring; C1/C2/C3 inspected |
| F4.5 T4 Longitudinal maintenance | COMPLETE | Compact prefix-vs-recent contract; B3 maintenance_of_gain on RHR/HRV/VO2; B1 negative control |
| F4.6 T5 Salience / insight-worthiness | COMPLETE | Deterministic salience contract; B1 not insight-worthy; A1/B3 eligible; early-pattern preserved |
| F4.7 Recommendation boundary | COMPLETE + LIVE VALIDATED | Combined gate enforced; B3 rec blocked / INSIGHT kept; A1 dual-true rec permitted |
| F4.8 T6 Respiratory control metric | COMPLETE + LIVE VALIDATED | Daily RR as control metric; E1 did not mint respiratory reassurance; B1 stayed non-salient |
| F4.9 T12 Variability | COMPLETE | HRV-only `within_window_spread`; C4 spread visible without calling HRV declining |
| Remaining F4 product remediation | IN PROGRESS | T1, T4, T5, T6, T12, F4.7 closed; T7 remain |
| Gemini baseline rerun | NOT STARTED | Full 15-scenario rerun not started; targeted C1/C2/C3 post-F4.4 check recorded below |
| CODIFY (graders/assertions) | NOT STARTED | |
| Final validation | NOT STARTED | |
| Submission | NOT STARTED | |

## F4.1.1 artifacts

- `evals/results/f41_contract_inspection_v1.md` / `.csv` / `.json`
- Offline verification: 33 passed (2026-08-21)

## F4.2 artifacts

- `evals/results/f42_llm_observability_v1.md` / `.json`
- Capture fidelity: **adk_pre_model_request**

## F4.3 weekly-summary bypass

- **Finding:** weekly averages + coverage, no claim strength; Gemini could treat a partial-week mean as a complete-week measurement and ignore trend eligibility.
- **Remediation:** per-metric `coverage.claim_semantics` (`summary_value_allowed`, `summary_comparison_allowed`, `summary_recommendation_support_allowed`). Comparison/recommendation follow the as-of trend contract; they are not independently authorized. Not a copy of `snapshot_allowed` / `trend_allowed`.
- **Verification:** `evals/results/f43_weekly_summary_alignment_v1.md` — D1/D2/A1 bypass_closed=true, no weekly/trend contradictions.

## F4.4 T1 lifestyle context

- **Original T1 failure:** C1/C2/C3 lifestyle events existed in SQLite but no ADK tool exposed them. Gemini could not inspect caffeine / alcohol / mood / late-work context. Evidence policy also never received lifestyle-derived `available_inputs` (R-07 `caffeine_mg` stayed `INPUT_UNAVAILABLE`).
- **Implementation:** deterministic `get_lifestyle_context(user_id, as_of_date, lookback_days=14)` over existing `lifestyle_events`. Observational context only. No RAG, no causal scoring, no recommendation authority.
- **ADK inventory:** `get_trend_signals`, `get_lifestyle_context`, `retrieve_authorized_evidence` (single agent; no router/MCP).
- **Policy-input wiring:** after a lifestyle lookup in the same run, `retrieve_authorized_evidence` passes mapped inputs into `evaluate_evidence_policy()`. Mapping: caffeine+mg → `caffeine_mg`; alcohol+standard_drinks → `alcohol_units`. Mood/late-work do not map. Presence does not prove causation; R-08 still cannot authorize alcohol advice.
- **Observability:** TRACE `origin=lifestyle_context`; `lifestyle_context_visible`; subsequent evidence `available_inputs` recorded. No hidden CoT. Secrets still redacted.
- **Deterministic C1/C2/C3 inspection:** `evals/results/f44_lifestyle_context_v1.md` / `.json` (no Gemini).
  - C1 2026-08-02: 7 afternoon 200mg caffeine events; late-work notes present; sleep decreasing.
  - C2 2026-07-31: caffeine + late-work + alcohol co-occur; ambiguity preserved in the tool (no ranked cause).
  - C3 2026-06-29: 2 routine 180mg caffeine events; sleep stable; tool does not manufacture a caffeine problem.
- **Tests:** `tests/test_lifestyle_context.py` (17). Focused related suite 95 passed. Full pytest **284 passed** (2026-08-21). Frozen human labels unchanged.
- **Targeted live C-family check (2026-08-21):** Gemini ran C1/C2/C3 only. All three called `get_lifestyle_context`; TRACE `origin=lifestyle_context`; `caffeine_mg`/`alcohol_units` reached policy. C1 improved (caffeine co-occurrence + authorized R-07). C2 collapsed to a caffeine recommendation despite visible late-work/alcohol. C3 did not manufacture a caffeine problem. Frozen human labels unchanged. Artifact: `evals/results/f44_c_family_post_remediation_v1.md`.

## F4.5 T4 longitudinal maintenance

- **Original B3 failure:** Frozen Gemini treated 2026-08-17 as `NO_SIGNIFICANT_NEW_PATTERN` because the recent 7-day window was stable vs a rolling baseline that had already absorbed Phase 2 fitness gains. Human review: this is holding onto prior gains, not “nothing happened.”
- **Why it was missed:** F4.1 current window is 7 days (2026-08-11→2026-08-17). The 60-day lookback baseline starts **2026-06-19** (Phase 2). Phase 1 (2026-05-20→2026-06-18: RHR 71.07, exercise 11.18, VO2 38.5) is entirely outside that comparison. Stable recently ≠ no older change.
- **Design:** Compact `longitudinal_context` per metric (not a second trend engine, not 7/30/90 directional forecasts). Long-term reference = history older than the F4.1 baseline, capped at 90 days. Medium/long horizon values are observational only. Weekly summaries remain observed-week facts and cannot independently authorize a maintenance claim.
- **Maintenance-of-gain rule (MVP knobs, not physiology):** `trend_allowed` AND recent 7-vs-60 direction is `stable` AND current is ≥3% better than the older reference AND the F4.1 baseline is already ≥3% better than that reference. Same 3% knob as F4.1 `STABLE_PERCENT_THRESHOLD`. Not a celebration directive.
- **B3 deterministic post-remediation (no Gemini):** `maintenance_of_gain=true` for `resting_hr_bpm` (−4.44% vs Phase 1), `hrv_sdnn_ms` (+16.03%), `vo2_max` (+5.31%). Exercise/workouts remain recent **improving** (not maintenance). Sleep is worse than Phase 1. Steps is a maintained decline vs the walking-heavy early period, not a gain.
- **Negative controls:** B1 2026-06-18 has no history older than the F4.1 baseline → `longitudinal_context_available=false`, all `maintenance_of_gain=false`. Synthetic 90-day flat series: available but no prior improvement → false. Improvement then reversal → false.
- **Observability:** TRACE `origin=deterministic_longitudinal_analytics`; `longitudinal_context_visible` shows old reference, prior change, current vs long-term, `maintenance_of_gain` true/false. No hidden CoT.
- **Tests:** `tests/test_longitudinal.py` (12). Focused related suite 95 passed. Full pytest **296 passed** (2026-08-21). Frozen human labels unchanged.
- **Artifacts:** `evals/results/f45_longitudinal_context_v1.md` / `.json`.

## F4.6 T5 salience — COMPLETE

- **Original B1 failure:** Frozen Gemini returned INSIGHT for modest isolated steps +6.55% / exercise +3.87% during Day-30 calibration. Human review: technically correct, low-salience for the Directive page. Taxonomy T5 unchanged.
- **Implementation:** Orthogonal `trends[].salience` + payload `insight_salience`. Magnitude uses percent **and** absolute product knobs (not clinical cutoffs). Weak+weak activity does not promote. Recovery-family concordance may. F4.5 `maintenance_of_gain` / `maintenance_of_decline` remain independently insight-eligible. Lifestyle never manufactures physiological salience. Coverage may cap high→moderate, never creates salience. `recommendation_worthy` is separate and does not authorize recs. Early-pattern: `baseline_ready=false` does not auto-suppress a strong/corroborated observation; it stays `EARLY_PATTERN`, not an established trend.
- **Decision log:** distinguishes detectable vs insight-worthy vs recommendation-worthy.
- **TRACE:** origin=`deterministic_salience_analytics`; `insight_salience_visible` with reasons, corroborators, maintenance flags, and F4.1 eligibility. No hidden CoT.
- **Deterministic inspection (no Gemini):** `evals/results/f46_salience_inspection_v1.md` / `.json`
  - B1: `insight_worthy=false`; steps/exercise remain `improving` but `barely_directional` / low; weak pair does not corroborate.
  - A1: sleep −18.0% / −1.28h `strong`, `insight_worthy=true`.
  - B3: RHR/HRV/VO₂ `maintenance_of_gain` still insight-eligible; `recommendation_worthy=false`.
  - C3: sleep stable, not an insight candidate despite caffeine/alcohol events. Payload may still be worthy from real activity moves (exercise/steps), not from lifestyle.
  - Synthetic early-pattern: `EARLY_PATTERN`, `trend_allowed=false`, strong sleep drop still `insight_candidate=true`, `recommendation_worthy=false`.
- **Tests:** `tests/test_salience.py` (9). Full pytest **305 passed** (2026-08-21). Frozen human labels unchanged. No prompt/guard/CODIFY/Gemini.
- **Design:** `evals/results/f46_salience_design_v1.md`.
- **Prompt/output honor (2026-08-21):** System instructions now treat `insight_worthy` as deterministic authority for INSIGHT status. Direction remains visible when false. Guard unchanged. Artifact: `evals/results/f46_prompt_salience_honor_inspection_v1.md`. Tests: `tests/test_salience_prompt_honor.py` (10). Full pytest **315 passed**. No Gemini.
- **Targeted Gemini B1/A1/B3 (2026-08-21):** Live measurement only. Frozen labels unchanged. Artifact: `evals/results/f46_b1_a1_b3_post_remediation_v1.md`. Traces: `evals/results/f46_b1_a1_b3_traces/`. B1 → `NO_SIGNIFICANT_NEW_PATTERN` (T5 honor). A1 sleep still surfaced but flipped to R-07 `RECOMMENDATION`. B3 maintenance `INSIGHT` with an R-05 recommendation field despite `recommendation_worthy=false`.

## F4.7 recommendation boundary — COMPLETE

- **Trigger:** Live B3 wrote `Maintain your regular aerobic exercise habit` under INSIGHT after R-05 returned `recommendation_authorized=true` while `recommendation_worthy=false`. Guard passed. Evidence authorization was treated as permission to recommend.
- **Contract:** `final_recommendation_allowed = recommendation_worthy AND recommendation_authorized`. Upstream fields remain distinct (salience vs policy).
- **Enforcement:** Deterministic sanitizer nulls `recommendation` and blocks `status=RECOMMENDATION` when the gate is false; valid INSIGHT is preserved. Guard also checks status/field. Existing rec-phrase list is reused for leftover insight prose; no new keyword blacklist.
- **B3:** insight remains allowed; rec blocked.
- **A1:** both gates true when R-07 sees lifestyle inputs → recommendation **permitted** (not a UX verdict).
- **B1:** remains non-salient; rec path cannot reopen it.
- **TRACE:** `recommendation_boundary` + F4.2 `recommendation_boundary_visible` with origins. No CoT.
- **Tests:** `tests/test_recommendation_boundary.py` (22). Full pytest **337 passed**. Frozen labels unchanged. No Gemini / CODIFY / T6 / T12 / T7.
- **Artifact:** `evals/results/f47_recommendation_boundary_inspection_v1.md`
- **Live validation (2026-08-21):** B3 + A1 only. Artifact: `evals/results/f47_b3_a1_live_validation_v1.md`. Traces: `evals/results/f47_b3_a1_traces/`.
  - B3: `allowed=false`; Gemini produced INSIGHT with null rec (obeyed); sanitizer idle; maintenance insight survived; guard PASS.
  - A1: `allowed=true`; RECOMMENDATION not suppressed; association (`co-occurs`) preserved; guard PASS. Not a UX verdict.
  - F4.7 **LIVE VALIDATED** on final system behavior. Frozen labels unchanged.

## F4.8 T6 respiratory-rate control metric — COMPLETE

- **Original E1 limitation:** Frozen Gemini never saw `respiratory_rate`. The field existed and was stable in `health_daily`, but it was omitted from `METRIC_SPECS` / `get_trend_signals`. The model generalized other signals as “cardiovascular indicators remained stable.” Intended control-metric bounding could not be tested. Frozen E1 FAIL / T6 unchanged.
- **Implementation:** Daily cadence, same F4.1 maturity/coverage/eligibility as other dailies. No clinical respiratory thresholds. `control_metric=true` on spec, trend row, and salience. Payload `insight_salience.control_metrics` lists designated controls. Stable/barely RR is not insight-eligible and cannot mint `maintenance_of_gain`. Weekly `average_respiratory_rate` uses F4.3 claim_semantics (cannot independently authorize a trend).
- **Deterministic E1 (2026-08-02, no Gemini):** Sleep decreasing −18.0% / 5.83 vs 7.11, insight candidate. RHR stable +0.18%. HRV improving +11.72%. Exercise improving +29.02%. VO2 stable +1.8%. Respiratory rate **stable −1.67% / 14.3 vs 14.54**, 7/7 coverage, `ESTABLISHED_TREND`, `insight_candidate=false`, `control_metric=true`, not in `primary_metrics`. Payload remains `insight_worthy=true` from sleep/activity, not from RR.
- **Control-metric role:** Bounding context for a sleep-specific change. Does not produce “respiratory health is good” or “cardiorespiratory health is stable.”
- **Negative controls:** B1 RR stable, `insight_worthy` still false. D2/synthetic partial coverage keeps missing days visible (no imputation). Immature 8-day series is `EARLY_PATTERN`, direction unknown, no established trend.
- **TRACE:** F4.2 `origin=deterministic_analytics` (existing constant). Value, maturity, allowed direction, `control_metric`, coverage/provenance visible. No hidden CoT.
- **Tests:** `tests/test_respiratory_control.py` (14). Focused related suite 108 passed. Full pytest **351 passed**. Frozen labels unchanged. No Gemini / CODIFY / T7 / T12.
- **Artifact:** `evals/results/f48_respiratory_control_inspection_v1.md` / `.json`
- **Live validation (2026-08-21):** E1 + B1 only. Artifact: `evals/results/f481_e1_b1_live_validation_v1.md`. Traces: `evals/results/f481_e1_b1_traces/`.
  - E1: RR visible (`14.3` vs `14.54`, −1.67%, `control_metric=true`, `insight_candidate=false`). Sleep treated as a specific decline. No “cardiovascular indicators remained stable” / respiratory-health reassurance. Final status **RECOMMENDATION** via R-07 caffeine latch (same as-of as A1; both F4.7 gates true). Not a T6 miss.
  - B1: RR visible and stable; `insight_worthy=false`; **NO_SIGNIFICANT_NEW_PATTERN**. T5 not reopened.
  - F4.8 **LIVE VALIDATED** on the control-metric contract. Frozen labels unchanged.

## F4.9 T12 within-window spread — COMPLETE

- **Implementation:** HRV-only `within_window_spread` on the F4.1 trend contract. Fields: observation_count, mean, sample SD, min/max/range, baseline SD, spread_ratio, spread_observation_allowed, spread_comparison_allowed. Same current/baseline windows. No band, CV, 0–100 score, clinical threshold, causal interpretation, salience promotion, recommendation authority, longitudinal interaction, or T7/T8.
- **Comparison gate:** false when baseline is immature, current n < 4, baseline sample SD < 1e-6, partial coverage, or gap caveat. Ratio is omitted when comparison is not allowed.
- **Deterministic C4 (2026-07-28, no Gemini):** current 7d HRV `28.7, 48.9, 30.5, 44.9, 25.7, 44.4, 24.7`. Mean **35.4**, sample SD **10.25**, min/max **24.7 / 48.9**, range **24.2**, baseline SD **3.94**, spread_ratio **2.61**, comparison allowed. Published level remains **improving +5.56%** (`ESTABLISHED_TREND`), not declining. HRV `insight_candidate=false`, not in `primary_metrics`. Sleep remains the level story (−10.58%).
- **Negative controls:** stable mean + normal spread (ratio 1.09, not a candidate); B1 still `insight_worthy=false`; immature baseline / partial coverage / near-zero baseline SD all set `spread_comparison_allowed=false` and null the ratio; one extreme outlier keeps min/max visible; VO2 has no spread object; RR stays a control with no spread object.
- **TRACE:** F4.2 origin `deterministic_spread_analytics`. Allow-flags and numerical provenance are visible.
- **Prompt honor:** smallest descriptive instruction only — spread is context; stable/improving mean + higher spread is not decline; no stress / poor recovery / cardiovascular instability from spread alone. No T7 output formatting.
- **Tests:** `tests/test_spread.py` (19). Full pytest **370 passed**. Frozen labels unchanged. No Gemini / CODIFY / T7 / T8.
- **Artifacts:** `evals/results/f49_variability_design_v1.md`, `evals/results/f49_spread_inspection_v1.md` / `.json`

## Remaining backlog

1. C2-style ambiguity collapse / A1 R-07 latch as a UX question (architecture now permits A1 rec when both gates are true)
2. Other taxonomy: T7 output contract (T8 remains generation-constraint after T12 exists)
3. Full Gemini baseline rerun
4. CODIFY
