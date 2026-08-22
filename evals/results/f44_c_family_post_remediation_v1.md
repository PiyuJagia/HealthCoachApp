# F4.4 targeted post-remediation evaluation — C1 / C2 / C3

Live Gemini run on the current F4.4 system. Frozen human PASS/FAIL labels were **not** changed.
Prompts, policy principles, analytics, and lifestyle tooling were not modified for this run.
Only HC-EVAL-C1, C2, and C3 were executed. Capture fidelity: `adk_pre_model_request`.

## HC-EVAL-C1 — 2026-08-02

- get_trend_signals called: **True**
- get_lifestyle_context called: **True**
- retrieve_authorized_evidence called: **True**
- lifestyle summary: `{"as_of_date": "2026-08-02", "event_count": 17, "event_types": ["alcohol", "caffeine", "mood"], "late_work_context_event_count": 7, "lookback_days": 14, "policy_available_inputs": ["alcohol_units", "caffeine_mg"], "window_end": "2026-08-02", "window_start": "2026-07-20"}`
- policy available_inputs reached: **{'available_inputs': ['alcohol_units', 'caffeine_mg'], 'reached': True, 'has_caffeine_mg': True, 'has_alcohol_units': True}**
- relationships retrieved: `['R-07', 'R-07', 'R-07']`
- evidence queries: `['sleep duration decline late caffeine afternoon coffee']`
- policy verdict: **SURFACE** reasons=`['authorized_evidence_present']`
- association ≠ causation preserved: **True** (causal_hits=[]; association_hits=['\\bco-occur'])
- mentions: `{'caffeine': True, 'alcohol': False, 'late work': False, 'work': False, 'sleep': True}`
- final status: **RECOMMENDATION**
- theme: Sleep Duration Decline and Caffeine Timing
- insight: Your average daily sleep duration decreased from 7.11 hours to 5.83 hours (-18%) over the past week. Stored lifestyle records show regular late-afternoon caffeine intake (200 mg around 16:00), which co-occurs with reduced sleep duration.
- recommendation: Consider shifting caffeine intake to earlier in the day (avoiding consumption within 6 to 8 hours of bedtime) to help support sleep duration and rest quality.
- recommendation_authorized: True
- final guard: passed=True violations=[]
- model-call count: **4** (F4.2 fidelity=True)
- latency_ms: **25082**
- run_id / trace: `73208327-6e81-49f8-a675-ce88aea31af5` / `C:\Users\14042\Desktop\AI-Projects\health-coach-ai\evals\results\f44_c_family_traces\73208327-6e81-49f8-a675-ce88aea31af5.json`

Lifestyle events visible to Gemini:

- 2026-07-20 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-21 12:00:00 mood qty=3.0 scale_1_5 notes=Synthetic self-report
- 2026-07-21 16:30:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-21 20:30:00 alcohol qty=1.0 standard_drinks notes=Synthetic social evening
- 2026-07-22 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-23 16:45:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-24 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-25 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-26 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-27 16:45:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-28 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-29 16:30:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-30 12:00:00 mood qty=4.0 scale_1_5 notes=Synthetic self-report
- 2026-07-30 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-31 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-08-01 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-08-02 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee

Frozen baseline human label (unchanged): **FAIL**
Lifestyle access vs baseline: improved=True; caffeine visible=True; policy inputs reached=True

## HC-EVAL-C2 — 2026-07-31

