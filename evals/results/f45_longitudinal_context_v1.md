# F4.5 Longitudinal context inspection (B3 / B1)

Deterministic only. No Gemini. Weekly summaries remain observed-week facts.

**Thresholds:** material change ≥ 3.0% (same knob as F4.1 stable band). Long-term reference = history older than the F4.1 60-day baseline, within a 90-day cap.

## HC-EVAL-B3 — 2026-08-17

Primary — recent stability vs older personal baseline

- Maintaining gains: ['resting_hr_bpm', 'hrv_sdnn_ms', 'vo2_max']
- Maintaining decline: ['steps']

| metric | recent dir | recent % | current | F4.1 baseline | long-term ref | vs old % | maint. gain | available |
|---|---|---|---|---|---|---|---|---|
| exercise_minutes | improving | 8.05 | 26.76 | 24.76 | 11.18 | 139.39 | False | True |
| workout_count | improving | 8.16 | 0.43 | 0.4 | 0.29 | 50.5 | False | True |
| resting_hr_bpm | stable | -1.33 | 67.91 | 68.83 | 71.07 | -4.44 | True | True |
| hrv_sdnn_ms | stable | 2.81 | 36.83 | 35.82 | 31.74 | 16.03 | True | True |
| steps | stable | 0.45 | 8562.0 | 8523.28 | 10387.39 | -17.57 | False | True |
| sleep_duration_hours | decreasing | -4.27 | 6.52 | 6.81 | 6.99 | -6.78 | False | True |
| vo2_max | stable | 2.03 | 40.54 | 39.73 | 38.5 | 5.31 | True | True |

## HC-EVAL-B1 — 2026-06-18

Negative control — stable early calibration

- Maintaining gains: []
- Maintaining decline: []

| metric | recent dir | recent % | current | F4.1 baseline | long-term ref | vs old % | maint. gain | available |
|---|---|---|---|---|---|---|---|---|
| exercise_minutes | improving | 3.87 | 11.5 | 11.07 | None | None | False | False |
| workout_count | stable | 0.0 | 0.29 | 0.29 | None | None | False | False |
| resting_hr_bpm | stable | 1.35 | 71.79 | 70.83 | None | None | False | False |
| hrv_sdnn_ms | stable | 1.63 | 32.13 | 31.61 | None | None | False | False |
| steps | improving | 6.55 | 10889.71 | 10219.95 | None | None | False | False |
| sleep_duration_hours | stable | -1.79 | 6.9 | 7.03 | None | None | False | False |
| vo2_max | stable | -0.12 | 38.46 | 38.51 | None | None | False | False |

## B3 answers

1. Recent 7-vs-60 is not a blank slate; several metrics are stable while exercise/workouts may still move. Maintenance flags use **stable** recent direction: ['resting_hr_bpm', 'hrv_sdnn_ms', 'vo2_max']
2. Still materially better than the older (pre-F4.1-baseline) reference: True
3. Support maintenance-of-gain: ['resting_hr_bpm', 'hrv_sdnn_ms', 'vo2_max']
4. Do not: ['exercise_minutes', 'workout_count', 'steps', 'sleep_duration_hours']
5. Contract can distinguish nothing-new vs holding gains: True
6. Grounded in Marcus prefix 2026-05-20→2026-06-18 vs current week 2026-08-11→2026-08-17.

## Negative control

- B1 maintenance_of_gain all false: True
- Weekly summaries cannot independently claim maintenance: True
