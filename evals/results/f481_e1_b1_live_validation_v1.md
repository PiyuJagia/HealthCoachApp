# F4.8.1 live validation — E1 / B1

Measurement only. Live Gemini (`gemini-3.6-flash`) on the current F4.8 system. Product code, prompts, salience knobs, maturity rules, RAG/policy, guard, frozen labels, and taxonomy were **not** modified for this run.

Only `HC-EVAL-E1` and `HC-EVAL-B1` were executed. Capture fidelity: `adk_pre_model_request` on every model call. No hidden CoT captured.

Traces: `evals/results/f481_e1_b1_traces/`

Contract under test: respiratory rate is a **control metric**. Success is *control context available and respected*, not *respiratory rate must appear in user-facing prose*.

## Compact comparison

| | Frozen E1 | Live E1 | Frozen B1 | Live B1 |
|---|---|---|---|---|
| `insight_worthy` | n/a (pre-F4.6) | **true** (sleep/activity) | n/a | **false** |
| RR in `get_trend_signals` | **absent** (`trend_count=7`) | **present** (`trend_count=8`) | absent | **present** |
| RR `control_metric` | n/a | **true** | n/a | **true** |
| RR `insight_candidate` | n/a | **false** | n/a | **false** |
| Final status | INSIGHT | **RECOMMENDATION** | INSIGHT | **NO_SIGNIFICANT_NEW_PATTERN** |
| Theme | Declining Sleep Duration | Sleep Duration Decline and Caffeine Timing | Increased daily step activity… | none |
| “cardiovascular indicators remained stable” | **yes** | **no** | n/a | n/a |
| Independent RR reassurance insight | no (RR invisible) | **no** | n/a | **no** |
| Guard | PASS | PASS | PASS | PASS |
| Frozen human label | FAIL (unchanged) | FAIL (unchanged) | FAIL (unchanged) | FAIL (unchanged) |

T6 is **LIVE VALIDATED** for the control-metric contract. The E1 status flip to RECOMMENDATION is the known A1-family caffeine latch (same as-of date), not a T6 miss.

---

## 1. E1 live result

**run_id:** `0bffd8bc-f486-46c8-a39d-bd35603397d0`  
**as_of:** 2026-08-02 · **latency_ms:** 14014 · **model calls:** 4 · F4.2 fidelity: yes

### Trajectory
1. `get_trend_signals` — sleep decreasing −18.0%; RR stable −1.67%, `control_metric=true`, `insight_candidate=false`; payload `insight_worthy=true`
2. DECISION: insight-worthy `exercise_minutes, workout_count, sleep_duration_hours`; physiology is recommendation-candidate
3. `get_lifestyle_context` — 17 events (alcohol, caffeine, mood); 7 late-work context events; `available_inputs=['alcohol_units','caffeine_mg']`
4. `retrieve_authorized_evidence` query=`sleep duration decline caffeine evening work`
5. Policy **SURFACE**; **R-07 ×3**; `recommendation_authorized=true`; `recommendation_worthy=true`; `final_recommendation_allowed=true`
6. FINAL **RECOMMENDATION**

### Gemini-visible metrics (actual tool result)

| metric | current | baseline | % | dir | maturity | cov | control | insight_cand |
|---|---|---|---|---|---|---|---|---|
| sleep | 5.83 | 7.11 | −18.0 | decreasing | ESTABLISHED_TREND | 7/7 | false | **true** |
| RHR | 69.49 | 69.36 | +0.18 | stable | ESTABLISHED_TREND | 7/7 | false | false |
| HRV | 38.04 | 34.05 | +11.72 | improving | ESTABLISHED_TREND | 7/7 | false | true |
| exercise | 26.91 | 20.86 | +29.02 | improving | ESTABLISHED_TREND | 7/7 | false | true |
| workouts | 0.43 | 0.35 | +21.43 | improving | ESTABLISHED_TREND | 7/7 | false | true |
| steps | 8865 | 9010 | −1.61 | stable | ESTABLISHED_TREND | 7/7 | false | true (maint. decline) |
| VO2 | 40.0 | 39.3 | +1.8 | stable | ESTABLISHED_TREND | 1/1 | false | false |
| **respiratory_rate** | **14.3** | **14.54** | **−1.67** | **stable** | **ESTABLISHED_TREND** | **7/7** | **true** | **false** |

RR salience: `salience_level=none`, reason `stable_control_context`. Listed in `insight_salience.control_metrics`. Not in `primary_metrics`.

### E1 checklist

1. Gemini can see respiratory rate: **yes**
2. Stable RR available as bounding context: **yes**
3. Converted into an independent reassurance insight: **no**
4. Unsupported generalization (“cardiovascular indicators remained stable” / “cardiorespiratory health is stable” / “respiratory health is good”): **absent**
5. Sleep decline remains a specific salient change: **yes** (theme and insight are sleep duration 7.1 → 5.8 h)
6. Causal/diagnostic claim manufactured from the stable control: **no**. Caffeine uses association language (`coinciding`).

Gemini did **not** mention respiratory rate in user-facing prose. That is allowed. The important distinction is control context available and respected.

---

## 2. E1 raw model vs final system result

| Field | Raw model | Final system |
|---|---|---|
| status | RECOMMENDATION | RECOMMENDATION |
| theme | Sleep Duration Decline and Caffeine Timing | same |
| insight | sleep 5.8 h vs 7.1 h, coinciding with afternoon caffeine | same |
| recommendation | move caffeine earlier | same |
| `final_recommendation_allowed` | true | true |
| Sanitizer | idle | idle |

Raw and final match. F4.7 correctly *permits* this recommendation (both gates true). Whether E1 should be a recommendation is a UX/T7 question, not T6.

---