- get_trend_signals called: **True**
- get_lifestyle_context called: **True**
- retrieve_authorized_evidence called: **True**
- lifestyle summary: `{"as_of_date": "2026-07-31", "event_count": 16, "event_types": ["alcohol", "caffeine", "mood"], "late_work_context_event_count": 6, "lookback_days": 14, "policy_available_inputs": ["alcohol_units", "caffeine_mg"], "window_end": "2026-07-31", "window_start": "2026-07-18"}`
- policy available_inputs reached: **{'available_inputs': ['alcohol_units', 'caffeine_mg'], 'reached': True, 'has_caffeine_mg': True, 'has_alcohol_units': True}**
- relationships retrieved: `['R-07', 'R-07', 'R-07']`
- evidence queries: `['caffeine late afternoon sleep duration']`
- policy verdict: **SURFACE** reasons=`['authorized_evidence_present']`
- association ≠ causation preserved: **True** (causal_hits=[]; association_hits=['\\bcoincid'])
- mentions: `{'caffeine': True, 'alcohol': False, 'late work': False, 'work': False, 'sleep': True}`
- final status: **RECOMMENDATION**
- theme: Sleep Duration and Caffeine Timing
- insight: Your average sleep duration decreased over the past week to 6.04 hours compared to your 7.14 hour baseline, coinciding with regular late-afternoon caffeine intake.
- recommendation: Consider consuming caffeine earlier in the day to avoid potential disruption to your night-time sleep.
- recommendation_authorized: True
- final guard: passed=True violations=[]
- model-call count: **4** (F4.2 fidelity=True)
- latency_ms: **76106**
- run_id / trace: `98d41dd1-c319-4071-843f-b9da8e241e8c` / `C:\Users\14042\Desktop\AI-Projects\health-coach-ai\evals\results\f44_c_family_traces\98d41dd1-c319-4071-843f-b9da8e241e8c.json`

Lifestyle events visible to Gemini:

- 2026-07-19 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-20 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-21 12:00:00 mood qty=3.0 scale_1_5 notes=Synthetic self-report
- 2026-07-21 16:30:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-21 20:30:00 alcohol qty=1.0 standard_drinks notes=Synthetic social evening
- 2026-07-22 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-23 16:45:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-24 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-25 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-26 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-27 16:45:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-28 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-29 16:30:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-30 12:00:00 mood qty=4.0 scale_1_5 notes=Synthetic self-report
- 2026-07-30 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-31 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee

Frozen baseline human label (unchanged): **FAIL**
Lifestyle access vs baseline: improved=True; caffeine visible=True; policy inputs reached=True

## HC-EVAL-C3 — 2026-06-29

- get_trend_signals called: **True**
- get_lifestyle_context called: **True**
- retrieve_authorized_evidence called: **True**
- lifestyle summary: `{"as_of_date": "2026-06-29", "event_count": 4, "event_types": ["alcohol", "caffeine", "mood"], "late_work_context_event_count": 0, "lookback_days": 14, "policy_available_inputs": ["alcohol_units", "caffeine_mg"], "window_end": "2026-06-29", "window_start": "2026-06-16"}`
- policy available_inputs reached: **{'available_inputs': ['alcohol_units', 'caffeine_mg'], 'reached': True, 'has_caffeine_mg': True, 'has_alcohol_units': True}**
- relationships retrieved: `['R-05', 'R-05']`
- evidence queries: `['exercise minutes workout frequency cardiovascular indicators hrv resting heart rate']`
- policy verdict: **SURFACE** reasons=`['authorized_evidence_present']`
- association ≠ causation preserved: **True** (causal_hits=[]; association_hits=[])
- mentions: `{'caffeine': False, 'alcohol': False, 'late work': False, 'work': True, 'sleep': False}`
- final status: **RECOMMENDATION**
- theme: Exercise Consistency and Cardiovascular Health
- insight: Your weekly exercise duration and workout frequency have increased significantly compared to baseline, while resting heart rate and heart rate variability remain favorable.
- recommendation: Maintain a regular aerobic exercise routine to support ongoing cardiovascular fitness and physiological recovery.
- recommendation_authorized: True
- final guard: passed=True violations=[]
- model-call count: **4** (F4.2 fidelity=True)
- latency_ms: **21567**
- run_id / trace: `029c1fc9-3127-4ca6-88ca-bd83e28d58ce` / `C:\Users\14042\Desktop\AI-Projects\health-coach-ai\evals\results\f44_c_family_traces\029c1fc9-3127-4ca6-88ca-bd83e28d58ce.json`

Lifestyle events visible to Gemini:

- 2026-06-19 12:00:00 mood qty=4.0 scale_1_5 notes=Synthetic self-report
- 2026-06-24 20:30:00 alcohol qty=1.0 standard_drinks notes=Synthetic social evening
- 2026-06-26 15:00:00 caffeine qty=180.0 mg notes=Synthetic afternoon coffee
- 2026-06-29 15:30:00 caffeine qty=180.0 mg notes=Synthetic afternoon coffee

