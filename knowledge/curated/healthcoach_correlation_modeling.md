---
doc_id: L2-CR-001
title: Correlation & Relationship Modeling — Registry, Lag Structure, Causal Discipline and Relationship Catalogue
layer: L2
domain: analytics
metrics: [hrv_sdnn, rhr, hrr_1min, vo2max, sleep_total, sleep_efficiency, sleep_deep, sleep_rem, sleep_consistency, workout_freq, workout_intensity, training_load, active_kcal, steps, weight, bmi, stress, mood, energy, alcohol_units, smoking, travel_tz_delta, illness, water_intake, diet_quality, caffeine_mg, cycle_phase, recovery_perception]
entities: [correlation, causation, mediation, confounding, lag, n_of_1, effect_size]
evidence_grade: B
verification_status: needs_verification
retrieval_hints:
  - "does alcohol affect my HRV"
  - "how does sleep affect my recovery"
  - "what is connected to what in my health data"
  - "why did my performance drop"
last_reviewed: 2026-08-07
sources: [Shaffer-2017, ACSM-GETP11, AHA-RHR, WHO-PA-2020]
---

# Correlation & Relationship Modeling

The highest-value and highest-risk document in the corpus. It is what lets the
coach say *"these two things move together, here is why, and here is how sure we
are"* — and it is where a careless implementation manufactures plausible,
confident, wrong stories.

Every relationship in the catalogue carries the same six fields you specified:
mechanism, direction, evidence strength, timeframe, confounders, and — the one
most often omitted — **the conditions under which the relationship does not
hold.** That last field does more work than the other five combined, because it
is what stops the agent from applying a population truth to a user it doesn't fit.

---

## 1. Relationship registry schema

Relationships are data, not prose. Each entry is a record the analytics layer
reads to decide what to test, at what lag, and how to talk about the result.

```json
{
  "rel_id": "REL-ALC-HRV-001",
  "exposure": "alcohol_units",
  "outcome": "hrv_sdnn",
  "direction": "negative",
  "mechanism_ref": "L1-LS-001#alcohol-autonomic-effects",
  "lag_days": { "min": 0, "max": 2, "peak": 0 },
  "dose_response": true,
  "population_evidence_grade": "B",
  "expected_effect_size": { "metric": "robust_z", "range": [-1.5, -0.5] },
  "confounders": ["late_meal", "poor_sleep", "evening_training", "illness"],
  "mediators": ["sleep_efficiency", "sleep_deep"],
  "non_applicability": [
    "rate_control_meds", "af_diagnosis", "very_low_dose_single_unit"
  ],
  "min_paired_observations": 20,
  "test_method": "within_person_paired_lagged",
  "personal_evidence": {
    "n_pairs": 0, "effect": null, "ci": null, "last_updated": null
  },
  "narrative_template": "NT-ATTRIB-LIFESTYLE"
}
```

**`personal_evidence` is the point of the whole design.** The registry ships with
population priors, then accumulates the individual user's own effect estimate.
Over months the coach shifts from *"alcohol typically suppresses HRV"* to
*"across 34 occasions, your HRV runs about 1.2 SD below baseline the night after
you drink — larger than typical."* The second statement is both more useful and
more defensible, and it is only reachable if the registry is a living data
structure rather than a static document.

---

## 2. Statistical method for within-person relationships

### Paired lagged comparison, not Pearson on raw series
Do not correlate two raw daily series. Both are autocorrelated and both trend;
the result is dominated by shared drift and produces large spurious correlations.
Instead:

1. **Detrend both series** (subtract the 60-day robust rolling median) so you are
   correlating deviations from baseline, not levels.
2. **Apply the registry's lag** — align exposure at day *t* with outcome at day
   *t + lag*. Lag is taken from the registry, i.e. from physiology, **not**
   selected as the maximum of the empirical cross-correlation function. Choosing
   the best-fitting lag from data and then reporting its significance is a
   garden-of-forking-paths error that will find relationships in noise.
3. **Compare exposed vs unexposed days** for binary exposures (alcohol, travel,
   illness) using a robust paired statistic; use Spearman on detrended deviations
   for continuous exposures.
4. **Require `min_paired_observations`** before reporting anything.
5. **Report effect size in personal SDs and native units**, with an interval.
   Never report a bare correlation coefficient to a user.

### Autocorrelation and effective sample size
Thirty consecutive days is not thirty independent observations. Correct the
interval using effective sample size or a block bootstrap with block length ≈
the series' decorrelation time (typically 3–7 days for HRV and RHR). Skipping
this produces intervals roughly half their true width.

