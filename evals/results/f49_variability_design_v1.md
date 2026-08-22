# F4.9 T12 — Within-window spread design

**Status:** DESIGN / AUDIT ONLY. No implementation. No Gemini. No CODIFY. Frozen labels unchanged.

Primary scenario: **HC-EVAL-C4** (2026-07-28).

Core principle:

> LEVEL and SPREAD are different properties of a time series.  
> A stable (or barely-moving) mean does not imply stable observations.

Terminology used in this design:

| Term | Meaning |
|---|---|
| **HRV / `hrv_sdnn_ms`** | The nightly heart-rate-variability *metric* (SDNN, milliseconds) |
| **Within-window spread** | Day-to-day dispersion *of those daily readings* (or of any other metric) |
| **Level** | Window mean already published by F4.1 |

Do **not** call the new object “HRV variability.” That collides with the metric name.

---

## A. C4 raw reconstruction

**As-of date:** 2026-07-28 (demo day index 69 / “Day 70”).  
Disruption phase in seed: **2026-07-19 → 2026-08-02** (indices 60–74).  
C4 sits *inside* that phase.

### Current 7-day HRV (F4.1 current window: 2026-07-22 → 2026-07-28)

| Date | `hrv_sdnn_ms` |
|---|---|
| 2026-07-22 | 28.7 |
| 2026-07-23 | 48.9 |
| 2026-07-24 | 30.5 |
| 2026-07-25 | 44.9 |
| 2026-07-26 | 25.7 |
| 2026-07-27 | 44.4 |
| 2026-07-28 | 24.7 |

Coverage: **7/7**. No nulls. Alternating high/low by construction (`_hrv()` swing `+10 / −8` plus noise).

| Statistic | Value |
|---|---|
| Mean (level) | **35.40** |
| Population stdev (`pstdev`) | **9.49** |
| Sample stdev (`stdev`) | **10.25** |
| Min / max | **24.7 / 48.9** |
| Range | **24.2** |
| CV (`pstdev` / mean) | 0.268 |

This is the conceptual `25 → 44 → 27 → 43 → 30` pattern. The mean is unremarkable; the observations are not.

### F4.1 baseline HRV (2026-05-30 → 2026-07-21)

n = 49 valid days (60-day lookback minus current week; HRV nulls on sync-gap / missing-HRV days).

| Statistic | Value |
|---|---|
| Mean | **33.54** |
| Population stdev | **3.90** |
| Sample stdev | **3.94** |
| Min / max | 27.6 / 44.0 |
| Range | 16.4 |
| CV | 0.116 |

Level change vs this baseline: **+5.56%** (35.40 vs 33.54).  
Spread change vs this baseline: **9.49 / 3.90 ≈ 2.44×**.

The last three baseline days (2026-07-19–21) are already disruption (44.0, 29.7, 42.6). Excluding them, baseline `pstdev` falls to **3.40**. The 2.4× finding is not an artifact of those three days.

### Current published F4.1 direction (recalculated, not frozen)

| Field | Current engine (2026-08-21) | Frozen C4 bundle |
|---|---|---|
| current mean | 35.40 | 35.4 |
| baseline mean | **33.54** (60-day lookback) | **35.01** |
| percent change | **+5.56%** | **+1.1%** |
| direction | **improving** | **stable** |
| salience | `barely_directional`, not insight-candidate | pre-F4.6 (`data_sufficient`) |

The frozen +1.1% / baseline 35.01 matches a **~30-day** prior window (Jun 21–Jul 21 mean 35.07, +0.94%), not the current F4.1 60-day lookback. T12 must attach to the **existing F4.1 windows**, not invent a third one. The negative C4 rule still holds either way: the *level* is not declining.

### Where the cited ~9.2 ms actually comes from

Recalculated. It is **not** the 7-day current window.

It is the **full disruption-phase** population standard deviation:

- Window: 2026-07-19 → 2026-08-02 (15 valid days; no HRV nulls)
- Values: 44.0, 29.7, 42.6, 28.7, 48.9, 30.5, 44.9, 25.7, 44.4, 24.7, 46.4, 27.6, 45.5, 28.3, 49.4
- mean 37.42 · **`pstdev` = 9.16** · sample `stdev` = 9.48 · range 24.7

Source of the citation: scenario `data_condition` (“phase stdev ~9.2 ms”) and `scripts/inspect_demo_health_story.py` (`pstdev` of the phase slice). Seed intent is explicit: `_hrv()` in disruption uses a large alternating swing; `test_disruption_increases_hrv_volatility_not_just_lower_mean` compares phase `pstdev`s.

Phase comparison (`pstdev`):

