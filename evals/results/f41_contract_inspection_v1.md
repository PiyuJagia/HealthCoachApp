# F4.1.1 Deterministic contract inspection

Inspection only. No Gemini. Canonical Marcus seed dates.

**Contradiction count:** 0
**Foundation safe to accept:** True

## Answers

1. D1 preserves recent HRV trend while marking today missing: **True**
2. D2 preserves history while identifying the same-day sync gap: **True**
3. D3 allows trend reasoning (10 valid days, not 15-in-30): **True**
4. A1 mature-data control behaves normally: **True**

## HC-EVAL-D1 — 2026-07-13

HRV missing on as-of date; recent history exists

Payload: gap_caveat_required=True; as_of_any_daily_metric_available=True; data_sufficient_present=False

| metric | cadence | as_of_value | as_of_avail | n_cur/exp | cov | n_base | ready | latest | partial | gap | state | dir | pct | snap/early/trend | rec | basis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sleep_duration_hours | daily | 7.58 | true | 7/7 | 1.0 | 45 | true | 2026-07-13 / 7.58 | false | false | ESTABLISHED_TREND | increasing | 5.09 | true/true/true | true | established_trend |
| resting_hr_bpm | daily | 67.7 | true | 7/7 | 1.0 | 46 | true | 2026-07-13 / 67.7 | false | false | ESTABLISHED_TREND | decreasing | -3.47 | true/true/true | true | established_trend |
| hrv_sdnn_ms | daily | None | false | 5/7 | 0.7143 | 46 | true | 2026-07-11 / 33.5 | true | true | ESTABLISHED_TREND | improving | 6.05 | true/true/true | true | established_trend |
| exercise_minutes | activity_dependent | 47.5 | true | 7/7 | 1.0 | 46 | true | 2026-07-13 / 47.5 | false | false | ESTABLISHED_TREND | improving | 76.36 | true/true/true | true | established_trend |
| workout_count | activity_dependent | 1.0 | true | 7/7 | 1.0 | 46 | true | 2026-07-13 / 1.0 | false | false | ESTABLISHED_TREND | improving | 40.82 | true/true/true | true | established_trend |
| steps | daily | 9070.0 | true | 7/7 | 1.0 | 46 | true | 2026-07-13 / 9070.0 | false | false | ESTABLISHED_TREND | declining | -10.34 | true/true/true | true | established_trend |
| vo2_max | episodic | 39.97 | true | 7/1 | 1.0 | 45 | true | 2026-07-13 / 39.97 | false | false | ESTABLISHED_TREND | stable | 2.99 | true/true/true | true | established_trend |

Contradictions: none.

Weekly-summary notes:
- Latest weekly_summary has averages but no claim_eligibility object.
- hrv_sdnn_ms: week average/total is computed from 5/7 days; coverage is attached but the average still looks like a complete-week number.

VO2: cadence=episodic; expected=1; n_cur=7; coverage=1.0; as_of=True; gap=False; state=ESTABLISHED_TREND

## HC-EVAL-D2 — 2026-06-10

Full same-day wearable sync gap; recent history exists

Payload: gap_caveat_required=True; as_of_any_daily_metric_available=False; data_sufficient_present=False

| metric | cadence | as_of_value | as_of_avail | n_cur/exp | cov | n_base | ready | latest | partial | gap | state | dir | pct | snap/early/trend | rec | basis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sleep_duration_hours | daily | None | false | 6/7 | 0.8571 | 15 | true | 2026-06-09 / 7.23 | true | true | ESTABLISHED_TREND | stable | 0.38 | true/true/true | true | established_trend |
| resting_hr_bpm | daily | None | false | 6/7 | 0.8571 | 15 | true | 2026-06-09 / 69.4 | true | true | ESTABLISHED_TREND | stable | 0.14 | true/true/true | true | established_trend |
| hrv_sdnn_ms | daily | None | false | 6/7 | 0.8571 | 15 | true | 2026-06-09 / 31.0 | true | true | ESTABLISHED_TREND | stable | -2.19 | true/true/true | true | established_trend |
| exercise_minutes | activity_dependent | None | false | 6/7 | 0.8571 | 15 | true | 2026-06-09 / 5.6 | true | true | ESTABLISHED_TREND | improving | 36.21 | true/true/true | true | established_trend |
| workout_count | activity_dependent | None | false | 6/7 | 0.8571 | 15 | true | 2026-06-09 / 0.0 | true | true | ESTABLISHED_TREND | improving | 25.0 | true/true/true | true | established_trend |
| steps | daily | None | false | 6/7 | 0.8571 | 15 | true | 2026-06-09 / 9779.0 | true | true | ESTABLISHED_TREND | improving | 6.43 | true/true/true | true | established_trend |
| vo2_max | episodic | None | false | 6/1 | 1.0 | 15 | true | 2026-06-09 / 38.59 | false | false | ESTABLISHED_TREND | stable | -0.17 | true/true/true | true | established_trend |

Contradictions: none.