### Simpson's paradox and stratification
Aggregate relationships can reverse within strata. The canonical case here:
across a training block, both training load and HRV rise together (fitness
adaptation), while *within* any given week, high load days are followed by
*lower* HRV (acute fatigue). Both are true. Reporting only the aggregate
produces "training raises HRV," which will be wrong on the exact day the user
asks. **Always stratify by timescale: acute (0–3 days), intermediate (1–4
weeks), chronic (3+ months).** Most exposure–outcome pairs in this domain have
different signs at different timescales, and this is the most common source of
incoherent coaching.

---

## 3. Causal discipline

### The mediation chains are the product
The lifestyle chains you sketched are mediation structures, and they should be
modeled as such rather than as direct links:

```
alcohol → sleep_efficiency ↓ → hrv_sdnn ↓ → next-day workout quality ↓
stress → sleep_total ↓, sleep_efficiency ↓ → rhr ↑ → recovery_perception ↓
travel_tz_delta → circadian misalignment → sleep timing + efficiency ↓ → hrv ↓
training_load ↑ → (acute) hrv ↓, rhr ↑ → (chronic, if recovery adequate) hrv ↑, rhr ↓, vo2max ↑
```

Modeling the mediator explicitly buys two things. First, better explanations —
*"the alcohol effect showed up through your sleep: efficiency dropped 9 points"*
is checkable by the user in a way that *"alcohol lowered your HRV"* is not.
Second, it identifies where intervention is possible: if the mediator is sleep,
then improving sleep on drinking nights is an actionable lever, whereas a direct
link offers only abstinence.

### Reverse causation is live in almost every pair
Poor sleep degrades next-day activity; low activity degrades that night's sleep.
Low mood reduces exercise; exercise improves mood. Illness reduces training;
overtraining raises illness risk. **Every bidirectional pair must be flagged in
the registry**, and narratives for flagged pairs use symmetric language
("these have been moving together") unless lag structure clearly separates them.

### Colliders
Do not condition on a variable that both exposure and outcome influence. The
practical instance: filtering analysis to "days the user recorded a workout"
conditions on a collider — both good recovery and high motivation drive workout
recording — and induces spurious associations. Analyze all days; treat
missingness as informative (`L2-TD §Missing not at random`).

### Permitted language, restated
`coincided with` · `is associated with` · `often precedes` · `is consistent
with`. At high runtime confidence with Grade A/B: `likely contributed to`.
Never `caused`. The L3 core enforces this; the registry's
`narrative_template` selects the register.

---

## 4. N-of-1 experiments — converting weak evidence into strong personal evidence

This is the most defensible personalization available, and it is what
distinguishes this product from a dashboard with an LLM attached.

When a registry entry has ≥20 paired observations, a low-to-moderate confidence
effect, and an exposure the user controls, propose a structured trial:

- **Design:** alternating 2-week blocks, minimum 3 blocks (ABAB or ABA), or
  randomized day-level assignment for exposures with short washout.
- **Pre-register** the outcome metric, the window, and the effect size that
  would count as meaningful — *before* the trial starts, stored in the registry.
  Deciding afterward what counted as success is how self-experiments become
  self-confirmation.
- **Respect washout.** Alcohol: 3 days. Caffeine timing: 3 days. Sleep extension:
  7 days. Training-load change: 14–21 days.
- **Power it honestly.** Use the MDE formula in `L2-TD` to state up front what
  the trial can and cannot detect. If it can't detect a plausible effect, say so
  and propose a longer design rather than running an uninformative one.
- **Report the null.** A trial showing no detectable effect is a genuinely
  useful result and must be delivered as one, not buried. Users who see nulls
  reported believe the positives.

---

## 5. Relationship catalogue

Direction is stated for the **acute** timescale unless noted. Ev = evidence
grade. "Fails when" is the non-applicability field.

### Recovery and autonomic

| Exposure → Outcome | Dir | Lag | Ev | Key confounders | Fails when |
|---|---|---|---|---|---|
| alcohol → hrv_sdnn | ↓ | 0–2 d | B | late meals, poor sleep, evening training | rate-control meds; AF; very low single-unit doses |
| alcohol → rhr | ↑ | 0–1 d | B | dehydration, heat, illness | as above |
| alcohol → sleep_efficiency, sleep_deep | ↓ | 0 d | B | late eating, screens, stress | tolerance masks subjective effect but not physiology |
| sleep_total ↓ → hrv_sdnn | ↓ | 0–1 d | B | stress, alcohol, training | single short nights in well-rested users |
| sleep_efficiency ↓ → rhr | ↑ | 0–1 d | B | heat, illness, caffeine | rate-control meds |
| stress ↑ → rhr, hrv | ↑ / ↓ | 0–2 d | B | sleep, alcohol, caffeine | self-report reliability varies by user |
| training_load ↑ → hrv (acute) | ↓ | 0–2 d | B | sleep, heat, hydration | low-intensity volume increases |
| training_load ↑ → hrv (chronic, adequate recovery) | ↑ | 8–12 wk | B | sleep, life stress | insufficient recovery inverts the sign |
| illness → resp_rate, rhr | ↑ | 0–2 d | B | heat, altitude, alcohol | asymptomatic infections may not show |
| travel_tz_delta ≥3 → hrv, sleep_efficiency | ↓ | 0–3 d | B | flight duration, sleep loss | short eastward hops in adapted travelers |
| dehydration → rhr | ↑ | 0 d | C | heat, activity | poorly measured; water_intake self-report is weak |