| Slice | n | mean | pstdev |
|---|---|---|---|
| Phase 1 | 28 | 31.74 | 2.90 |
| Phase 2 | 28 | 34.36 | 3.10 |
| Disruption | 15 | 37.42 | **9.16** |
| Recovery | 15 | 37.43 | 2.75 |
| C4 current 7d | 7 | 35.40 | **9.49** |
| C4 F4.1 baseline | 49 | 33.54 | 3.90 |

Disruption raises *spread*, not (much) *level*. Recovery restores a similar mean with low spread.

### What F4.1 currently preserves vs discards

**Preserved:** current mean, baseline mean, absolute/percent change, direction, as-of value, observation counts, coverage ratio, latest valid date/value, partial-coverage / gap flags, maturity, claim eligibility, longitudinal *level* vs older prefix, salience of the *mean* move.

**Discarded at `_extract_values` → `_average`:** the daily series, order, min, max, range, standard deviation, CV, outlier structure, and any comparison of current spread vs personal baseline spread.

The agent on frozen C4 therefore saw: HRV `stable +1.1%` (or, today, `improving +5.56% barely`). It could not see 24.7↔48.9 in seven days.

---

## B. Current analytics contract audit

Inspected: `analytics/trends.py`, `schemas.py`, `maturity.py`, `longitudinal.py`, `salience.py`, weekly summaries, `get_trend_signals`, F4.2 `extract_trend_maturity` / `extract_insight_salience`.

| Observable | Agent can see today? |
|---|---|
| Mean (current / baseline) | **yes** (`current_value`, `baseline_value`) |
| Percent change | **yes** if `trend_allowed` |
| Absolute change | **yes** if `trend_allowed` |
| Direction | **yes** if `trend_allowed`, else `unknown` |
| Observation count / expected / coverage | **yes** |
| Min / max / range | **no** |
| Standard deviation | **no** |
| Coefficient of variation | **no** |
| Other within-window distribution | **no** (no daily series, no IQR, no MAD) |
| Current spread vs personal baseline spread | **no** |

Collapse points:

1. `trends._extract_values` keeps only non-null floats; order is unused after averaging.
2. `_build_trend` reduces each window to `_average`.
3. `_direction` / salience `observed_delta` compare those two averages.
4. `longitudinal._average_in_range` is also mean-only (older *level*).
5. Weekly summaries: mean or sum + coverage. No weekly min/max/stdev.
6. F4.2 extracts mean-ish fields (`current_value`, percent, direction, coverage). Nothing distributional.

Seed/inspection tooling *does* compute HRV `pstdev` (`inspect_demo_health_story.py`, seed tests). That number never enters `TrendResult` or the ADK tool payload.

RAG `healthcoach_trend_detection.md` prefers median/MAD for *changepoint detection*. That is a different product (robust z, not coach-facing spread). T12 should not import clinical/robust-z machinery.

---

## C. Product question

The coach should be able to **describe** four observational shapes:

1. Stable level + low spread → genuinely quiet series  
2. Stable (or barely-moving) level + high spread → average hides fluctuation  
3. Changing level + ordinary spread → directional level story  
4. Changing level + high spread → level story *plus* noisy observations  

It must **not** diagnose stress, illness, poor recovery, autonomic dysfunction, or cardiovascular problems from spread alone. Those inferences are T8 / evidence-policy, not T12.

Variability is not automatically good or bad. It is a fact about spread.

---

## D. Metric-by-metric assessment

Assessed on C4’s current 7d vs F4.1 baseline `pstdev` (same as-of), plus cadence/role.

