# F4.8 Respiratory-rate control-metric inspection

Deterministic only. No Gemini. No clinical respiratory thresholds.

## Original E1 limitation

HC-EVAL-E1 (2026-08-02) stored a stable `respiratory_rate` in `health_daily`, but the
metric was omitted from `METRIC_SPECS` / `get_trend_signals`. Gemini had zero access
and generalized other signals as “cardiovascular indicators remained stable.”

## Implementation

- Daily cadence, same F4.1 maturity/provenance contract as other daily metrics.
- `control_metric=true` on the metric spec, trend row, and salience row.
- Payload `insight_salience.control_metrics` lists designated controls.
- Stable/barely-directional RR is not an insight candidate and cannot create maintenance flags.
- Weekly summaries include `average_respiratory_rate` with F4.3 claim_semantics.

## HC-EVAL-E1 — 2026-08-02

- insight_worthy: `True`
- primary_metrics: ['exercise_minutes', 'workout_count', 'sleep_duration_hours', 'hrv_sdnn_ms', 'steps']
- control_metrics: ['respiratory_rate']
- sleep: decreasing -18.0% / 5.83 vs 7.11
- respiratory_rate: stable -1.67% / 14.3 vs 14.54
- RR maturity: `ESTABLISHED_TREND` coverage 7/7
- RR insight_candidate: `False`
- RR weekly average: `14.3` comparison_allowed=`True`

| metric | current | baseline | % | dir | maturity | cov | control | insight_cand | reasons |
|---|---|---|---|---|---|---|---|---|---|
| sleep_duration_hours | 5.83 | 7.11 | -18.0 | decreasing | ESTABLISHED_TREND | 7/7 | False | True | strong_recent_change |
| resting_hr_bpm | 69.49 | 69.36 | 0.18 | stable | ESTABLISHED_TREND | 7/7 | False | False |  |
| hrv_sdnn_ms | 38.04 | 34.05 | 11.72 | improving | ESTABLISHED_TREND | 7/7 | False | True | clear_recent_change |
| exercise_minutes | 26.91 | 20.86 | 29.02 | improving | ESTABLISHED_TREND | 7/7 | False | True | clear_recent_change |
| vo2_max | 40.0 | 39.3 | 1.8 | stable | ESTABLISHED_TREND | 7/1 | False | False |  |
| respiratory_rate | 14.3 | 14.54 | -1.67 | stable | ESTABLISHED_TREND | 7/7 | True | False | stable_control_context |

### Deterministic answers

1. Is respiratory rate stable? **Yes** — direction `stable`, percent change `-1.67` (below the 3% detectability knob).
2. Does its presence help bound the sleep decline? **Yes** — sleep remains the salient decline; RR is a stable control on the same as-of date.
3. Does the contract avoid an independent reassurance claim? **Yes** — `insight_candidate=false`, not in `primary_metrics`, `control_metric=true`.
4. Can Gemini now distinguish sleep decline from broader physiological deterioration? **Contract yes** — RR is visible with provenance. Live Gemini not run in this phase.

## Negative controls

### B1 2026-06-18 (stable period)

- insight_worthy: `False`
- RR direction: `stable`
- RR insight_candidate: `False`
- Stable RR does not independently create INSIGHT.

### D2 / synthetic partial coverage

- D2 as-of available: `False`
- D2 gap caveat: `True`
- Synthetic partial current observations: `4/7`
- Synthetic as-of available: `False` (no silent imputation)

### Immature baseline

- maturity: `EARLY_PATTERN`
- trend_allowed: `False`
- published direction: `unknown`
- percent_change: `None`

## TRACE

F4.2 `model_calls[]` extract `respiratory_rate` from `get_trend_signals` with
`origin=deterministic_analytics` (existing F4.2 constant; not a second origin).
Visible fields include value, maturity, direction when allowed, `control_metric`,
and coverage/provenance. No hidden CoT.
