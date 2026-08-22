# F4.6 T5 Salience / Insight-Worthiness — Design (no implementation)

Status: **IMPLEMENTED** (deterministic contract). See `f46_salience_inspection_v1.md`. No Gemini, no CODIFY.

Orthogonal to F4.1 claim eligibility. Does not replace `direction`. Does not invent clinical cutoffs.

---

## 1. Current-state audit

### What exists today

| Layer | What it answers | What it does not answer |
|---|---|---|
| F4.1 `direction` + `percent_change` | Was the 7-vs-60 change large enough to leave the 3% noise band? | Is this worth a Directive-page INSIGHT? |
| F4.1 `claim_eligibility` | May we speak snapshot / early pattern / trend / recommendation-support? | Should we bother the user? |
| F4.3 weekly `claim_semantics` | May a weekly average be described / compared? | Insight-worthiness |
| F4.4 lifestyle | Observational co-occurrence | Importance of a weak metric |
| F4.5 `maintenance_of_gain` | Is recent stability still better than an older personal reference? | Whether to surface that as an INSIGHT |
| Agent `tools.py` decision | Any `trend_allowed` metric with `direction` not in `{stable, unknown}` → “Reviewing stored signals for …” | Magnitude, corroboration, absolute size |
| Evidence `meaningful_signal` | Gemini-chosen boolean into policy | Product salience |
| Output guard | Causal wording, unauthorized recs, suppressed IDs | Low-salience INSIGHT |
| Instructions | INSIGHT includes positive / negative / recovery / mixed / **stable-reassuring** | A contract for “worth surfacing” |

The 3% `STABLE_PERCENT_THRESHOLD` is a **detectability** knob. It is already doing the job the user does **not** want salience to clone: `abs(percent) < X ⇒ suppress`. Crossing 3% currently means “improving/declining” and that is treated as product-worthy.

### Failure cascade on frozen B1

1. Steps +6.55% and exercise +3.87% exceed 3% → `direction=improving`.
2. Activity log: “Reviewing stored signals for: exercise_minutes, steps.”
3. Gemini sets `meaningful_signal=true`, retrieves HHS activity chunks (`SURFACE`, rec unauthorized).
4. Instructions allow INSIGHT for a positive pattern “worth surfacing.”
5. Guard passes. Status=`INSIGHT`, confidence=`HIGH`.

Human review: technically correct, **low-salience for the Directive page**. Needed distinction: “a metric changed” vs “important enough to proactively surface.”

### Why a second percent cutoff is the wrong fix

- Exercise +3.87% is **+0.43 minutes** (~26 seconds). Percent fires; product meaning does not.
- Steps +6.55% is **+670 steps**. Percent fires; weekly history already 9442 → 10430 → 10516 → 10890 (gradual, not a break).
- Sleep −18% is ~−1.3 hours. Same 3% gate, completely different product weight.
- A3 resting HR −3.61% (~−2.5 bpm) is barely directional, but sits next to exercise +35% and HRV +15%. A lone `|pct| < 10 ⇒ suppress` rule would either kill A3’s named metric or still promote B1.
- F4.5 `maintenance_of_gain` is **stable** recently. A percent-suppress rule would hide B3’s held RHR/HRV/VO₂ gains.

Detectability and insight-worthiness must stay separate, the same way F4.1 separated snapshot / trend / recommendation-support.

---

## 2. Proposed salience architecture

Three orthogonal questions, in order:

1. **Eligibility (F4.1):** May this claim be made at all?
2. **Longitudinal (F4.5):** Is the recent state different from an older personal reference?
3. **Salience (F4.6):** Is this review worth a proactive INSIGHT (or a later recommendation), and why?

Salience **never** overrides eligibility. If `trend_allowed` is false, directional salience is capped / unavailable. Partial coverage **weakens** (caps level), it does not create importance.

Salience **does not hide** `direction`. B1 would still show steps `improving` +6.55%. The new contract would add: *low product salience, isolated, small absolute change, no older-horizon story.*

### Inputs (deterministic only)

- Magnitude: `percent_change` **and** `absolute_change` (already on `TrendResult`)
- Cross-metric families (closed list, not causal)
- F4.5 `maintenance_of_gain` / `maintenance_of_decline` / `longitudinal_context_available`
- F4.1 maturity: `trend_allowed`, `coverage_ratio`, `partial_coverage`, `gap_caveat_required`, `data_maturity_state`
- Lifestyle: **qualifier only**. Presence must not raise a weak physiological signal.

Weekly summaries remain observed-week facts. They must not independently set `insight_worthy`.

### Metric families (product grouping, not physiology-as-proof)