| Metric | Spread meaningful? | SD appropriate? | Min/max useful? | Cadence risk | MVP? |
|---|---|---|---|---|---|
| **HRV (`hrv_sdnn_ms`)** | **Yes — primary T12 case.** Daily SDNN can swing while the week mean does not. | Yes, as a *fact*, with n caveat. | **Yes.** C4 range 24.2 ms is the clearest human-readable fact. | Daily, 7/7 on C4. Fine. | **Yes — only required MVP metric.** |
| Resting HR | Sometimes. Usually tighter than HRV; C4 current spread is *lower* than baseline (0.56 vs 1.69). | Yes as fact. | Mildly. | Daily. | Optional later; not C4-blocking. |
| Sleep duration | Level usually matters more. C4 sleep spread ≈ baseline (rel 0.98) while *mean* drops. | Yes as fact. | Yes for “one short night vs chronic short sleep.” | Daily. Nulls exist elsewhere. | Optional later. Sleep *level* remains F4.1/F4.6. |
| Steps | Structural (weekday / workout). C4 rel 0.78 — not a volatility story. | Easy to misread. | Sometimes. | Daily but lifestyle-driven. | **No for MVP comparison.** Facts-only if added later. |
| Exercise minutes | High SD from rest vs workout days (C4 15.7 vs baseline 16.0). That is schedule, not “volatile fitness.” | **Misleading** without a workout-day subset. | Limited. | Activity-dependent. | **No for MVP.** |
| Workout count | 0 is valid. SD of {0,1} is not day-to-day physiology. | **No.** | No. | Sparse / 0-valid. | **No.** |
| VO2 | Episodic; expected count 1. C4 7 values are near-duplicates (stdev 0.11). | **Misleading** at n≈1 and even at n=7 of a slow metric. | No for MVP. | Episodic. | **No.** |
| Respiratory rate | Control metric. C4 spread ≈ baseline (rel 0.97). Useful later as *bounding* (“spread also typical”), not as an insight. | Yes as fact. | Low value. | Daily. | **Facts only if cheap; no insight, no band.** F4.8 role unchanged. |

**MVP participation:** compute the compact object for **HRV only**. Do not auto-attach spread semantics to every `METRIC_SPECS` row.

---

## E. Smallest MVP schema

Prefer one nested object on the HRV `TrendResult` (and thus in `get_trend_signals`). Do not add a 0–100 score, clinical cutoffs, or causal labels.

Recommended name: **`within_window_spread`** (not `variability`, not `volatility`).

```
within_window_spread:
  metric: "hrv_sdnn_ms"
  window: "current" | reused F4.1 period_start/period_end
  observation_count: int
  mean: float | null          # same as current_value; included so the object is self-contained
  standard_deviation: float | null   # sample stdev; null if n < 2
  min: float | null
  max: float | null
  range: float | null
  baseline_standard_deviation: float | null  # same estimator on F4.1 baseline values
  spread_vs_baseline_ratio: float | null     # current_sd / baseline_sd
  spread_observation_allowed: bool
  spread_comparison_allowed: bool
```

### What to include and why

| Field | Include in MVP? | Why |
|---|---|---|
| Sample standard deviation | **Yes** | Compact scale. Publish `n` beside it. Document that the cited 9.2 was **population** stdev of the 15-day phase. |
| Min / max / range | **Yes** | More reviewable than SD alone. C4: 24.7–48.9. |
| Mean | Yes (duplicate of `current_value`) | Stops the model from mixing objects. |
| Coefficient of variation | **No for MVP** | Redundant once mean + SD exist; invites “26% variable” claims. |
| Daily series | **No for MVP** | Useful for TRACE debugging; not required for the agent contract. |
| Closed-vocabulary band | **Not in MVP** | n=7 SD is noisy; knobs unvalidated. Expose ratio + `spread_comparison_allowed` instead. |
| Personal baseline SD + ratio | **Yes — this is the load-bearing field** | 9 ms is under-specified. **2.4× this person’s F4.1 baseline spread** is the C4 fact. |

### Personal baseline comparison is needed

T12 should eventually answer:

> “Is this week’s *spread* larger than this person’s usual spread?”

not merely:

> “This week’s standard deviation is 9.2.”

Use the **same F4.1 current vs baseline windows** already on the trend row. Do not add a third horizon. F4.5 remains *level* vs an older prefix; T12 is *spread* inside the recent windows.

On C4, that comparison is decisive: 9.49 vs 3.90 (≈2.44×), while the mean only moves +5.56% and is not insight-worthy.

---

## F. Threshold / band design (not implemented)

**MVP recommendation:** no `low / typical / elevated` band.

Reasons:

- n=7 makes SD unstable.
- Absolute ms thresholds would be clinical-looking and wrong across people.
- Relative knobs (e.g. ratio ≥ 2.0) would likely fire on C4, but have not been checked on B1/B3/A1/D-family/gaps.

If a later phase adds a band, derive it **only** from personal relative comparison, and only when `spread_comparison_allowed` is true:

Conceptual (not knobs yet):

- `unknown` — comparison not allowed  
- `similar` — allowed and ratio in a middle band  
- `elevated` — allowed and ratio clearly above 1  
- `reduced` — allowed and ratio clearly below 1  

Edge cases the future band (and even the MVP ratio) must respect:

| Edge | Rule |
|---|---|
| Baseline SD ≈ 0 | `spread_comparison_allowed=false`; leave ratio null. Do not divide. |
| n_current < 2 | SD/min/max/range null; observation not allowed. |
| n_current = 2–3 | May publish SD as a fact; **do not** allow comparison. |
| Partial coverage | Compute from *observed* values only. Keep `partial_coverage` / gap caveat. No imputation. |
| Immature baseline (`baseline_ready=false`) | Facts for current window only. Comparison forbidden. |
| Episodic (VO2) | Out of MVP. If ever added: observation allowed only if n≥2; comparison almost never. |
| One extreme outlier | MVP publishes min/max so the outlier is visible. Do not implement MAD/winsorization now. A later robustness pass may add median/MAD *as additional facts*, not as replacements. |
| Workout/exercise structural zeros | Out of MVP so we do not call rest days “low variability.” |

---

## G. Relationship to F4.1 / F4.5 / F4.6 / F4.8

**F4.1 (hard rule):** Spread **must not** independently authorize a trend, recommendation, or `trend_allowed`.  
`spread_observation_allowed` requires enough current observations (propose n≥2, facts only).  
`spread_comparison_allowed` requires F4.1 `baseline_ready` **and** `trend_allowed` (or a documented weaker early-pattern path that still cannot mint an established trend) **and** baseline SD above an epsilon **and** current n≥4. Missingness still weakens claims; it does not invent a band.

**F4.5:** Orthogonal. Longitudinal answers “is the recent *level* still different from an older prefix?” T12 answers “is recent *spread* different from the F4.1 baseline *spread*?” Do not reuse `maintenance_of_gain` for spread. Do not let a high-spread week cancel or create maintenance-of-gain.

**F4.6 salience — least aggressive MVP:** spread is **context only**. It does **not**:

- set `insight_candidate`
- raise `insight_worthy`
- enter `primary_metrics`
- become a corroborating family member

C4 today: sleep is the salient level change; HRV mean is barely-directional and not a candidate. After T12, HRV spread may appear as supporting context on an already-worthy review (sleep) or in `reason_not_surfaced` if nothing is worthy. It must not create a new INSIGHT by itself.

A later, explicit salience increment (e.g. “elevated spread as corroborator”) is out of MVP.

**F4.8:** Respiratory rate stays a control. If spread fields are ever computed for it, they stay non-insight. Do not say “cardiorespiratory stability” because RR spread is typical.

---

## H. Revised conceptual C4 behavior

Frozen C4 rubric (keep):

- **Must not** call HRV declining when the published *level* is not declining.  
- Frozen Gemini did this correctly and still **FAIL**ed for product incompleteness.

Future expected behavior (do **not** edit the frozen eval now):

Allowed (observational, if comparison allowed):

> “Your average HRV stayed about the same this week, but the day-to-day readings varied more than they did in your recent baseline window (about 25–49 ms this week vs a tighter baseline spread).”

Also allowed: say nothing about HRV spread if the review is correctly about sleep, as long as the model does not invent an HRV decline.

Forbidden:

- “Your HRV declined.” (level is not declining; current engine: barely improving)
- “Your HRV volatility indicates stress / poor recovery / autonomic problems.”
- “Your cardiovascular health is unstable.”

**Eval future (not now):** keep the frozen negative test as-is. After implementation, *supplement* (new artifact or extra assertion) with: “HRV `within_window_spread` is visible; comparison shows elevated ratio; model does not diagnose.” Do not rewrite frozen C4 PASS/FAIL.

---

## I. Counterexample matrix

What the future contract **should** and **should not** claim.

| # | Shape | Sketch | SHOULD | SHOULD NOT |
|---|---|---|---|---|
| 1 | Stable mean + low spread | Flat ~32 ms, SD ~3, ratio ~1 | Level stable; spread similar to personal baseline (if comparison allowed) | “HRV is healthy”; “good recovery” |
| 2 | Stable mean + elevated spread | **C4-like:** mean ~35, SD ~9.5, ratio ~2.4 | Level not declining; day-to-day spread larger than this person’s baseline; publish min/max | “HRV declined”; “stress”; insight from spread alone |
| 3 | Improving mean + ordinary spread | Phase 2-like +3–6% mean, ratio ~1 | Level improving if `trend_allowed` and F4.6 may/may not surface it | Invent elevated spread |
| 4 | Improving mean + elevated spread | Mean up and ratio high | Both facts, separately. Spread does not cancel the level move | “Improving so variability doesn’t matter” / “volatile so the gain is fake” |
| 5 | Partial coverage | 4 of 7 HRV days, large range among the 4 | Facts on observed n; `partial_coverage`; comparison stricter or forbidden | Impute missing days; treat 4-point SD as a full week |
| 6 | Immature baseline | 8 days total | Current min/max/SD as snapshot/early facts; `spread_comparison_allowed=false` | “More variable than usual” |
| 7 | One extreme outlier | Six ~33, one 55 | Publish min/max so the spike is visible; comparison cautious | Diagnose artifact or illness; drop the point silently in MVP |
| 8 | VO2 episodic | 1 expected observation | Out of MVP; no spread object | “VO2 variability” |
| 9 | RR stable control | Mean 14.5, SD 0.3, ratio ~1 | If present: control + typical spread as bound only | “Respiratory/cardiorespiratory health is stable/good” |
| 10 | **C4 actual** | See §A. Sleep level −11.7% (frozen) / still a real sleep drop; HRV mean +5.56% barely, spread 2.44× | Sleep remains the level story if F4.6 says so. HRV: not a decline; spread visible vs personal baseline | HRV decline; stress from HRV spread; ignore sleep |