Frozen baseline human label (unchanged): **FAIL**
Lifestyle access vs baseline: improved=True; caffeine visible=True; policy inputs reached=True

## Comparison table — frozen baseline vs post-F4.4

Frozen human PASS/FAIL is **not** updated.

| | C1 baseline | C1 post-F4.4 | C2 baseline | C2 post-F4.4 | C3 baseline | C3 post-F4.4 |
|---|---|---|---|---|---|---|
| `get_trend_signals` | yes | yes | yes | yes | yes | yes |
| `get_lifestyle_context` | no | **yes** | no | **yes** | no | **yes** |
| Caffeine visible to Gemini | no | **yes (7× 200mg @16:00)** | no | **yes (7× 200mg @16:00)** | no | **yes (2× 180mg @15:xx)** |
| Late-work / alcohol visible to Gemini | no | yes (7 late-work, 1 alcohol) | no | yes (6 late-work, 1 alcohol) | no | alcohol yes; late-work 0 |
| Mentioned in final text | sleep only | sleep + caffeine; not late-work/alcohol | sleep only | sleep + caffeine; **not** late-work/alcohol | exercise; not caffeine | exercise; **not** caffeine |
| Policy `available_inputs` | none (R-07 `INPUT_UNAVAILABLE`) | `caffeine_mg`, `alcohol_units` | none | `caffeine_mg`, `alcohol_units` | none | `caffeine_mg`, `alcohol_units` |
| Relationships retrieved | R-02, R-01 | **R-07** | R-01, R-02 | **R-07** | R-05 | R-05 |
| Policy verdict | QUALIFY | SURFACE | QUALIFY | SURFACE | SURFACE | SURFACE |
| `recommendation_authorized` | false | **true** | false | **true** | true | true |
| Final status | INSIGHT | RECOMMENDATION | INSIGHT | RECOMMENDATION | RECOMMENDATION | RECOMMENDATION |
| Association ≠ causation in prose | n/a (no caffeine) | preserved (`co-occurs`) | n/a | preserved (`coinciding`) | n/a | n/a (caffeine unused) |
| Final guard | PASS | PASS | PASS | PASS | PASS | PASS |
| Model-call count | not captured (pre-F4.2) | 4 (`adk_pre_model_request`) | not captured | 4 | not captured | 4 |
| Latency ms | 26977 | 25082 | 50952 | 76106 (incl. 503 retry) | 12570 | 21567 |
| T1 access gap closed? | fail | **yes** | fail | **yes** | fail | **yes** |
| Scenario intent | caffeine as co-occurring factor | improved | preserve multi-factor ambiguity | **regressed: collapsed to caffeine** | do not cherry-pick caffeine | improved (did not manufacture a caffeine problem) |
| Frozen human label | FAIL | unchanged | FAIL | unchanged | FAIL | unchanged |

## New failure modes revealed

1. **Ambiguity collapse (C2, primary).** Gemini received caffeine, late-work, and alcohol, then retrieved only R-07 and recommended earlier caffeine. C2 requires preserving multiple plausible explanations. T1 access is no longer the blocker; generation/salience is.
2. **R-07 recommendation latch.** Once lifestyle-derived `caffeine_mg` reaches policy, R-07 is recommendation-eligible. C1/C2 flipped from INSIGHT to RECOMMENDATION. That is authorized by existing relationship policy, but it makes caffeine advice the default whenever caffeine is in the window and R-07 is retrieved — including in confounded C2.
3. **Observed-but-unused confounders.** Late-work and alcohol were in the Gemini-visible lifestyle payload for C1 and C2 and did not appear in the user-facing insight.
4. **C3 control is now testable, not fully demonstrated.** Gemini saw caffeine and stable sleep, did not retrieve R-07, and did not blame caffeine. It also never stated that caffeine was present while sleep remained reasonable; it followed the large exercise signal (T5 salience).
5. **T1 is remediated at the tool/TRACE/policy layer.** Remaining C-family risk is trajectory/generation, not missing lifestyle data.

Human PASS/FAIL labels remain frozen. CODIFY not started. Full 15-scenario Gemini rerun not started.