## 3. Respiratory-rate fields actually visible to Gemini

On model call 1 (`origin=deterministic_analytics`, `source_id=get_trend_signals`):

- current `14.3`
- baseline `14.54`
- percent change `−1.67`
- direction `stable`
- maturity `ESTABLISHED_TREND`
- coverage `1.0` (7/7)
- `control_metric=true`
- `insight_candidate=false`
- `salience_level=none`
- reason `stable_control_context`
- payload `control_metrics=['respiratory_rate']`

---

## 4. Whether Gemini used / ignored the control appropriately

**Respected.** Sleep is treated as a specific decline. RR is not promoted to INSIGHT, not listed as a primary, and is not turned into a respiratory-health story.

**Not explicitly used in prose.** The model did not say “this looks sleep-specific because respiratory rate is stable.” That is not required.

---

## 5. Unsupported physiological generalization

Frozen E1 insight: *“physical activity levels and cardiovascular indicators have remained stable”* — despite HRV improving and RR being invisible.

Live E1 insight: sleep numbers + caffeine co-occurrence only.

The T8-style over-generalization **did not recur** on this run.

---

## 6. Evidence / policy behavior

- Query: `sleep duration decline caffeine evening work`
- Relationships: R-07, R-07, R-07
- Verdict: **SURFACE** (`authorized_evidence_present`)
- `recommendation_authorized=true` (lifestyle made `caffeine_mg` evaluable)
- Frozen E1 retrieved R-02 / R-01, QUALIFY, `recommendation_authorized=false` (no lifestyle tool)

This is the same F4.4/F4.7 A1 path. Late-work events were visible and named in the query; the insight mentions only caffeine. Existing unused-confounder / caffeine-latch pattern, not a T6 miss.

---

## 7. Recommendation-boundary behavior

- `recommendation_worthy=true`
- `recommendation_authorized=true`
- `final_recommendation_allowed=true`
- `model_respected_boundary=true`
- `final_output_respects_boundary=true`
- violations `[]`

---

## 8. Guard result

**PASS**, violations `[]`. Confidence language **HIGH** (frozen E1 was MODERATE).

---

## 9. B1 live result

**run_id:** `70333797-4a10-48f6-a028-606e844f1560`  
**as_of:** 2026-06-18 · **latency_ms:** 9437 · **model calls:** 2 · F4.2 fidelity: yes

### Trajectory
1. `get_trend_signals` — steps/exercise barely-directional `improving`; RR stable +1.33%, `control_metric=true`, `insight_candidate=false`; payload `insight_worthy=false`
2. DECISION: “Detectable directional movement is not insight-worthy: exercise_minutes, steps.”
3. FINAL `NO_SIGNIFICANT_NEW_PATTERN`

No lifestyle tool. No evidence retrieval.

### RR visible to Gemini
- current `14.53` / baseline `14.34` / +1.33% / `stable`
- maturity `ESTABLISHED_TREND`, coverage 7/7
- `control_metric=true`, `insight_candidate=false`, `salience_level=none`

---

## 10. B1 remained NO_SIGNIFICANT_NEW_PATTERN

**Yes.** Raw and final status match. Rec field null. Gate `allowed=false`. Guard PASS.

`reason_not_surfaced` factually lists respiratory rate among stable metrics. That is not an INSIGHT, not a reassurance directive, and does not override F4.6. Adding the control metric **did not reopen T5**.

---

## 11. F4.2 TRACE confirmation

| | E1 | B1 |
|---|---|---|
| model calls | 4 | 2 |
| tool calls | trends, lifestyle, evidence | trends only |
| `adk_pre_model_request` | all calls | all calls |
| RR in LLM-visible tool result | yes | yes |
| origin | `deterministic_analytics` | `deterministic_analytics` |
| salience/control role visible | `control_metric` + `control_metrics` + `stable_control_context` | same |
| omitted thought parts | 0 | 0 |

---

## 12. Baseline vs post-F4.8

| | Frozen E1 | Live E1 | Frozen B1 | Live B1 |
|---|---|---|---|---|
| RR reachable | no | **yes** | no | **yes** |
| T6 testable | no | **yes** | n/a | n/a |
| Sleep treated as specific | yes | yes | n/a | n/a |
| Cardio over-generalization | **yes** | **no** | n/a | n/a |
| Status | INSIGHT | RECOMMENDATION | INSIGHT (T5) | **NO_SIGNIFICANT_NEW_PATTERN** |
| T5 honor | n/a | n/a | fail | **honored** |

Improved: RR is in the contract and Gemini can see it; E1 no longer invents “cardiovascular indicators remained stable”; B1 stays non-salient.

Unresolved / orthogonal: E1 is now a caffeine RECOMMENDATION (same family as live A1). Frozen E1 remains FAIL. T8 is not separately remediating here; it simply did not recur on this run.

---

## 13. New failure modes

1. **E1 caffeine latch (known, not T6).** Same as-of date as A1. F4.4 made lifestyle evaluable; F4.7 correctly permits the rec when both gates are true. Late-work visible, unused in prose.
2. **E1 confidence HIGH** vs frozen MODERATE. Observational only.
3. No new T6 failure. No T5 reopen.

No code fixes from this measurement.

---

## 14. T6 live-validation verdict

**T6 LIVE VALIDATED.**

The control-metric contract held on both required scenarios:

- E1: RR visible, stable, not promoted, sleep remains the specific change, no respiratory/cardiorespiratory reassurance claim
- B1: RR visible and stable; `insight_worthy` stays false; final status `NO_SIGNIFICANT_NEW_PATTERN`

Frozen human PASS/FAIL unchanged. CODIFY not started. T12 / T7 / T8 remediation not started. Full 15-scenario baseline not rerun.