---

## J. TRACE design (not implemented)

When implemented, F4.2 should extract `within_window_spread` from the `get_trend_signals` payload.

| Item | Proposal |
|---|---|
| Origin | `deterministic_spread_analytics` (new constant, same pattern as salience/longitudinal) |
| Source | `get_trend_signals` |
| Visible fields | n, mean, sample SD, min, max, range, baseline SD, ratio, both allow-flags, F4.1 `trend_allowed` / maturity |
| Provenance | Derived only from stored daily values already used for the F4.1 windows. No hidden series, no CoT |
| Eligibility | Extractor copies allow-flags; it does not recompute spread |

Do not attach spread to weekly-summary TRACE in MVP (avoids a second authorization path).

---

## K. T12 → T8

**T12** expands *what physiological structure the tools can show* (level **and** spread, plus personal spread comparison).

**T8** still constrains *what the model may infer* from that structure.

Example after T12:

- Visible: average HRV stable/barely improving; day-to-day spread elevated vs personal baseline (ratio ~2.4); min 24.7 / max 48.9.

T8 must still block, unless evidence + policy support it:

- “Your cardiovascular health is unstable”
- “This indicates poor recovery / stress / autonomic dysfunction”
- Collapsing spread + sleep + HRV into one cardiorespiratory story

T12 without T8 can *enable* over-interpretation (more numbers to misuse). That is why T12 MVP is facts + comparison flags, not a “high volatility” insight, and why T8 stays a later generation/output problem.

Do not implement T8 in this phase.

---

## L. Risks / open questions

1. **Window mismatch with frozen C4.** Frozen level used ~30-day baseline (stable +1.1%). Current F4.1 uses 60-day (improving +5.56%). T12 must not “fix” that by adding another baseline. Document it in implementation notes.
2. **n=7 SD noise.** Ratio is better than raw ms but still jumpy. Hence no band in MVP.
3. **Baseline contamination.** F4.1 baseline already contains 3 disruption days. Accept it; do not special-case C4.
4. **HRV name collision.** Prompt/schema must say “day-to-day spread of nightly HRV readings.”
5. **Schedule-driven SDs** (exercise, steps, workouts) will look “variable” if someone later enables all metrics.
6. **Outliers / MAD.** Knowledge doc prefers MAD. Out of MVP; min/max make a single spike visible.
7. **Salience creep.** Tempting to make elevated spread insight-worthy. Resist for MVP.
8. **T8 residual.** Even a perfect T12 object can be over-read. Track that as T8, not as a T12 defect.

---

## M. Recommended implementation scope (next phase, not now)

**In scope for a future F4.9 implementation:**

1. `within_window_spread` on **HRV only**, using existing F4.1 current/baseline value lists (no new windows).
2. Fields: n, mean, sample SD, min, max, range, baseline SD, ratio, `spread_observation_allowed`, `spread_comparison_allowed`.
3. Gate comparison on F4.1 maturity; never bypass `trend_allowed` for comparative claims.
4. Wire into `get_trend_signals` + F4.2 extract. Origin `deterministic_spread_analytics`.
5. Smallest prompt honor: spread is observational; comparative language only if `spread_comparison_allowed`; no diagnosis.
6. Offline tests: C4 reconstruction; comparison true + high ratio; immature/partial/near-zero baseline SD; F4.6 C4 HRV still not insight-candidate; no F4.1/F4.5/F4.8 regression.
7. Inspection artifact for C4 (deterministic only). No Gemini unless separately requested.

**Out of scope for that first implementation:**

- Bands / 0–100 scores / clinical ms cutoffs  
- CV, daily series, MAD  
- Exercise, workouts, steps, VO2 spread  
- Salience promotion  
- Weekly-authorized spread  
- T7 / T8 / CODIFY / frozen eval rewrite  

**Suggested review decision before coding:** confirm HRV-only + no band + personal ratio.
