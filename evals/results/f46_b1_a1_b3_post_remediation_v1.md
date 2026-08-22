# F4.6 targeted post-remediation evaluation — B1 / A1 / B3

Live Gemini (`gemini-3.6-flash`) on the current F4.6 prompt-honor system. Prompts, salience knobs, F4.1/F4.5/F4.6 semantics, guard, and policy were **not** modified for this run.

Only `HC-EVAL-B1`, `HC-EVAL-A1`, and `HC-EVAL-B3` were executed. Frozen human PASS/FAIL labels were **not** changed. Capture fidelity: `adk_pre_model_request` on every model call. No hidden CoT captured.

Traces: `evals/results/f46_b1_a1_b3_traces/`

Operational note: a Gemini `503 UNAVAILABLE` (high demand) appeared during the session; all three scenarios still completed product traces. B1 latency (30905 ms) is consistent with a retry.

## Intended post-remediation behavior

| Scenario | Deterministic contract | Intended live behavior |
|---|---|---|
| B1 | `improving` steps/exercise remain visible; `insight_worthy=false` | Do **not** promote weak activity into INSIGHT |
| A1 | sleep −18.0% / −1.28 h; `insight_worthy=true` | INSIGHT allowed from eligible salient sleep evidence |
| B3 | `stable` + `maintenance_of_gain`; `insight_worthy=true`; `recommendation_worthy=false` | INSIGHT allowed for maintenance; rec flag is **not** rec authorization |

## HC-EVAL-B1 — 2026-06-18

**Frozen baseline:** status=`INSIGHT`, theme=Increased daily step activity…, guard PASS, human **FAIL** (T5). Trajectory: `get_trend_signals` → evidence query `steps exercise physical activity trend` → INSIGHT celebrating ~10,900 steps.

**This run:** `828f9950-8743-4a1e-b210-629233d87a9e`

### Trajectory
1. Model call 0: request `get_trend_signals` (`adk_pre_model_request`)
2. OBSERVE: steps `improving` +6.55%, exercise `improving` +3.87%, both `insight_candidate=false`, payload `insight_worthy=false`, `salience_level=low`, reasons `same_family_weak_corroboration`, `detectable_but_small_absolute`, `no_older_horizon`
3. DECISION: “Detectable directional movement is not insight-worthy: exercise_minutes, steps.”
4. Model call 1: final JSON (no further tools)

No lifestyle tool. No evidence retrieval.

### Gemini-visible salience / longitudinal
- `insight_salience_visible.insight_worthy=false`
- `recommendation_worthy=false`
- `longitudinal_context_available=false`
- Direction **not hidden**: steps/exercise remain `improving` in the trend payload
- System instruction on every call includes `insight_salience.insight_worthy`

### Evidence / policy / guard
- Evidence: not called
- Policy: none (no retrieval)
- `recommendation_authorized=false`
- Guard: **PASS**, violations=`[]`

### Final
- status: **`NO_SIGNIFICANT_NEW_PATTERN`**
- reason_not_surfaced: metrics “remain stable or show only minor variations that do not meet salience thresholds for elevation into an insight”
- insight/recommendation: none

**Vs frozen baseline:** T5 promotion closed on this run.  
**Vs intended F4.6 honor:** **match.** Detectable ≠ insight-worthy.

## HC-EVAL-A1 — 2026-08-02

**Frozen baseline:** status=`INSIGHT`, QUALIFY, `recommendation_authorized=false`, R-07 suppressed (`required_input_unavailable`), human **PASS** (T7 product-output gap only). Sleep −18.4% from 7.14 h to 5.83 h.

**This run:** `6400020e-7657-4996-ba03-a226fd070ac3`

### Trajectory
1. `get_trend_signals`
2. DECISION: insight-worthy `exercise_minutes, workout_count, sleep_duration_hours`; “Physiology is recommendation-candidate; evidence policy remains the authorization gate.”
3. `get_lifestyle_context` — 17 events (alcohol, caffeine, mood); 7 late-work context events; `available_inputs=['alcohol_units','caffeine_mg']`
4. `retrieve_authorized_evidence` query=`sleep duration decrease caffeine late work`
5. Policy SURFACE, R-07 ×3, `recommendation_authorized=true`
6. FINAL `RECOMMENDATION`

