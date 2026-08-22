# F4.9 Within-window HRV spread inspection

Deterministic only. No Gemini. No CODIFY. Frozen labels unchanged.
HRV-only MVP. Level change and within-window spread remain distinct.

## Contract

- Object: `within_window_spread` on the HRV trend row.
- Fields: observation_count, mean, sample_standard_deviation, min, max, range,
  baseline_standard_deviation, spread_ratio, spread_observation_allowed,
  spread_comparison_allowed.
- Same F4.1 current/baseline windows. No band, CV, 0–100 score, clinical threshold,
  causal interpretation, salience promotion, recommendation authority, or T7/T8.

## HC-EVAL-C4 — 2026-07-28

- reconstructed current 7d HRV: `[28.7, 48.9, 30.5, 44.9, 25.7, 44.4, 24.7]`
- reconstructed mean / sample SD: `35.4` / `10.25`
- published level: `improving` `5.56`% / `35.4` vs `33.54`
- maturity: `ESTABLISHED_TREND` trend_allowed=`True`
- spread n/mean/sample SD: `7` / `35.4` / `10.25`
- min/max/range: `24.7` / `48.9` / `24.2`
- baseline SD / spread ratio: `3.94` / `2.61`
- observation/comparison allowed: `True` / `True`
- HRV insight_candidate / recommendation_candidate: `False` / `False`
- review insight_worthy / primary_metrics: `True` / ['exercise_minutes', 'workout_count', 'sleep_duration_hours', 'steps']
- sleep remains the level story: `decreasing` `-10.58`% insight_candidate=`True`

### Deterministic answers

1. Is average HRV called declining? **No** — published direction is `improving`.
2. Is increased day-to-day spread visible? **Yes** — sample SD `10.25` vs baseline SD `3.94` (ratio `2.61`), range `24.7`–`48.9`.
3. Was an independent insight/recommendation minted from spread? **No** — HRV is not insight_candidate, not recommendation_candidate, and not in primary_metrics.

## Negative controls

### Stable mean + normal spread

- direction: `stable`
- spread_ratio: `1.09`
- comparison allowed: `True`
- insight_candidate: `False`

### B1 2026-06-18 (stable period regression)

- insight_worthy: `False`
- HRV spread_ratio: `1.47`
- HRV insight_candidate: `False`

### Immature baseline

- maturity: `EARLY_PATTERN`
- trend_allowed: `False`
- comparison allowed: `False`
- spread_ratio: `None`

### Partial coverage

- current observations: `4/7`
- partial_coverage: `True`
- comparison allowed: `False`
- spread_ratio: `None`

### Near-zero baseline SD

- baseline SD: `0.0`
- comparison allowed: `False`
- spread_ratio: `None`

### One extreme outlier

- min/max/range: `33.0` / `55.0` / `22.0`
- direction: `improving`
- recommendation_candidate: `True` (F4.6 level effect from the pulled mean; spread added no band or insight reason)

### Episodic VO2 excluded

- C4 VO2 within_window_spread: `None`

### Respiratory-rate control unaffected

- C4 RR within_window_spread: `None`
- C4 RR control_metric / insight_candidate: `True` / `False`
- B1 RR insight_candidate: `False`

## TRACE

F4.2 `model_calls[]` extract `within_window_spread` from `get_trend_signals` with
`origin=deterministic_spread_analytics`. Visible fields include n, mean, sample SD,
min/max/range, baseline SD, ratio, both allow-flags, direction, maturity, and
coverage/provenance needed to reconstruct the comparison. No hidden CoT.