### Fitness and adaptation

| Exposure → Outcome | Dir | Lag | Ev | Key confounders | Fails when |
|---|---|---|---|---|---|
| workout_freq (aerobic) → rhr | ↓ | 6–12 wk | B | weight, sleep, alcohol | already highly trained (floor effect) |
| workout_freq (aerobic) → vo2max | ↑ | 8–12 wk | B | weight change, estimation error | insufficient intensity; monotonous training |
| aerobic training → hrr_1min | ↑ | 4–8 wk | B | cool-down behavior, heat | rate-control meds invalidate |
| high-intensity intervals → vo2max | ↑ | 6–10 wk | B | total volume, recovery | inadequate recovery between sessions |
| weight ↓ → vo2max (per kg) | ↑ | immediate | A | — | it is arithmetic, not fitness — must be disclosed |
| detraining → rhr, vo2max | ↑ / ↓ | 2–4 wk | B | illness, seasonality | brief tapers improve rather than degrade |
| steps ↑ → active_kcal, weight | ↑ / ↓ | 4–12 wk | B | compensatory intake, NEAT reduction | intake compensation commonly nullifies it |

### Sleep and behavior

| Exposure → Outcome | Dir | Lag | Ev | Key confounders | Fails when |
|---|---|---|---|---|---|
| sleep_consistency ↑ → hrv, rhr | ↑ / ↓ | 3–8 wk | B | total duration, alcohol | shift work; irregular caregiving schedules |
| caffeine (late) → sleep_efficiency | ↓ | 0 d | B | dose, tolerance, genetics | fast metabolizers; wide individual variation |
| evening high-intensity training → sleep_efficiency, hrv | ↓ | 0 d | C | timing, individual variation | many users show no effect — test individually |
| bedtime_var ↓ → sleep_total | ↑ | 2–4 wk | B | work schedule | fixed external constraints |
| morning light exposure → sleep timing | advances | 1–2 wk | B | season, latitude | not directly measurable from Apple Health |

### Body, nutrition and cycle

| Exposure → Outcome | Dir | Lag | Ev | Key confounders | Fails when |
|---|---|---|---|---|---|
| energy deficit → hrv, rhr, recovery_perception | ↓ / ↑ / ↓ | 2–6 wk | B | training load, sleep | **gated entirely under `eating_disorder_risk`** |
| diet_quality ↑ → energy, recovery_perception | ↑ | 2–6 wk | C | self-report bias, sleep | self-report quality is the limiting factor |
| luteal phase → rhr, resp_rate | ↑ | cyclic | B | training, sleep, illness | irregular cycles; hormonal contraception alters pattern |
| luteal phase → hrv | ↓ | cyclic | B | as above | must not be flagged as regression — see L1-WH |
| weight change → bmi, vo2max scaling | — | immediate | A | hydration, glycogen | day-to-day weight is mostly fluid, not mass |

**Note on the cycle rows:** these are among the most frequently mis-flagged
patterns in wearable coaching. A cyclic RHR rise and HRV dip in the luteal phase
is normal physiology; a system that flags it monthly as "declining recovery"
will be both wrong and irritating. Cycle phase must be a covariate in every
autonomic rule when the data is available, and rules must be widened when it is
not.

---

## 6. Building out the rest of the catalogue

1. Enumerate the exposure × outcome matrix (20 lifestyle inputs × 12
   well-measured outcomes = 240 candidate cells).
2. Delete every cell without a citable L1 mechanism section. Expect to keep
   roughly a third.
3. For each survivor, fill all six fields — and refuse to ship any entry with an
   empty `non_applicability` array. Every real relationship has conditions under
   which it fails; an empty field means the author hasn't found them yet.
4. Assign lag from physiology before looking at any data.
5. Register the timescale stratification (acute / intermediate / chronic) and
   check whether the sign flips. If it does, that is not a problem to hide —
   it is one of the most genuinely useful things the coach can explain.