### Gemini-visible salience / longitudinal
- `insight_worthy=true`, `salience_level=high`
- primary_metrics: exercise_minutes, workout_count, sleep_duration_hours, hrv_sdnn_ms, steps
- reasons: `strong_recent_change`, `clear_recent_change`, `maintenance_of_decline`
- `recommendation_worthy=true` (physiology flag only)
- longitudinal: `maintenance_of_decline` on steps; sleep remains the strong recent change
- Sleep numbers match current analytics: 7.11 h → 5.83 h (−18%), not the frozen 7.14 / −18.37 window

### Evidence / policy / guard
- Relationships: **R-07, R-07, R-07** (caffeine timing now evaluable because lifestyle inputs reached policy)
- Verdict: SURFACE; rec authorized at relationship level (`relationship_detected_recommendation_eligible`)
- Association language preserved (`coinciding`); also mentions late-work evenings
- Guard: **PASS**

### Final
- status: **`RECOMMENDATION`**
- theme: Sleep Duration & Caffeine Timing
- insight: sleep −18% coinciding with afternoon caffeine ~16:00 and late work evenings
- recommendation: shift caffeine earlier / avoid late afternoon

**Vs frozen baseline:** sleep signal still surfaced (F4.6 honor holds). Status flipped INSIGHT → RECOMMENDATION because F4.4 lifestyle made R-07 recommendation-eligible. Frozen PASS assumed no rec authority.  
**Vs intended F4.6 honor:** sleep INSIGHT eligibility **honored**; the live outcome is a **caffeine recommendation latch**, not a salience-suppression failure.

## HC-EVAL-B3 — 2026-08-17

**Frozen baseline:** status=`NO_SIGNIFICANT_NEW_PATTERN`, human **FAIL** (T4: treated maintenance as “nothing new”).

**This run:** `2f65850e-ae3a-48a4-8249-6e5d3c5da9b9`

### Trajectory
1. `get_trend_signals`
2. DECISION: insight-worthy `hrv_sdnn_ms, vo2_max, resting_hr_bpm`
3. DECISION: “Insight-worthy but not recommendation-worthy; this does not authorize a recommendation.”
4. `get_lifestyle_context` — 4 events (alcohol, caffeine, mood); not used in the final theme
5. `retrieve_authorized_evidence` query=`cardiovascular fitness maintenance resting heart rate HRV VO2 max stability`
6. Policy SURFACE, R-05 recommendation-eligible
7. FINAL status=`INSIGHT` **with a populated recommendation field**

### Gemini-visible salience / longitudinal
- `insight_worthy=true`, `salience_level=moderate`, `recommendation_worthy=false`
- reasons: `maintenance_of_gain`, `maintenance_of_decline`
- longitudinal: `maintenance_of_gain` on resting_hr_bpm, hrv_sdnn_ms, vo2_max; `maintenance_of_decline` on steps
- Recent RHR/HRV/VO₂ directions remain `stable` (maintenance, not a new trend)

### Evidence / policy / guard
- R-05 SURFACE / recommendation_authorized=true (`relationship_detected_recommendation_eligible`)
- Guard: **PASS** (the rec text is “Maintain your regular aerobic exercise **habit**”; the guard regex looks for “maintain your … **routine**”)

### Final
- status: **`INSIGHT`**
- theme: Maintenance of Cardiovascular Fitness Gains
- insight: recent stability while sustaining long-term CV improvements vs earlier baseline
- recommendation: maintain regular aerobic exercise habit

**Vs frozen baseline:** T4 “nothing new” failure closed; maintenance is now the insight.  
**Vs intended F4.6 honor:** INSIGHT eligibility **match**. Rec boundary **not** honored in the output field: `recommendation_worthy=false` was visible, then policy authorized R-05 and the model still wrote a recommendation under INSIGHT status.