| Family | Metrics | Why |
|---|---|---|
| `activity` | `exercise_minutes`, `workout_count`, `steps` | Same behavioral bucket. Two *weak* members must **not** auto-promote (B1 trap). |
| `recovery` | `sleep_duration_hours`, `hrv_sdnn_ms`, `resting_hr_bpm` | Concordant sleep + HRV (or sleep + RHR) is more worth a look than either wiggle alone. |
| `fitness` | `vo2_max`, `resting_hr_bpm`, `exercise_minutes` | Supports “held fitness” / structured-training stories; still observational. |

Corroboration rule for MVP:

- Two metrics in a family **both** in the barely-directional band → **do not** raise payload `insight_worthy`. (B1 steps + exercise.)
- One **clear** metric plus a same-family directional partner → partner may be listed as `corroborating_metrics`; payload can be worthy. (A2/A3 day 60.)
- Two **recovery** metrics both at least barely-directional **and** same qualitative direction (both worse / both better) → may raise to worthy even if neither is “strong.” This is the sleep+HRV case, still not causation.

### Magnitude bands (product knobs, not medical thresholds)

Keep 3% as **detectable**. Add a *band*, not a hard suppress:

| Band | Intent |
|---|---|
| `none` | `direction=stable` or not `trend_allowed` |
| `barely_directional` | Detectable (≥3%) but not product-clear on **either** percent or absolute |
| `clear` | Percent ≥ proposed **10%** **or** absolute ≥ metric knob |
| `strong` | Percent ≥ proposed **15%** **and** absolute ≥ metric knob |

Proposed absolute knobs (Directive-card materiality, **not** clinical significance, **not** RAG-derived):

| Metric | Absolute “clear” knob | Why this shape |
|---|---|---|
| `sleep_duration_hours` | 0.50 h | 3% of 7h is 0.21h; B1 −0.13h stays none; A1 ~1.3h is strong |
| `resting_hr_bpm` | 3.0 bpm | B1 +0.96 none; A3 −2.5 still barely unless corroborated |
| `hrv_sdnn_ms` | 3.0 ms | Avoid treating +0.5 ms as an insight |
| `exercise_minutes` | 8.0 min/day | B1 +0.43 min cannot be “clear”; A2 +7 min is near-clear **and** +35% is clear on percent |
| `workout_count` | 0.20 / day (~+1.4 sessions/week) | Daily mean is fractional; percent is jumpy |
| `steps` | 1500 steps | B1 +670 stays barely; a +2k step break can be clear even if percent is modest |
| `vo2_max` | 1.0 ml/kg/min | Episodic; percent-only is noisy |

These numbers are **MVP starting knobs**, documented in code the same way as `STABLE_PERCENT_THRESHOLD`. They are not ACSM/AHA/sleep-medicine cutoffs and must not be phrased as such in user copy.

### Payload-level `insight_worthy` (derived, with reasons)

True if **any** of:

1. At least one metric with `trend_allowed` and magnitude band `clear` or `strong`
2. Recovery-family corroboration rule (above)
3. `maintenance_of_gain` or `maintenance_of_decline` is true (F4.5 already required a material older-horizon gap)

False when all directional metrics are `barely_directional` and there is no longitudinal maintenance flag (B1).

Caps:

- If no metric has `trend_allowed`, `insight_worthy` is false (fall back to snapshot/early-pattern language; do not mint a high-salience INSIGHT).
- `partial_coverage` or `gap_caveat_required` may not **increase** level. It may add reason `coverage_caveat` and cap `high` → `moderate`.
- Lifestyle events never flip false → true.

### `recommendation_worthy` is a separate, stricter gate

Not the same as insight-worthiness.

MVP: `recommendation_worthy` requires **all** of:

- F4.1 `recommendation_support_allowed` on the supporting metric(s)
- Payload would be `insight_worthy`
- At least one supporting metric is `clear`/`strong` **or** recovery corroboration (not maintenance-of-gain alone)

Still **cannot** authorize a recommendation. Evidence policy + `recommendation_authorized` remain the only rec authority. This field only answers: “is the physiology even in the neighborhood of supporting a rec, if policy later allows?”

B1: `recommendation_worthy=false` (and frozen policy already had rec unauthorized).
B3 maintenance-of-gain: may be `insight_worthy=true` and `recommendation_worthy=false` (celebrate/hold, don’t prescribe).

---

## 3. Proposed schema / fields

Prefer a **small object + closed-vocab reasons** over a 0–100 score (false precision) and over a lone boolean (second `data_sufficient`).

### Per metric (`trends[].salience`)

```text
salience_level: "none" | "low" | "moderate" | "high"
magnitude_band: "none" | "barely_directional" | "clear" | "strong"
insight_candidate: bool          # this metric can contribute to a surfaced insight
recommendation_candidate: bool   # stricter; still not policy authorization
corroborating_metrics: [str]
reasons: [str]                   # closed vocabulary
```