Weekly-summary notes:
- Latest weekly_summary has averages but no claim_eligibility object.
- sleep_duration_hours: week average/total is computed from 6/7 days; coverage is attached but the average still looks like a complete-week number.
- resting_hr_bpm: week average/total is computed from 6/7 days; coverage is attached but the average still looks like a complete-week number.
- hrv_sdnn_ms: week average/total is computed from 6/7 days; coverage is attached but the average still looks like a complete-week number.
- exercise_minutes: week average/total is computed from 6/7 days; coverage is attached but the average still looks like a complete-week number.
- workout_count: week average/total is computed from 6/7 days; coverage is attached but the average still looks like a complete-week number.
- steps: week average/total is computed from 6/7 days; coverage is attached but the average still looks like a complete-week number.

VO2: cadence=episodic; expected=1; n_cur=6; coverage=1.0; as_of=False; gap=False; state=ESTABLISHED_TREND

## HC-EVAL-D3 — 2026-06-08

Shorter history that failed the old 15-in-30 rule

Payload: gap_caveat_required=False; as_of_any_daily_metric_available=True; data_sufficient_present=False

| metric | cadence | as_of_value | as_of_avail | n_cur/exp | cov | n_base | ready | latest | partial | gap | state | dir | pct | snap/early/trend | rec | basis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sleep_duration_hours | daily | 7.07 | true | 7/7 | 1.0 | 13 | true | 2026-06-08 / 7.07 | false | false | ESTABLISHED_TREND | stable | -0.37 | true/true/true | true | established_trend |
| resting_hr_bpm | daily | 72.2 | true | 7/7 | 1.0 | 13 | true | 2026-06-08 / 72.2 | false | false | ESTABLISHED_TREND | stable | 0.75 | true/true/true | true | established_trend |
| hrv_sdnn_ms | daily | 28.9 | true | 7/7 | 1.0 | 13 | true | 2026-06-08 / 28.9 | false | false | ESTABLISHED_TREND | declining | -5.33 | true/true/true | true | established_trend |
| exercise_minutes | activity_dependent | 33.0 | true | 7/7 | 1.0 | 13 | true | 2026-06-08 / 33.0 | false | false | ESTABLISHED_TREND | improving | 73.83 | true/true/true | true | established_trend |
| workout_count | activity_dependent | 1.0 | true | 7/7 | 1.0 | 13 | true | 2026-06-08 / 1.0 | false | false | ESTABLISHED_TREND | improving | 85.71 | true/true/true | true | established_trend |
| steps | daily | 10268.0 | true | 7/7 | 1.0 | 13 | true | 2026-06-08 / 10268.0 | false | false | ESTABLISHED_TREND | improving | 12.61 | true/true/true | true | established_trend |
| vo2_max | episodic | 38.48 | true | 7/1 | 1.0 | 13 | true | 2026-06-08 / 38.48 | false | false | ESTABLISHED_TREND | stable | -0.11 | true/true/true | true | established_trend |

Contradictions: none.

Weekly-summary notes:
- Latest weekly_summary has averages but no claim_eligibility object.

VO2: cadence=episodic; expected=1; n_cur=7; coverage=1.0; as_of=True; gap=False; state=ESTABLISHED_TREND

## HC-EVAL-A1 — 2026-08-02

Mature-data control — clear sleep deterioration

Payload: gap_caveat_required=False; as_of_any_daily_metric_available=True; data_sufficient_present=False

| metric | cadence | as_of_value | as_of_avail | n_cur/exp | cov | n_base | ready | latest | partial | gap | state | dir | pct | snap/early/trend | rec | basis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sleep_duration_hours | daily | 5.5 | true | 7/7 | 1.0 | 50 | true | 2026-08-02 / 5.5 | false | false | ESTABLISHED_TREND | decreasing | -18.0 | true/true/true | true | established_trend |
| resting_hr_bpm | daily | 70.2 | true | 7/7 | 1.0 | 51 | true | 2026-08-02 / 70.2 | false | false | ESTABLISHED_TREND | stable | 0.18 | true/true/true | true | established_trend |
| hrv_sdnn_ms | daily | 49.4 | true | 7/7 | 1.0 | 49 | true | 2026-08-02 / 49.4 | false | false | ESTABLISHED_TREND | improving | 11.72 | true/true/true | true | established_trend |
| exercise_minutes | activity_dependent | 14.6 | true | 7/7 | 1.0 | 51 | true | 2026-08-02 / 14.6 | false | false | ESTABLISHED_TREND | improving | 29.02 | true/true/true | true | established_trend |
| workout_count | activity_dependent | 0.0 | true | 7/7 | 1.0 | 51 | true | 2026-08-02 / 0.0 | false | false | ESTABLISHED_TREND | improving | 21.43 | true/true/true | true | established_trend |
| steps | daily | 8205.0 | true | 7/7 | 1.0 | 51 | true | 2026-08-02 / 8205.0 | false | false | ESTABLISHED_TREND | stable | -1.61 | true/true/true | true | established_trend |
| vo2_max | episodic | 39.93 | true | 7/1 | 1.0 | 50 | true | 2026-08-02 / 39.93 | false | false | ESTABLISHED_TREND | stable | 1.8 | true/true/true | true | established_trend |

Contradictions: none.

Weekly-summary notes:
- Latest weekly_summary has averages but no claim_eligibility object.

VO2: cadence=episodic; expected=1; n_cur=7; coverage=1.0; as_of=True; gap=False; state=ESTABLISHED_TREND

