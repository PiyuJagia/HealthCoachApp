# F4.6 Salience inspection

Deterministic only. No Gemini. Salience knobs are product surfacing thresholds, not clinical cutoffs.

## HC-EVAL-B1 — 2026-06-18

Low-salience negative control

- insight_worthy: `False`
- recommendation_worthy: `False`
- salience_level: `low`
- primary_metrics: []
- reasons: ['same_family_weak_corroboration', 'detectable_but_small_absolute', 'no_older_horizon']
- lifestyle events: 4 inputs=['alcohol_units', 'caffeine_mg']

| metric | dir | % | abs | maturity | trend_ok | early | maint_gain | level | band | insight_cand | reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sleep_duration_hours | stable | -1.79 | -0.13 | ESTABLISHED_TREND | True | True | False | none | none | False | no_older_horizon |
| resting_hr_bpm | stable | 1.35 | 0.96 | ESTABLISHED_TREND | True | True | False | none | none | False | no_older_horizon |
| hrv_sdnn_ms | stable | 1.63 | 0.51 | ESTABLISHED_TREND | True | True | False | none | none | False | no_older_horizon |
| exercise_minutes | improving | 3.87 | 0.43 | ESTABLISHED_TREND | True | True | False | low | barely_directional | False | same_family_weak_corroboration, detectable_but_small_absolute, no_older_horizon |
| workout_count | stable | 0.0 | 0.0 | ESTABLISHED_TREND | True | True | False | none | none | False | no_older_horizon |
| steps | improving | 6.55 | 669.76 | ESTABLISHED_TREND | True | True | False | low | barely_directional | False | same_family_weak_corroboration, detectable_but_small_absolute, no_older_horizon |
| vo2_max | stable | -0.12 | -0.05 | ESTABLISHED_TREND | True | True | False | none | none | False | no_older_horizon |

## HC-EVAL-A1 — 2026-08-02

Large isolated sleep decline

- insight_worthy: `True`
- recommendation_worthy: `True`
- salience_level: `high`
- primary_metrics: ['exercise_minutes', 'workout_count', 'sleep_duration_hours', 'hrv_sdnn_ms', 'steps']
- reasons: ['strong_recent_change', 'clear_recent_change', 'maintenance_of_decline']
- lifestyle events: 17 inputs=['alcohol_units', 'caffeine_mg']

| metric | dir | % | abs | maturity | trend_ok | early | maint_gain | level | band | insight_cand | reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sleep_duration_hours | decreasing | -18.0 | -1.28 | ESTABLISHED_TREND | True | True | False | high | strong | True | strong_recent_change |
| resting_hr_bpm | stable | 0.18 | 0.12 | ESTABLISHED_TREND | True | True | False | none | none | False |  |
| hrv_sdnn_ms | improving | 11.72 | 3.99 | ESTABLISHED_TREND | True | True | False | high | clear | True | clear_recent_change |
| exercise_minutes | improving | 29.02 | 6.05 | ESTABLISHED_TREND | True | True | False | high | clear | True | clear_recent_change |
| workout_count | improving | 21.43 | 0.08 | ESTABLISHED_TREND | True | True | False | high | clear | True | clear_recent_change |
| steps | stable | -1.61 | -145.06 | ESTABLISHED_TREND | True | True | False | moderate | none | True | maintenance_of_decline |
| vo2_max | stable | 1.8 | 0.71 | ESTABLISHED_TREND | True | True | False | none | none | False |  |

## HC-EVAL-B3 — 2026-08-17

F4.5 maintenance must remain eligible

- insight_worthy: `True`
- recommendation_worthy: `False`
- salience_level: `moderate`
- primary_metrics: ['hrv_sdnn_ms', 'vo2_max', 'resting_hr_bpm', 'steps']
- reasons: ['maintenance_of_gain', 'maintenance_of_decline']
- lifestyle events: 4 inputs=['alcohol_units', 'caffeine_mg']

| metric | dir | % | abs | maturity | trend_ok | early | maint_gain | level | band | insight_cand | reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sleep_duration_hours | decreasing | -4.27 | -0.29 | ESTABLISHED_TREND | True | True | False | low | barely_directional | False | detectable_but_small_absolute, isolated_barely_directional |
| resting_hr_bpm | stable | -1.33 | -0.91 | ESTABLISHED_TREND | True | True | True | moderate | none | True | maintenance_of_gain |
| hrv_sdnn_ms | stable | 2.81 | 1.01 | ESTABLISHED_TREND | True | True | True | moderate | none | True | maintenance_of_gain |
| exercise_minutes | improving | 8.05 | 1.99 | ESTABLISHED_TREND | True | True | False | low | barely_directional | False | same_family_weak_corroboration, detectable_but_small_absolute |
| workout_count | improving | 8.16 | 0.03 | ESTABLISHED_TREND | True | True | False | low | barely_directional | False | same_family_weak_corroboration, detectable_but_small_absolute |
| steps | stable | 0.45 | 38.72 | ESTABLISHED_TREND | True | True | False | moderate | none | True | maintenance_of_decline |
| vo2_max | stable | 2.03 | 0.81 | ESTABLISHED_TREND | True | True | True | moderate | none | True | maintenance_of_gain |

## HC-EVAL-C3 — 2026-06-29

Lifestyle must not manufacture sleep salience

- insight_worthy: `True`
- recommendation_worthy: `True`
- salience_level: `high`
- primary_metrics: ['exercise_minutes', 'workout_count', 'steps']
- reasons: ['strong_recent_change', 'clear_recent_change', 'no_older_horizon']
- lifestyle events: 4 inputs=['alcohol_units', 'caffeine_mg']

| metric | dir | % | abs | maturity | trend_ok | early | maint_gain | level | band | insight_cand | reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sleep_duration_hours | stable | 2.06 | 0.14 | ESTABLISHED_TREND | True | True | False | none | none | False | no_older_horizon |
| resting_hr_bpm | stable | -1.89 | -1.34 | ESTABLISHED_TREND | True | True | False | none | none | False | no_older_horizon |
| hrv_sdnn_ms | improving | 4.52 | 1.44 | ESTABLISHED_TREND | True | True | False | low | barely_directional | False | detectable_but_small_absolute, isolated_barely_directional, no_older_horizon |
| exercise_minutes | improving | 152.53 | 15.96 | ESTABLISHED_TREND | True | True | False | high | strong | True | strong_recent_change, no_older_horizon |
| workout_count | improving | 71.43 | 0.18 | ESTABLISHED_TREND | True | True | False | high | clear | True | clear_recent_change, no_older_horizon |
| steps | declining | -15.89 | -1585.96 | ESTABLISHED_TREND | True | True | False | high | strong | True | strong_recent_change, no_older_horizon |
| vo2_max | stable | 1.17 | 0.45 | ESTABLISHED_TREND | True | True | False | none | none | False | no_older_horizon |

## SYNTHETIC-EARLY-PATTERN — 2026-06-12

Strong early-pattern observation must not be auto-suppressed

- insight_worthy: `True`
- recommendation_worthy: `False`
- sleep maturity: `EARLY_PATTERN`
- baseline_ready: `False`
- trend_allowed: `False`
- early_pattern_allowed: `True`
- published direction: `unknown` (F4.1 still blanks established-trend direction)
- salience band: `strong`
- insight_candidate: `True`
- reasons: ['strong_recent_change', 'recovery_family_corroboration', 'early_pattern_observation', 'no_older_horizon']
