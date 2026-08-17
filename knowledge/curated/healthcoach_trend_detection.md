---
doc_id: L2-TD-001
title: Trend Detection & Signal Processing — Baselines, Thresholds, Changepoints and Data Hygiene
layer: L2
domain: analytics
metrics: [rhr, hrv_sdnn, hrr_1min, vo2max, resp_rate, sleep_total, sleep_efficiency, sleep_consistency, bedtime_var, steps, workout_freq, training_load, weight, active_kcal]
entities: [baseline, rolling_average, z_score, changepoint, plateau, regression, seasonality, missingness, autocorrelation]
evidence_grade: A
verification_status: verified
retrieval_hints:
  - "is this change meaningful or just noise"
  - "how much has my resting heart rate really changed"
  - "what counts as a trend"
last_reviewed: 2026-08-07
sources: [ISO-statistical-methods, Shaffer-2017]
---

# Trend Detection & Signal Processing

This document defines the statistical primitives every L2 rule and every chart in
the application depends on. It is deliberately upstream of the correlation and
rule documents: if the baseline and noise model are wrong, everything built on
top produces confident nonsense at scale.

The governing principle from `00-CORPUS-SPEC §5` applies throughout: population
ranges screen, personal baselines coach.

---

## The core problem: these series are noisy, sparse, autocorrelated and non-stationary

Consumer wearable time series violate nearly every assumption of naive
statistics simultaneously:

- **Noisy.** Day-to-day HRV commonly swings ±20–30% around a stable baseline
  with no underlying change. RHR carries several bpm of measurement variance.
- **Sparse and irregular.** The watch is not worn every night. HRV is sampled
  opportunistically. VO₂max updates only on qualifying outdoor workouts.
- **Autocorrelated.** Today's value is strongly predicted by yesterday's.
  Effective sample size is far below the number of observations, which means
  standard significance tests will overstate confidence badly.
- **Non-stationary.** The baseline itself legitimately moves — that is the thing
  being measured. A method that assumes a fixed mean cannot distinguish
  adaptation from drift.
- **Missing not at random.** This is the one most systems get wrong. The watch
  comes off during illness, after heavy drinking, during travel, and during
  periods of low motivation. **Missingness correlates with exactly the states
  worth detecting.** Treat gaps as informative: a sudden drop in wear compliance
  is itself a signal, and complete-case analysis systematically underestimates
  bad periods.

Every method below is chosen to survive these conditions rather than to be
statistically elegant.

---

## Baseline construction

### Windows
Three baselines are maintained per metric:

| Baseline | Window | Purpose |
|---|---|---|
| Short | 7-day rolling | Current state |
| Medium | 30-day rolling | Trend reference |
| Long | 60–90-day rolling | Stability reference and z-score denominator |

Rules compare short-vs-long, never point-vs-point. A "today vs baseline"
comparison is only used for same-day acute attribution (alcohol, travel) where
temporal proximity carries the evidential weight.

### Robust statistics, not mean and SD
Use **median and MAD-derived scale** rather than mean and standard deviation.
Wearable series contain artifacts — a 200 bpm reading from a loose watch, a
14-hour "sleep" from a forgotten wear session. A single artifact shifts a mean
and inflates an SD enough to suppress genuine detections for weeks.

```
robust_z = 0.6745 * (x - median_60d) / MAD_60d
```

The 0.6745 constant scales MAD to be comparable to a standard deviation under
normality, so existing z-thresholds carry over.

### Cleaned vs raw baselines
Maintain both. The **cleaned** baseline excludes flagged windows:

- `illness_active` days plus 3 days after
- days with `travel_tz_delta ≥ 3` plus 2 days after
- nights following `alcohol_units ≥ 3`
- physiologically implausible values (per-metric bounds)
- days with wear time below the metric's minimum density

Detection uses cleaned. Reporting to the user uses raw, so charts match what
they actually lived. Never let a bad fortnight silently redefine "normal" — that
is how a system stops noticing a six-month decline.

### Cold start
Per spec: <14 days descriptive only · 14–30 days low-confidence trends with the
limitation stated · 30–60 days normal operation, no seasonal claims · 60+ days
full · 12+ months seasonal comparison unlocked. Where a baseline is short,
widen thresholds rather than lowering them — an immature baseline has an
underestimated variance and will over-fire.

---

## Detecting change

### 1. Rolling-mean crossover (the workhorse)
Signal when the 7-day robust mean crosses the 60-day robust mean by more than
`k` robust SDs and holds for `d` days. Defaults: `k = 1.0`, `d = 2` for acute
rules; `k = 0.75`, `d = 7` for chronic rules. Simple, interpretable, and it maps
directly onto a chart the user can see.

### 2. Theil–Sen slope + Mann–Kendall test (for "is this actually trending")
For claims like "your RHR has been declining for three months," fit a
**Theil–Sen** slope (median of all pairwise slopes) and test monotonicity with
**Mann–Kendall**. Both are non-parametric, robust to outliers, tolerate missing
values, and make no normality assumption. Report the slope in native units per
30 days — "−1.8 bpm per month" is a statement a user can act on; "p = 0.03" is
not.

**Correct for autocorrelation.** Apply a variance correction or use a
block bootstrap; the standard Mann–Kendall variance assumes independence and
will produce significant trends from pure random walks in daily physiological
data. This single correction removes a large fraction of spurious "trends."

### 3. EWMA control chart (for early warning)
An exponentially weighted moving average with λ ≈ 0.2 and control limits at ±3σ
of the cleaned baseline detects small sustained shifts earlier than a rolling
mean. Best suited to `resp_rate` and `rhr`, which are low-variance and where
early detection has real value.