`salience_level` mapping (MVP):

- `none` — stable / ineligible
- `low` — barely directional, isolated or same-family weak-weak
- `moderate` — clear isolated, or barely + real corroboration, or maintenance flags
- `high` — strong magnitude, or clear + corroboration; coverage caveats cap this

### Payload (`insight_salience`)

```text
insight_worthy: bool
recommendation_worthy: bool
primary_metrics: [str]
corroborating_metrics: [str]
reasons: [str]
salience_level: "none" | "low" | "moderate" | "high"
```

Closed-vocab `reasons` (illustrative MVP set):

- `detectable_but_small_absolute`
- `isolated_barely_directional`
- `same_family_weak_corroboration`   # B1 steps+exercise
- `recovery_family_corroboration`
- `clear_recent_change`
- `strong_recent_change`
- `maintenance_of_gain`
- `maintenance_of_decline`
- `coverage_caveat`
- `trend_not_allowed`
- `no_older_horizon`
- `lifestyle_context_present_not_causal`  # qualifier only

Gemini should see **level + reasons + candidates**, not a hidden suppress. That matches F4.1: eligibility is visible; the model is asked to honor it.

TRACE origin (when implemented): `deterministic_salience_analytics`. No CoT.

---

## 4. B1 reconstruction (post-F4.5, 2026-06-18)

Computed from current analytics (no Gemini). Day-30 checkpoint. Coverage full. `gap_caveat_required=false`.

| Metric | Direction | % | Absolute | Maturity | F4.5 |
|---|---|---|---|---|---|
| sleep | stable | −1.79 | −0.13 h | ESTABLISHED_TREND | unavailable |
| RHR | stable | +1.35 | +0.96 bpm | ESTABLISHED_TREND | unavailable |
| HRV | stable | +1.63 | +0.51 ms | ESTABLISHED_TREND | unavailable |
| exercise_minutes | **improving** | **+3.87** | **+0.43 min** | ESTABLISHED_TREND | unavailable |
| workout_count | stable | 0 | 0 | ESTABLISHED_TREND | unavailable |
| steps | **improving** | **+6.55** | **+670 steps** | ESTABLISHED_TREND | unavailable |
| VO₂ | stable | −0.12 | −0.05 | ESTABLISHED_TREND | unavailable |

Also present:

- Weekly steps 9442 → 10430 → 10516 → 10890 (slow drift, not a break).
- Lifestyle 14-day window: 4 events (caffeine, alcohol, mood); `policy_available_inputs` includes `caffeine_mg`, `alcohol_units`. Physiology is not a problem.
- `longitudinal_summary`: no older prefix, all maintenance flags false.

### Answers

1. **Signals available:** Full F4.1 trends + weekly observed facts + F4.5 “no older history” + lifestyle events. Two directional flags (steps, exercise). Rec-support allowed on all seven (eligibility ≠ salience).

2. **What caused / could cause the low-salience INSIGHT:** `direction=improving` on steps (and secondarily exercise) after the 3% detectability gate, then agent trajectory treating any non-stable trend as investigation-worthy, then INSIGHT. Absolute size was never in the decision.

3. **Worth surfacing under this model?** **No.** `insight_worthy=false`, payload `salience_level=low`.

4. **Why:** Detectable ≠ Directive-worthy. +670 steps and +0.43 min, same activity family, both barely-directional, 5/7 metrics stable, no older-horizon gain, lifestyle must not inflate. `NO_SIGNIFICANT_NEW_PATTERN` (with optional factual stability note) matches the scenario intent.

5. **Fields Gemini needs:** existing direction/eligibility **plus** `insight_salience.insight_worthy=false`, `salience_level=low`, reasons `detectable_but_small_absolute` + `same_family_weak_corroboration` + `no_older_horizon`, per-metric bands for steps/exercise.

6. **Contract choice:** Use `salience_level` + `insight_worthy` + `reasons` + `corroborating_metrics`. Keep `insight_worthy` as a **derived summary**, not the only field (avoids a second `data_sufficient`). Do not use a 0–100 score.

7. **Responsibility split:** see §6.

---

## 5. Counterexample matrix