## Comparison table — frozen baseline vs post-F4.6 honor

Frozen human PASS/FAIL is **unchanged**.

| | B1 baseline | B1 this run | A1 baseline | A1 this run | B3 baseline | B3 this run |
|---|---|---|---|---|---|---|
| Tools | trends + evidence | trends only | trends + 2× evidence | trends + lifestyle + evidence | trends + evidence | trends + lifestyle + evidence |
| `insight_worthy` visible | n/a (pre-F4.6) | **false** | n/a | **true** | n/a | **true** |
| `recommendation_worthy` visible | n/a | false | n/a | true | n/a | **false** |
| Longitudinal visible | n/a | unavailable | n/a | steps maintenance_of_decline | n/a | RHR/HRV/VO₂ maintenance_of_gain |
| Relationships | none (HHS only) | none | R-02; R-07 suppressed; R-01 QUALIFY | **R-07 ×3 SURFACE** | none (HHS/general) | **R-05 SURFACE** |
| Policy verdict | SURFACE | none | QUALIFY | SURFACE | SURFACE | SURFACE |
| Rec authorized | false | false | false | **true** | false | **true** |
| Final status | INSIGHT | **NO_SIGNIFICANT_NEW_PATTERN** | INSIGHT | **RECOMMENDATION** | NO_SIGNIFICANT_NEW_PATTERN | **INSIGHT** |
| Guard | PASS | PASS | PASS | PASS | PASS | PASS |
| Model calls | not captured | 2 F4.2 | not captured | 4 F4.2 | not captured | 4 F4.2 |
| Latency ms | 10076 | 30905 | 60349 | 43785 | 42373 | 25875 |
| Frozen human label | FAIL | unchanged | PASS | unchanged | FAIL | unchanged |
| F4.6 honor of `insight_worthy` | fail | **honored** | n/a | **honored** (sleep eligible) | fail (no F4.5 yet) | **honored** |
| Rec boundary | n/a | held | rec correctly withheld | **R-07 latch** | n/a | **R-05 rec under INSIGHT** |

## New failure modes revealed

1. **B1 honor succeeded.** Weak `improving` activity stayed visible and was not promoted to INSIGHT. Gemini used `NO_SIGNIFICANT_NEW_PATTERN` and named salience thresholds in `reason_not_surfaced`. This is the T5 measurement we wanted.

2. **A1 R-07 recommendation latch (same family as C1/C2).** F4.6 correctly kept sleep insight-eligible. F4.4 lifestyle then made caffeine evaluable, the model queried caffeine+late-work, policy authorized R-07, and a frozen **PASS** INSIGHT became a caffeine RECOMMENDATION. Association wording (`coinciding`) and late-work mention are better than C2 collapse, but A1 is no longer the quiet sleep-observation control. This is **not** an `insight_worthy` miss; it is policy/generation once lifestyle inputs exist.

3. **B3 rec field vs `recommendation_worthy=false`.** Maintenance INSIGHT is correct. The model then retrieved R-05, policy authorized a recommendation, and it wrote “Maintain your regular aerobic exercise habit” while keeping `status=INSIGHT`. Decision-log text said rec was not authorized by salience; policy overrode. Guard did not fire. This is the architectural boundary we preserved (`recommendation_worthy ≠ recommendation_authorized`) showing a **product** gap: maintenance should be celebratory INSIGHT, not an exercise prescription.

4. **Status/field mismatch on B3.** Instructions say use RECOMMENDATION status when a rec is appropriate *and* `recommendation_authorized=true`. The run used INSIGHT status with a non-null recommendation. Guard does not check that pairing.

5. **Prompt honor is empirically real for B1, not a guarantee against rec-latch.** Local contract tests could not have caught A1/B3 policy-authorized recommendations.

Human PASS/FAIL labels remain frozen. CODIFY not started. Full 15-scenario Gemini rerun not started. T6/T12/T7 not started.