### 4. Changepoint detection (for "when did this start")
Use an offline changepoint method (PELT with an L2 cost, or Bayesian online
changepoint detection for streaming) to locate the date a level shift began.
This is what lets the coach say *"this started around March 14"* — which is
enormously more useful than *"this is trending"*, because it lets the user
connect the change to something they remember. Require a minimum segment length
of 14 days and a penalty tuned so that a typical user gets no more than 3–4
changepoints per metric per year.

### 5. Plateau detection
A plateau is the **absence** of trend where a trend was previously present, not
merely the absence of trend. Fire only when:
- a prior significant Theil–Sen slope existed in the preceding 90 days, AND
- the current 84-day slope confidence interval contains zero, AND
- the equivalent minimum detectable effect is smaller than the change the user
  is trying to achieve.

That last condition matters: declaring a plateau when the data could not have
detected the improvement anyway is a measurement failure being reported as a
physiological one.

---

## Minimum detectable effect

Before any rule ships, compute what it can actually see. For a metric with
robust SD `σ`, comparing an `n₁`-day window to an `n₂`-day window, the smallest
reliably detectable difference is approximately:

```
MDE ≈ 2.8 * σ * sqrt(1/n₁ + 1/n₂) * sqrt(ESS_correction)
```

where the ESS correction inflates for autocorrelation (for daily physiological
data with lag-1 autocorrelation ρ, roughly `(1+ρ)/(1−ρ)`).

Practical consequences to encode:
- **HRV** has a large σ relative to plausible effects. Weekly comparisons are
  near-useless; 30-day windows are the practical floor for most users.
- **VO₂max** updates too sparsely for anything under 90 days.
- **Sleeping respiratory rate** has a very small σ, so 7-day windows detect
  meaningful shifts — this is why it punches above its weight for illness onset.
- **Weight** has high day-to-day fluid noise but a stable trend; use a 14-day
  window minimum and never comment on a single-day change.

If a rule's MDE exceeds the effect size in the literature it is meant to detect,
the rule does not ship. Write that check into the build.

---

## Multiple comparisons — the quiet correctness problem

With ~40 metrics, exhaustive pairwise correlation gives ~780 tests. At α = 0.05
that is roughly 39 false discoveries by construction, and a coach that surfaces
them will look insightful and be wrong. Three defenses, applied together:

1. **Pre-registered relationship whitelist.** Only test relationships that exist
   in the `L2-CR` registry with a documented biological mechanism. This is the
   primary defense and it reduces the test count by more than an order of
   magnitude.
2. **Benjamini–Hochberg FDR control** at q = 0.10 across the tests actually run
   in a given analysis pass.
3. **Effect-size floor.** Statistical significance is not the bar; a
   within-person correlation must also exceed a practical threshold (|r| ≥ 0.3
   as a default) before it is ever surfaced.

Never run open-ended correlation mining and report what comes back. That is a
false-discovery generator with a friendly interface.

---

## Confounder structures the analytics must handle

### Day-of-week effects
Sleep, alcohol, and activity are strongly weekly-periodic for most users. Before
testing any trend, either include day-of-week as a covariate or compare
week-aligned windows (multiples of 7 days). A 5-day window comparison silently
encodes a weekday/weekend difference as a trend.

### Time-of-day sampling in HRV
Apple's HRV samples are opportunistic and time-of-day confounded. Normalize by
comparing within sampling-hour bands, weight by sample count per day, and
require a minimum of 2 samples/day for the day to count. A week where the user
did daily Breathe sessions is not comparable to one where they did not.

### Seasonality
Requires 12+ months. Real and documented: activity and step counts vary
seasonally; sleep duration and timing shift with photoperiod; RHR is influenced
by ambient temperature. Before attributing a summer RHR rise to deconditioning,
check whether the same pattern appeared in prior years. Evidence: B.

### Regression to the mean
Any rule triggered by an extreme value will see improvement afterward regardless
of intervention. When the coach recommends an action after an extreme reading
and the next reading is better, it must **not** claim the action worked. This is
the most common way a wellness product accumulates false confidence in its own
advice. Attribution of improvement requires a sustained shift in the baseline,
not a return from an extreme.

### Wear-time and compliance drift
Track wear-time as a first-class series. A "improving sleep consistency" signal
that is actually declining wear compliance on irregular nights is a real and
common artifact.

---

## Trend vocabulary — mapping statistics to language

Consistency here is what makes the product feel trustworthy over months.

| Statistical state | Permitted phrasing | Never |
|---|---|---|
| Significant Theil–Sen slope, 90+ days, autocorr-corrected | "has been steadily declining/improving" | "is plummeting" |
| 7d/60d crossover ≥1 robust SD, held 2+ days | "is currently below your usual range" | "is dangerously low" |
| Changepoint located | "this shift appears to start around {date}" | "on {date} you caused" |
| CI contains zero after prior trend | "progress has levelled off" | "you've stopped improving" |
| Below MDE | *emit nothing* | any trend claim |
| <14 days data | "here's what your data shows so far" | any trend claim |

Absence of a detected trend is reported as *"nothing meaningful has changed,"*
never as silence — users read silence as the app being broken, and read
"nothing changed" as the app being honest.

---

## Analysis cadence

- **Daily:** acute rules (illness composite, alcohol attribution, travel).
  Latency matters; these are only useful same-day.
- **Weekly:** rolling crossovers, habit adherence, digest generation.
- **Monthly:** Theil–Sen trend refresh, changepoint scan, plateau evaluation,
  correlation registry update.
- **Quarterly:** baseline recomputation, seasonality check, rule firing-rate
  audit.

**Firing-rate audit is mandatory.** Target 2–3 surfaced insights per user per
week. Backtest the full rule set against historical exports before each release.
A rule base that fires fifteen times a week is not sensitive; it is broken, and
users will disable notifications rather than complain.