| Case | Sketch | Detectable? | Proposed `insight_worthy` | Notes |
|---|---|---|---|---|
| Small isolated change | B1 steps +6.55% / +670; exercise +0.43 min | Yes | **false** | Primary T5 target |
| Large isolated change | A1 sleep −18% / ~−1.3 h; other metrics mixed | Yes | **true** (high) | Isolated but strong; lifestyle may qualify, not cause |
| Two modest corroborating changes | Sleep −8% (−0.55 h) and HRV −8% (same window) | Yes | **true** (moderate) | Recovery family; association language only |
| Two weak activity wiggles | B1 steps + exercise | Yes | **false** | Must not count as corroboration |
| Stable + `maintenance_of_gain` | B3 RHR/HRV/VO₂ | Recent stable | **true** (moderate) | Do not treat as noise; rec-worthy likely false |
| Stable + `maintenance_of_decline` | B3 steps vs Phase 1 (−17.6%) | Recent stable | **true** (moderate) as a *possible* candidate | Surface as held decline, not praise; later T5/T7 copy still bounded |
| Partial coverage | D1-style missing as-of HRV, trend still allowed | Maybe | Unchanged truth-value; **cap high→moderate**, add `coverage_caveat` | Never manufactures salience |
| Lifestyle present, physiology stable | C3 caffeine; sleep stable | No directional problem | **false** | Events are context, not importance |
| Large change, no mature baseline | Early window, `trend_allowed=false`, huge 3-day swing | Direction unknown | **false** for INSIGHT | Snapshot/early_pattern may describe values; do not mint a high-salience trend insight |

Day-60 (A2/A3) check: exercise +35% is `strong`/`clear` → payload `insight_worthy=true`. RHR −3.61% / −2.5 bpm stays barely on its own and can appear as a **corroborator**, so A3 is not killed by the B1 fix.

---

## 6. Deterministic vs prompt vs CODIFY

| Decision | Where | This phase |
|---|---|---|
| Magnitude bands, families, `insight_worthy` derivation | Deterministic analytics (`analytics/salience.py` analog) | Design only |
| Keep showing `direction` even when not insight-worthy | Analytics contract | Design |
| Activity-log branch: no product-salient pattern vs reviewing signals | `agent/tools.py` (same style as F4.5 maintenance) | Later implementation |
| Honor `insight_worthy`; do not treat every `improving` as INSIGHT | Prompt / tool docstring | **Not now** (no prompt change) |
| Auto-flip `meaningful_signal` | Tempting; skip in MVP | Gemini still chooses the arg; field is visible |
| Block `status=INSIGHT` when `insight_worthy=false` | Output guard or CODIFY grader | **Later.** Guard is the wrong first hammer (over-blocks mixed/maintenance if the contract is ignored). Expose first, like F4.1. |
| Policy rec authorization | Unchanged evidence policy | No change |
| Directive-first copy (T7) | Generation / later CODIFY | Out of T5 |

MVP implementation (when approved), smallest useful slice:

1. Add `trends[].salience` + payload `insight_salience`.
2. Wire TRACE origin + reasons.
3. Decision-log branch only (no instruction rewrite, no guard rewrite).
4. Offline tests: B1 false; A1 true; day-60 true; B3 maintenance still candidate; C3 lifestyle does not boost; immature baseline cannot be `high`; F4.1/F4.5 unchanged.
5. Stop. No Gemini. No CODIFY.

---

## 7. Risks / open questions

1. **Knob tuning:** 10% / 1500 steps / 8 minutes are product guesses. They should live as named constants, not be justified as medical. Need a follow-up inspection table across the 15 frozen as-of dates before locking.
2. **A3 named metric is weak.** Payload-level worthiness (driven by exercise/HRV) is the intended protection. If implementation only looks at `primary_metrics` from the eval card, A3 could look like a miss.
3. **B3 `maintenance_of_decline` on steps.** F4.5 flags it. T5 should allow it as *eligible*, not *mandatory celebration*. Whether Gemini should lead with steps-down vs RHR-held is generation/T7, not this gate.
4. **Instructions currently allow stable-reassuring INSIGHT.** That collides with B1 if Gemini reads “stable” as INSIGHT-worthy. Contract first; prompt later.
5. **C2 ambiguity.** Salience must not use lifestyle to pick a winner among confounders.
6. **Workout_count percent** is unstable because the daily mean is ~0.3. Absolute knob is required.
7. **Enforcing in the guard too early** recreates `data_sufficient` as a silent suppress. Visibility first.

---

## 8. Recommendation (smallest MVP)

Implement a **visible, reason-bearing salience contract** next to F4.1/F4.5:

- Do **not** add `if abs(percent) < 10: suppress`.
- Do **not** change prompts, guards, taxonomy, or human labels in the first implementation slice.
- Do compute bands from **percent + absolute**, apply **asymmetric corroboration** (recovery yes / weak activity no), and treat **F4.5 maintenance flags as independently insight-eligible**.
- Expose `salience_level`, derived `insight_worthy`, `reasons`, `corroborating_metrics`, and a separate `recommendation_worthy`.
- Under that model, **B1 is not insight-worthy.**

Stop here pending design review.
