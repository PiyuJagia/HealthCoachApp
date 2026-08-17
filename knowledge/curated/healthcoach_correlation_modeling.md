---
doc_id: L2-CR-002
supersedes: L2-CR-001
title: Correlation & Relationship Modeling — Approved Relationship Catalogue, Suppression Gates and Safe Interpretation Levels
layer: L2
domain: analytics
metrics: [hrv_sdnn, rhr, sleep_total, sleep_efficiency, workout_freq, workout_intensity, training_load, vo2max_estimate, caffeine_mg, alcohol_units, cycle_phase]
entities: [correlation, association, confounding, within_person_inference, suppression, interpretation_level]
evidence_grade: pending_row_level_verification
verification_status: revision_complete_pending_review
approved_for_ingestion: FALSE
retrieval_hints:
  - "does alcohol affect my HRV"
  - "how does sleep affect my recovery"
  - "why did my resting heart rate go up"
  - "what is connected to what in my health data"
  - "is my training working"
last_revised: 2026-08-17
revision_basis: Phase C4 evidence audit of L2-CR-001
source_keys: [Reimers-2018-RHR, Gardiner-2023-CAF-SLEEP, Bellenger-2016-HR-TRAINING, Schmalenberger-2019-CYCLE-CVA, SD-HRV-META-2025, SLEEP-RESTRICT-HR-2023, Ralevski-2019-ALC-HRV, Spaak-2010-ALC-DOSE, Fisher-2018-ERGODICITY, AW-HRV-VALID-2025, Shaffer-2017, ACSM-GETP12, WHO-PA-2020]
---

# Correlation & Relationship Modeling

## 0. How to read this document

This document defines **which metric relationships the Health Coach is permitted to evaluate**, and the conditions under which a relationship may be shown to a user.

Three things to know before reading anything else, because they apply to every statement in this document:

1. **Every relationship here is an association, not a cause.** Arrow and directional notation is not used in this document for exactly that reason.
2. **A relationship existing in this catalogue does not mean it may be shown to a user.** It must first pass the gates in Section 3.
3. **"No reliable relationship detected" is a correct and complete answer.** The Health Coach is not required to find a pattern and should not manufacture one.

Every relationship entry in Section 5 is written to be safe when retrieved on its own. Each entry carries its own limitations, confounders, and contradiction conditions inside the entry. Do not rely on context from elsewhere in this document to make an entry safe.

---

## 1. Purpose of the correlation layer

The correlation layer is deliberately narrow. It is not responsible for discovering physiology. It answers five questions:

1. Did two of this user's metrics move together in a repeatable way?
2. Is that observed direction consistent with credible external evidence?
3. Is this relationship one that may be interpreted within a single person?
4. Is the signal strong and clean enough to show the user?
5. Is there a conflicting signal that should suppress the insight?

If the answer to any of questions 2 through 5 is unfavourable, the correct output is an observation, a mixed-signal statement, or silence.

**The system is designed to prefer restraint.** A suppressed insight is a successful outcome. A confident wrong explanation is the primary failure mode this layer exists to prevent.

---

## 2. Notation and language rules

**This document uses association language only.** The following phrasings are permitted in user-facing output:

- "tended to move with"
- "often coincided with"
- "was followed by"
- "may be associated with"
- "is consistent with"
- "occurred together during this period"

The following are **not permitted in user-facing output** for any relationship in this catalogue: *caused, causes, led to, resulted in, because of, improved, worsened, predicts, is driving, is due to.*

Where compact notation is used internally, it is **association notation, not causal notation**. The catalogue in Section 5 states an `observed_direction` field, which means "when input moved this way, output was observed to move that way in the cited evidence." It does not assert that changing the input will change the output for any individual.

### Worked example of the required register

| Quality | Output |
|---|---|
| **Not permitted** | "Poor sleep caused your resting heart rate to rise." |
| **Acceptable** | "During nights when you slept less, your resting heart rate was also higher than your recent baseline." |
| **Preferred** | "During this period, lower sleep duration and higher resting heart rate occurred together. Many factors can affect resting heart rate, so treat this as a pattern rather than proof of cause." |

---

## 3. Gates — evaluated in this order

A candidate insight must pass all five gates. Failing any gate stops escalation at the level indicated.

### Gate 1 — Catalogue gate (no correlation fishing)

**Only relationships listed as ACTIVE in Section 5 may be evaluated.**

The application must not scan metric pairs looking for whatever correlates most strongly. It must not infer a relationship because the data appears correlated. If a relationship is not in the ACTIVE catalogue, the observed correlation is treated as noise regardless of its strength.

This exists to prevent multiple-comparison artifacts, accidental correlations, and model-invented lifestyle explanations. A strong correlation between two unregistered metrics is not evidence of anything and must not be surfaced or narrated.

**Fail action:** do not evaluate. Do not mention the correlation.

### Gate 2 — Data-quality gate

Suppress the insight entirely if any of the following holds:

- Fewer paired observations than the relationship's stated minimum (see Section 9)
- A missing-data gap large enough that the comparison windows are not comparable
- A measurement-source change during the window (new device, OS update, changed wear pattern)
- Sampling density materially different between the two comparison periods
- Implausible or out-of-range values present
- Either metric unavailable for part of the window
- Comparison windows not temporally aligned

**Prefer silence to false precision.** A thin signal computed on sparse data is worse than no signal, because the user cannot tell the difference.

**Fail action:** output "insufficient data" or the underlying observation only. Never a correlation.

### Gate 3 — Within-person gate

Population evidence is **prior context, not proof of an individual relationship.** Group-level findings generalize to individuals only under ergodicity, which physiological and behavioural processes generally violate; within-individual variance around an expected value has been observed to run two to four times larger than within-group variance [Fisher-2018-ERGODICITY].

Before a personal correlation is surfaced, all of the following must hold:

1. Enough longitudinal paired observations for this user
2. The direction is consistent within that individual's own data, not just present on average
3. Temporal alignment is reasonable for the relationship's stated timescale
4. The relationship's `within_person_applicability` field permits individual interpretation
5. External evidence does not contradict the observed direction

If the user's observed direction **contradicts** the cited evidence direction, do not report either. Report the observation and note that the pattern is unclear.

**Fail action:** cap at Level 1 (observation).

### Gate 4 — Confounder gate

Check the relationship's `major_confounders` field. If a listed confounder is present in the window and cannot be separated from the candidate relationship, suppress or downgrade.

The initial gate is deliberately simple. It checks only for confounders that are both relevant to the specific relationship and available in the data:

recent illness · unusual training load · alcohol · caffeine · disrupted sleep · menstrual-cycle phase · travel · medication that materially alters heart rate (including rate-control agents) · device or measurement change

Do not attempt to model every possible confounder. Do not present a confounded relationship as causal under any circumstances.

**Fail action:** downgrade one level, or suppress if the confounder plausibly accounts for the whole pattern.

### Gate 5 — Contradiction gate (mandatory)

**If two or more candidate interpretations are simultaneously plausible and materially contradictory, do not surface a correlation insight.**

When contradictory signals are present:

- Suppress the correlation insight
- Do **not** select the explanation with the highest raw correlation
- Do **not** let the language model resolve the ambiguity by choosing the more plausible-sounding story
- Downgrade confidence
- Surface only the underlying observation, if it is useful on its own

Three concrete triggers:

- **HRV rises while training load rises.** This is consistent with positive adaptation *and* with functional overreaching. HRV direction alone cannot distinguish them [Bellenger-2016-HR-TRAINING]. Suppress.
- **Sleep worsens while a training metric improves and other recovery signals disagree.** Suppress.
- **Resting heart rate and HRV both rise, with recent training, illness, or alcohol offering competing explanations.** Suppress.

Required output shape when this gate fires:

> "Your recovery signals are mixed this week, so there is not enough consistent evidence to attribute the change to training."

Not:

> "Your higher training load is improving your recovery."

**Fail action:** suppress the correlation. Observation only.

---

## 4. Product interpretation levels

Four levels. Each relationship in Section 5 states its `max_product_level`. That cap may never be exceeded, regardless of how strong the observed correlation is.

**LEVEL 1 — OBSERVATION.** A single metric described against the user's own baseline.
> "Your resting heart rate has been above your 28-day baseline for three days."

**LEVEL 2 — PERSONAL CORRELATION.** Two of the user's metrics described as moving together, with no evidence claim and no mechanism.
> "On nights when your sleep was shorter, your resting heart rate also tended to be higher."

**LEVEL 3 — EVIDENCE CONTEXT.** The personal pattern plus a statement that it is directionally consistent with published evidence, plus an explicit limitation.
> "This pattern is directionally consistent with published evidence, although many factors can influence resting heart rate."

**LEVEL 4 — RECOMMENDATION.** A low-risk wellness suggestion. Permitted only when *all* of the following hold: the relationship is evidence-backed at strength B or better; the user-level signal is consistent; confounders are limited; no contradiction exists; and the recommendation itself is supported by credible guidance. If any criterion fails, do not escalate.

---

## 5. ACTIVE relationship catalogue

Nine active relationships. Each entry below is self-contained. **Fields are association descriptions, not causal claims.**

### Index

| ID | Input | Output | Evidence | Transfer risk | Max level | Status |
|---|---|---|---|---|---|---|
| R-01 | sleep_total | rhr | C | moderate | 2 | ACTIVE |
| R-02 | sleep_total | hrv_sdnn | C− | high | 2 | ACTIVE |
| R-03 | training_load (acute) | hrv_sdnn | B | moderate | 2 | ACTIVE |
| R-04 | training_load (acute) | rhr | C | moderate | 2 | ACTIVE |
| R-05 | aerobic exercise consistency | rhr | A | moderate | 4 | ACTIVE |
| R-06 | aerobic exercise consistency | vo2max_estimate | B | **high** | 3 | ACTIVE |
| R-07 | caffeine timing (user-entered) | sleep_total, sleep_efficiency | A | moderate | 4 | ACTIVE |
| R-08 | alcohol_units (user-entered) | sleep_efficiency, next-morning rhr / hrv_sdnn | C | moderate | 2 | ACTIVE |
| R-09 | cycle_phase (user-entered) | rhr, hrv_sdnn | B | moderate | 3 (modifier only) | ACTIVE |

---

### R-01 · Sleep duration and resting heart rate

- **relationship_id:** R-01
- **input_metric:** sleep_total (nightly sleep duration, Apple Health)
- **output_metric:** rhr (Apple Health daily resting heart rate)
- **relationship_type:** short-term association
- **observed_direction:** shorter sleep has been observed alongside higher resting heart rate
- **timescale:** same night into the following morning (0–1 day)
- **evidence_strength:** C — limited. Supported by a small randomized crossover polysomnography study (20 men, mean age ~41) in which a 5-hour sleep-restriction night showed significantly higher heart rate than the participant's own baseline night [SLEEP-RESTRICT-HR-2023]. Not a meta-analysis. Male-only sample.
- **source_keys:** SLEEP-RESTRICT-HR-2023
- **support_type:** direct, narrow population
- **within_person_applicability:** permitted — the source design is itself within-person
- **measurement_context:** evidence = laboratory PSG with ECG; product = consumer wearable derived daily value
- **measurement_transfer_risk:** moderate
- **major_confounders:** alcohol, illness, ambient heat, late caffeine, unusual prior-day training load, cycle phase
- **contradiction_conditions:** suppress if alcohol or illness is present in the same window, since either can produce the identical pattern independently. Suppress if HRV moves in the same direction as RHR rather than the opposite direction.
- **max_product_level:** 2
- **verification_status:** sourced, pending source-registry entry
- **user_safe_language:** "On nights when you slept less, your resting heart rate the next morning tended to be higher than your recent baseline. Sleep is one of several things that can affect resting heart rate."
- **status:** ACTIVE

> **Limitation carried with this row:** Apple resting heart rate is an algorithmically derived daily value, not a clinical resting measurement. Do not interpret it against clinical diagnostic thresholds such as the 60–100 bpm adult reference range.

---

### R-02 · Sleep duration and HRV

- **relationship_id:** R-02
- **input_metric:** sleep_total
- **output_metric:** hrv_sdnn (Apple Health SDNN)
- **relationship_type:** short-term association
- **observed_direction:** shorter sleep has been observed alongside reduced heart-rate variability
- **timescale:** same night into the following day (0–1 day)
- **evidence_strength:** C− — **weaker for SDNN specifically than for other HRV metrics.** In meta-analysis of sleep deprivation, RMSSD decreased significantly while **SDNN showed only a non-significant reduction**; low-frequency power and the LF/HF ratio increased significantly [SD-HRV-META-2025]. Apple Health supplies SDNN, which is the metric with the weaker evidence.
- **source_keys:** SD-HRV-META-2025, Shaffer-2017 (metric definitions only)
- **support_type:** partial — evidence is stronger for a metric the product does not have
- **within_person_applicability:** permitted for personal correlation only; **not** permitted for evidence contextualization, because the evidence does not establish the effect in this metric
- **measurement_context:** evidence = laboratory ECG, controlled recording length; product = ultra-short opportunistic PPG samples taken every few hours
- **measurement_transfer_risk:** **high**
- **major_confounders:** alcohol, illness, cycle phase, prior-day training load, measurement timing and posture, sampling sparsity
- **contradiction_conditions:** suppress if fewer than the minimum HRV samples are present in either window. Suppress if training load is also elevated, since acute load produces the same direction (see R-03) and the two cannot be separated.
- **max_product_level:** 2
- **verification_status:** sourced with explicit metric caveat
- **user_safe_language:** "On nights when you slept less, your HRV readings also tended to be lower. HRV readings from a watch vary for many reasons, so treat this as a loose pattern."
- **status:** ACTIVE

> **Limitation carried with this row:** Published HRV norms are derived from controlled ECG recordings of defined length, and their own authors caution that values across different recording lengths are not interchangeable [Shaffer-2017]. Apple SDNN is a fourth category those norms do not cover. Lab validation of Apple Watch against 3-lead ECG found near-perfect agreement for interbeat intervals and heart rate but only moderate agreement for N-N intervals, with mean absolute percentage error around 31% at rest [AW-HRV-VALID-2025]. **Never compare an Apple SDNN value to a published normative cutoff.**

---

### R-03 · Acute training load and HRV

- **relationship_id:** R-03
- **input_metric:** training_load (acute, 0–2 days prior)
- **output_metric:** hrv_sdnn
- **relationship_type:** short-term association
- **observed_direction:** in the days immediately following unusually high training load, reduced HRV has commonly been observed
- **timescale:** 0–2 days
- **evidence_strength:** B — supported by systematic review and meta-analysis of autonomic heart-rate regulation in endurance-trained athletes [Bellenger-2016-HR-TRAINING]. Population is trained athletes; generalization to unselected users is uncertain.
- **source_keys:** Bellenger-2016-HR-TRAINING
- **support_type:** direct, athlete population
- **within_person_applicability:** permitted for the acute direction only
- **measurement_context:** evidence = ECG / chest strap in trained athletes; product = consumer PPG in general population
- **measurement_transfer_risk:** moderate
- **major_confounders:** sleep, alcohol, ambient heat, illness, cycle phase
- **contradiction_conditions:** **Mandatory suppression trigger.** If HRV *rises* rather than falls alongside sustained higher training load, do not interpret the direction at all. Increases in vagal HRV indices are observed both when positive adaptation has occurred **and** in functionally overreached athletes, and post-exercise RMSSD has been reported to increase in functional overreaching — a finding the source authors themselves describe as paradoxical [Bellenger-2016-HR-TRAINING]. **HRV direction alone cannot distinguish positive adaptation from functional overreaching.** Suppress and report the observation only.
- **max_product_level:** 2
- **verification_status:** sourced
- **user_safe_language:** "In the day or two after your harder sessions, your HRV readings tended to be lower than your baseline. This is a common short-term pattern and is not by itself a sign of a problem."
- **status:** ACTIVE

> **Limitation carried with this row:** HRV direction is not diagnostic of training status in either direction. Do not tell a user their training is or is not working based on HRV.

---

### R-04 · Acute training load and resting heart rate

- **relationship_id:** R-04
- **input_metric:** training_load (acute, 0–2 days prior)
- **output_metric:** rhr
- **relationship_type:** short-term association
- **observed_direction:** in the days immediately following unusually high training load, elevated resting heart rate has commonly been observed
- **timescale:** 0–2 days
- **evidence_strength:** C — consistent with the autonomic-regulation literature in trained athletes [Bellenger-2016-HR-TRAINING], but resting heart rate is a less directly studied outcome than HRV in that source.
- **source_keys:** Bellenger-2016-HR-TRAINING
- **support_type:** partial
- **within_person_applicability:** permitted
- **measurement_context:** evidence = ECG in athletes; product = consumer derived daily value
- **measurement_transfer_risk:** moderate
- **major_confounders:** alcohol, illness, heat, dehydration status (not measured), sleep loss, cycle phase
- **contradiction_conditions:** suppress if illness indicators or alcohol are present, since both produce the same direction. Suppress if the elevation persists well beyond the stated 0–2 day window, since that is no longer an acute-load pattern and may indicate something this catalogue does not cover.
- **max_product_level:** 2
- **verification_status:** sourced, evidence thin for this specific outcome
- **user_safe_language:** "Your resting heart rate tended to sit a little above your baseline in the day or two after harder sessions."
- **status:** ACTIVE

---

### R-05 · Aerobic exercise consistency and resting heart rate

- **relationship_id:** R-05
- **input_metric:** aerobic exercise consistency (frequency and duration of aerobic sessions over 6–12 weeks)
- **output_metric:** rhr
- **relationship_type:** longer-term association with interventional support
- **observed_direction:** sustained aerobic exercise has been associated with lower resting heart rate
- **timescale:** 6–12 weeks
- **evidence_strength:** **A** — systematic review and meta-analysis of interventional studies, 191 studies across 215 samples. All exercise types reduced resting heart rate; endurance training and yoga were significant in both sexes [Reimers-2018-RHR]. Consistent with ACSM and WHO activity guidance [ACSM-GETP12, WHO-PA-2020].
- **source_keys:** Reimers-2018-RHR, ACSM-GETP12, WHO-PA-2020
- **support_type:** direct, interventional
- **within_person_applicability:** permitted, with the caveat that the *magnitude* for any individual is not predictable
- **measurement_context:** evidence = clinical and laboratory resting heart rate; product = consumer derived daily value. Direction transfers; absolute values do not.
- **measurement_transfer_risk:** moderate
- **major_confounders:** weight change, sleep, alcohol, illness, medication affecting heart rate
- **known effect modifiers (evidence-based):** the reduction was **positively related to pre-intervention resting heart rate and negatively related to participant age** [Reimers-2018-RHR]. Strength-only training showed weaker and less consistent effects than endurance work. **Set expectations accordingly for older users and users whose starting resting heart rate is already low — a small or absent change is expected, not a failure.**
- **contradiction_conditions:** suppress if a rate-affecting medication was started or stopped during the window. Suppress if weight changed substantially, since that is a competing explanation.
- **max_product_level:** **4**
- **verification_status:** sourced; ACSM key requires edition verification
- **user_safe_language:** Level 2 — "Over the past few months, as your aerobic sessions became more regular, your resting heart rate has trended down." Level 4 — "Keeping your aerobic sessions consistent is well supported for cardiovascular health. Maintaining your current routine is a reasonable goal."
- **status:** ACTIVE

---

### R-06 · Aerobic exercise consistency and estimated cardio fitness

- **relationship_id:** R-06
- **input_metric:** aerobic exercise consistency over 8–12 weeks
- **output_metric:** vo2max_estimate (Apple Health cardio fitness — **a derived estimate, not a measurement**)
- **relationship_type:** longer-term association with guideline support
- **observed_direction:** sustained aerobic training has been associated with higher measured cardiorespiratory fitness
- **timescale:** 8–12 weeks
- **evidence_strength:** B — the underlying training effect is well established in exercise-science guidance [ACSM-GETP12, WHO-PA-2020]. Graded B rather than A **because the product's outcome metric is an algorithmic estimate, not the measured value the evidence is based on.**
- **source_keys:** ACSM-GETP12, WHO-PA-2020
- **support_type:** context — the evidence concerns measured VO₂max, not a wrist-derived estimate
- **within_person_applicability:** conditional — estimation error may exceed a real training effect over this window
- **measurement_context:** evidence = laboratory or submaximal exercise testing; product = **derived estimate**
- **measurement_transfer_risk:** **HIGH**
- **major_confounders:** body-weight change, estimation error, changes in workout type recorded, terrain and GPS quality
- **contradiction_conditions:** **suppress if body weight changed materially during the window.** Cardio fitness is expressed per kilogram, so weight loss alone raises the value arithmetically without any change in fitness. This is a measurement artifact and must never be presented as improved fitness. Suppress if the estimate moves in the opposite direction to resting heart rate over the same window.
- **max_product_level:** **3 — this relationship must not drive a recommendation**, because measurement-transfer risk is high.
- **verification_status:** sourced at guideline level; requires ACSM edition verification
- **user_safe_language:** "Your estimated cardio fitness has trended up over this period, alongside more consistent aerobic sessions. This figure is an estimate from your watch, and body-weight changes affect it too."
- **status:** ACTIVE

---

### R-07 · Caffeine timing and sleep

- **relationship_id:** R-07
- **input_metric:** caffeine_mg with time of consumption (**user-entered lifestyle input; this relationship is inactive unless the user supplies it**)
- **output_metric:** sleep_total, sleep_efficiency
- **relationship_type:** same-day association with dose and timing structure
- **observed_direction:** caffeine consumed closer to bedtime, and at higher doses, has been associated with shorter and less efficient sleep
- **timescale:** same night (0 days)
- **evidence_strength:** **A** — systematic review and meta-analysis of 24 studies. Caffeine reduced total sleep time by about 45 minutes and sleep efficiency by about 7%, increased sleep-onset latency by about 9 minutes, and reduced deep sleep duration by about 11 minutes. Total sleep time recovered by roughly 2.8 minutes for each additional hour earlier the caffeine was consumed [Gardiner-2023-CAF-SLEEP].
- **source_keys:** Gardiner-2023-CAF-SLEEP
- **support_type:** direct, quantified
- **within_person_applicability:** permitted — and this is the strongest candidate in the catalogue for a personal pattern, because individual variation in caffeine sensitivity is wide
- **measurement_context:** evidence = polysomnography and actigraphy; product = self-reported exposure plus consumer sleep tracking
- **measurement_transfer_risk:** moderate
- **major_confounders:** alcohol, tolerance, age, evening screen use, total dose across the day, under-reporting of intake
- **contradiction_conditions:** suppress if alcohol was also consumed, since it independently affects sleep. Suppress if reported caffeine intake is implausibly sparse relative to typical patterns, since under-reporting will corrupt the comparison.
- **max_product_level:** **4**
- **verification_status:** sourced
- **user_safe_language:** Level 2 — "On days when your last caffeine was later in the afternoon, your sleep tended to be shorter." Level 4 — "If you'd like to test it, moving your last caffeine earlier is a low-risk change. Published averages suggest a standard coffee has less effect on sleep when taken well before bedtime, though individual sensitivity varies a lot."
- **status:** ACTIVE (gated on availability of user-entered caffeine data)

> **Population-average timings are not personal thresholds.** The published cut-offs — roughly 8.8 hours before bed for a standard 107 mg coffee, and about 13.2 hours for a 217.5 mg pre-workout dose [Gardiner-2023-CAF-SLEEP] — are population starting points. Do not present them to a user as their personal limit.

---

### R-08 · Alcohol and sleep / next-morning autonomic readings

- **relationship_id:** R-08
- **input_metric:** alcohol_units (**user-entered lifestyle input; this relationship is inactive unless the user supplies it**)
- **output_metric:** sleep_efficiency, next-morning rhr, next-morning hrv_sdnn
- **relationship_type:** short-term association
- **observed_direction:** alcohol consumption has been observed alongside reduced sleep efficiency, and alongside reduced heart-rate variability and elevated heart rate in the hours following intake
- **timescale:** same night into the following morning (0–1 day)
- **evidence_strength:** C — a narrative review of 33 studies reports that acute alcohol reduces parasympathetic and increases sympathetic HRV indices [Ralevski-2019-ALC-HRV]. A small controlled study (12 participants) found alcohol reduced parasympathetic HRV indices in a dose-dependent manner, with sympathetic augmentation only at the higher two-drink dose [Spaak-2010-ALC-DOSE]. Small samples, laboratory conditions, no meta-analysis identified.
- **source_keys:** Ralevski-2019-ALC-HRV, Spaak-2010-ALC-DOSE
- **support_type:** partial
- **within_person_applicability:** permitted for personal correlation only
- **measurement_context:** evidence = laboratory ECG; product = self-reported exposure plus consumer PPG and sleep tracking
- **measurement_transfer_risk:** moderate
- **major_confounders:** late eating, evening training, poor sleep independent of alcohol, dehydration (not measured), illness, under-reporting of intake
- **contradiction_conditions:** **Low doses do not behave like higher doses.** The literature is inconsistent at low intake, with some findings of unchanged or even increased HRV at low regular consumption [Ralevski-2019-ALC-HRV, Spaak-2010-ALC-DOSE]. Suppress the relationship for single-unit or very low reported doses. Suppress entirely if the user reports rate-control medication or has indicated an atrial fibrillation diagnosis, since HRV interpretation does not hold. Suppress if illness indicators are present.
- **max_product_level:** 2
- **verification_status:** sourced, evidence strength limited
- **user_safe_language:** "On nights after you recorded drinking, your sleep efficiency tended to be lower and your resting heart rate the next morning tended to be higher than your baseline. This is a pattern in your own data rather than a measured cause."
- **status:** ACTIVE (gated on availability of user-entered alcohol data)

> **Do not moralize and do not escalate.** This relationship is capped at Level 2. The correlation layer must not generate advice about drinking. Reporting the observed pattern is the entire permitted output.

---

### R-09 · Menstrual-cycle phase — modifier and suppressor only

- **relationship_id:** R-09
- **input_metric:** cycle_phase (**user-entered; inactive unless supplied**)
- **output_metric:** rhr, hrv_sdnn
- **relationship_type:** **cyclic modifier — not an insight in its own right**
- **observed_direction:** heart-rate variability has been observed to decrease from the follicular to the luteal phase; resting heart rate and respiratory rate have been observed to run higher in the luteal phase
- **timescale:** cyclic, within each cycle
- **evidence_strength:** B for HRV — systematic review and meta-analysis of **within-person** changes in cardiac vagal activity across the menstrual cycle, 37 studies and 1,004 individuals in naturally-cycling premenopausal participants [Schmalenberger-2019-CYCLE-CVA]. C for resting heart rate, which is less directly established in that source.
- **source_keys:** Schmalenberger-2019-CYCLE-CVA
- **support_type:** direct, and unusually well matched to this product because the pooled evidence is itself within-person
- **within_person_applicability:** permitted — this is the one relationship in the catalogue whose source evidence is within-person by design
- **measurement_context:** evidence = ECG-derived HRV with repeated measures; product = consumer PPG plus self-reported cycle data
- **measurement_transfer_risk:** moderate
- **major_confounders:** irregular cycles, hormonal contraception (which alters the pattern), illness, training load
- **contradiction_conditions:** do not apply if cycle data is absent, irregular, or the user reports hormonal contraception. When cycle data is unavailable, **widen the tolerance on autonomic rules rather than assuming a phase.**
- **max_product_level:** 3 — explanatory context only
- **verification_status:** sourced
- **primary function — SUPPRESSION:** a cyclic luteal-phase rise in resting heart rate and dip in HRV is **normal physiology, not declining recovery.** When cycle data is available, this relationship must suppress any "recovery is declining" or "resting heart rate is elevated" insight that coincides with the luteal phase. A system that flags normal cyclic variation monthly is both wrong and corrosive to user trust.
- **user_safe_language:** "Your resting heart rate and HRV shift across your cycle, and this week's readings are consistent with that normal pattern rather than a change in your recovery."
- **status:** ACTIVE (modifier and suppressor role only — never surfaced as a standalone correlation insight)

---

## 6. DEFERRED relationships

Potentially useful. Not active. **A deferred relationship must not be evaluated or narrated.**

| ID | Relationship | Why deferred | What would make it active |
|---|---|---|---|
| D-01 | sleep consistency and HRV / resting heart rate | The strong evidence for sleep regularity concerns **mortality and cardiovascular risk over years** [Windred-2024-SRI, Cribb-2023-SRI], not HRV or resting heart rate over weeks. The previous catalogue substituted one outcome for another. | Evidence linking regularity specifically to autonomic metrics on a weeks-to-months timescale |
| D-02 | aerobic training and 1-minute heart-rate recovery | The metric is not reliably derivable from Apple Health, and it depends on consistent cool-down behaviour | A reliable, consistently measured HRR value |
| D-03 | illness onset signature (resting heart rate and respiratory rate rising together) | Alert-generating and safety-adjacent. Heat, alcohol, altitude, and hard prior-day training produce the same signature. Requires its own document and a clinical-escalation boundary. | A dedicated curated document plus a specificity and false-positive assessment |
| D-04 | vigorous exercise ending within ~1 hour of bedtime, and sleep onset / duration | Requires reliable alignment of workout end time with bedtime. Note that the **general** direction is the opposite of what the previous catalogue claimed: meta-analysis found evening exercise did not disturb sleep and modestly increased slow-wave sleep, with impairment confined to vigorous exercise ending within about an hour of bedtime [Stutz-2019-EVE-EX]. | Reliable workout-end-to-bedtime alignment in the data |
| D-05 | perceived stress or mood, and autonomic metrics | Requires a validated self-report instrument the app does not yet collect | A validated instrument and evidence from free-living rather than laboratory stressor studies |
| D-06 | travel across time zones, and sleep or HRV | Travel data is not collected. The previous "≥3 time zones" threshold was not derived from evidence. | Collection of travel data and threshold evidence |
| D-07 | sleep-stage-specific relationships (deep sleep, REM) | Consumer sleep-staging agreement with polysomnography is moderate at best, and deep sleep is among the least reliable stages | Improved staging reliability or validation data |
| D-08 | detraining and resting heart rate / cardio fitness | Requires a defined detraining-detection rule that distinguishes a taper from genuine detraining | A defined detection rule |
| D-09 | steps and active energy | This is arithmetic, not a correlation. Reporting it as a discovered relationship would be misleading. | Not applicable — belongs in a metrics document, not here |

---

## 7. REMOVED relationships

Not appropriate for this product. **Do not reintroduce without a new evidence review.**

| ID | Relationship | Reason for removal |
|---|---|---|
| X-01 | dehydration and resting heart rate | The exposure cannot be measured at acceptable quality. Self-reported water intake is too weak to support any inference. |
| X-02 | diet quality and energy or recovery | Exposure not measurable at acceptable quality via app self-report. |
| X-03 | energy deficit and autonomic recovery | Evidence limited, and the safety burden outweighs the value. **Replaced by a global suppression rule — see Section 12.** |
| X-04 | steps and body weight | Intake compensation commonly nullifies the relationship at the individual level. Presenting it would mislead. |
| X-05 | morning light exposure and sleep timing | Exposure is not available from Apple Health. |
| X-06 | all multi-step mediation chains | Three- and four-step chains read as verified causal pathways when retrieved in isolation. Removed entirely from this document. |
| X-07 | expected effect-size priors in personal SD units | No published prior exists in these units for any relationship in the catalogue. The registry field ships empty and is learned from the individual's data. |
| X-08 | washout-period table | Values were unsourced and internally inconsistent with the lags claimed elsewhere. |
| X-09 | N-of-1 experimental prescriptions | Out of scope for this capstone phase. Preserve the design intent in a later document; do not ship prescriptive trial protocols now. |
| X-10 | decorrelation window as an empirical fact | Moved to Section 9 as a labelled implementation default. |

---

## 8. Measurement context reference

Five categories, kept distinct throughout this document:

| Category | Example | Interpretation rule |
|---|---|---|
| **Clinical measurement** | Resting heart rate taken seated in a clinic | Clinical thresholds apply to clinical measurements only |
| **Laboratory measurement** | ECG-derived HRV; polysomnography; measured VO₂max | The source of most evidence in this catalogue |
| **Consumer wearable measurement** | Apple resting heart rate; Apple SDNN; consumer sleep staging | Direction may transfer from laboratory evidence; **absolute values and thresholds do not** |
| **Derived estimate** | Apple cardio fitness (VO₂max estimate) | Treat as an estimate with its own error; never drive a recommendation from it alone |
| **Self-report** | Caffeine, alcohol, cycle phase | Subject to under-reporting; a missing entry is not a zero |

**Three rules that apply everywhere in this document:**

- Apple resting heart rate must not be interpreted using clinical diagnostic thresholds. The 60–100 bpm adult reference range [AHA-RHR] describes a calm clinical measurement and must not be used to flag a wearable value.
- Apple HRV SDNN must not inherit ECG normative cutoffs without explicit qualification [Shaffer-2017, AW-HRV-VALID-2025].
- Apple VO₂max is an estimate and is expressed per kilogram of body weight, so weight change alters it without any change in fitness.

**Relationships with high measurement-transfer risk must not drive recommendations.** In this catalogue that means R-02 and R-06.

---

## 9. DESIGN DEFAULTS — NOT EMPIRICAL FINDINGS

**Everything in this section is an implementation choice, not a research finding.** The literature does not establish these values. They are chosen to be conservative, and they are configurable.

| Default | Value | Basis |
|---|---|---|
| Minimum paired observations before any correlation is reported | 20 | **Implementation default, not an empirical threshold.** Chosen for conservatism. |
| Baseline window | 28 days | Implementation default. |
| Detrending window | 60-day robust rolling median | Implementation default. |
| Comparison period for longer-term relationships | 8–12 weeks | Implementation default, loosely aligned to the timescales in the cited training literature. |
| Assumed decorrelation time for interval correction | 3–7 days | **Implementation default.** Should be measured from the individual's own series rather than assumed. |
| Lag search | **none — no lag search permitted** | Lags come from the relationship entry. Selecting the best-fitting lag from data and then reporting its significance finds relationships in noise. |
| Statistical reporting | effect size in the user's own units and personal SDs, with an interval | Implementation choice. Never report a bare correlation coefficient to a user. |

**Two rules attached to this section:**

1. Do not present any value in this table to a user as though evidence supports it.
2. The minimum-observation default is a floor, not a licence. Passing it does not make a relationship reportable — Gates 3 through 5 still apply.

---

## 10. Null results are valid results

**"No reliable relationship detected" is a successful outcome.** The Health Coach is not required to produce a correlation and must not manufacture one to appear useful.

Permitted outputs from the correlation layer:

- reliable pattern detected
- weak pattern — monitor
- contradictory signals — suppressed
- insufficient observations
- data quality insufficient
- evidence does not support individual interpretation for this relationship
- no meaningful relationship detected

A null result should be delivered plainly, as a finding: *"I didn't find a consistent pattern between these two over this period."* Users who see nulls reported have reason to believe the positives.

---

## 11. Recommendation rule

The correlation layer **must not prescribe medical or clinical action**, must not suggest a user has a condition, and must not recommend for or against medication.

It may support low-risk wellness suggestions only:

- consider a lighter training day
- prioritize sleep opportunity
- maintain exercise consistency
- allow recovery after unusually hard training
- consider moving caffeine earlier, where the user's own data consistently supports the pattern

Every recommendation requires **all four** of:

user trend + verified relationship at strength B or better + credible source + no material contradiction

A high correlation coefficient is not one of the four and is never sufficient on its own.

**If the relationship's `max_product_level` is below 4, no recommendation may be generated from it under any circumstances.** In the current catalogue only R-05 and R-07 are eligible.

---

## 12. Safety rules

**Disordered-eating suppression (global).** If eating-disorder risk is indicated for a user, the Health Coach must emit **no numeric weight, body-composition, energy-intake, energy-deficit, or calorie-target output of any kind**, from any relationship, and no insight connecting activity to weight. This is not a per-relationship gate; it is a global output suppression, because equivalent reinforcement can reach a user through several different rows. This is why X-03 and X-04 were removed rather than gated.

**No clinical interpretation.** The correlation layer does not diagnose, does not name conditions, and does not interpret values against clinical thresholds. If a user's data suggests something clinically concerning, the correct output is a plain observation plus a suggestion to speak with a clinician — never an interpretation.

**Cycle variation is not deterioration.** See R-09. Normal cyclic autonomic variation must never be flagged as declining recovery.

**Conflict resolves toward silence.** When evidence, user data, or candidate explanations conflict, do not surface a causal or correlational explanation. Prefer observation only, a mixed-signal statement, an insufficient-evidence statement, or continued monitoring. **The Health Coach is designed to be rewarded for restraint.**

---

## 13. Source keys required by this document

| Key | Source | Identifier | Type | Used by |
|---|---|---|---|---|
| Reimers-2018-RHR | Reimers AK, Knapp G, Reimers C-D. Effects of Exercise on the Resting Heart Rate: A Systematic Review and Meta-Analysis of Interventional Studies. J Clin Med 2018;7(12):503 | DOI 10.3390/jcm7120503 | Systematic review / meta-analysis | R-05 |
| Gardiner-2023-CAF-SLEEP | Gardiner C, Weakley J, Burke LM, et al. The effect of caffeine on subsequent sleep: A systematic review and meta-analysis. Sleep Med Rev 2023;69:101764 | DOI 10.1016/j.smrv.2023.101764 · PMID 36870101 | Systematic review / meta-analysis | R-07 |
| Bellenger-2016-HR-TRAINING | Bellenger CR, Fuller JT, Thomson RL, et al. Monitoring Athletic Training Status Through Autonomic Heart Rate Regulation. Sports Med 2016;46(10):1461–1486 | DOI 10.1007/s40279-016-0484-2 · PMID 26888648 | Systematic review / meta-analysis | R-03, R-04 |
| Schmalenberger-2019-CYCLE-CVA | Schmalenberger KM, Eisenlohr-Moul TA, Würth L, et al. A Systematic Review and Meta-Analysis of Within-Person Changes in Cardiac Vagal Activity across the Menstrual Cycle. J Clin Med 2019;8(11):1946 | DOI 10.3390/jcm8111946 · PMID 31726666 | Within-person systematic review / meta-analysis | R-09 |
| SD-HRV-META-2025 | Effects of sleep deprivation on heart rate variability: a systematic review and meta-analysis (11 studies, 549 participants), 2025 | PMC12394884 — **author and journal metadata to be completed at registry entry** | Systematic review / meta-analysis | R-02 |
| SLEEP-RESTRICT-HR-2023 | Effects of sleep fragmentation and partial sleep restriction on heart rate variability during night. Sci Rep 2023 | DOI 10.1038/s41598-023-33013-5 — **author metadata to be completed at registry entry** | Randomized crossover primary research (n=20 men) | R-01 |
| Ralevski-2019-ALC-HRV | Ralevski E, Petrakis I, Altemus M. Heart rate variability in alcohol use: A review. Pharmacol Biochem Behav 2019;176:83–92 | DOI 10.1016/j.pbb.2018.12.003 · PMID 30529588 | Narrative review | R-08 |
| Spaak-2010-ALC-DOSE | Spaak J, et al. Dose-related effects of red wine and alcohol on heart rate variability. Am J Physiol Heart Circ Physiol 2010 | DOI 10.1152/ajpheart.00700.2009 | Primary research (n=12, randomized single-blind) | R-08 |
| Fisher-2018-ERGODICITY | Fisher AJ, Medaglia JD, Jeronimus BF. Lack of group-to-individual generalizability is a threat to human subjects research. PNAS 2018;115(27):E6106–E6115 | DOI 10.1073/pnas.1711978115 · PMID 29915059 | Primary research | Gate 3 |
| AW-HRV-VALID-2025 | Validity of Heart Rate Variability Measured with Apple Watch Series 6 Compared to Laboratory Measures. Sensors 2025;25(8):2380 | PMID 40285070 | Device validation | R-02, Section 8 |
| Shaffer-2017 | Shaffer F, Ginsberg JP. An Overview of Heart Rate Variability Metrics and Norms. Front Public Health 2017;5:258 | DOI 10.3389/fpubh.2017.00258 · PMID 29034226 | Narrative review | R-02, Section 8 — **metric definitions and recording-length caveat only** |
| ACSM-GETP12 | ACSM's Guidelines for Exercise Testing and Prescription, 12th ed., 2025 | ISBN pending | Professional guideline | R-05, R-06 — **requires page-level verification; supersedes ACSM-GETP11** |
| WHO-PA-2020 | WHO Guidelines on Physical Activity and Sedentary Behaviour; Bull FC et al., Br J Sports Med 2020;54:1451–1462 | DOI 10.1136/bjsports-2020-102955 · PMID 33239350 | Global public-health guideline | R-05, R-06 — **activity dosing only** |
| AHA-RHR | American Heart Association, All About Heart Rate (Pulse) | heart.org health topic page | **Consumer patient education — capped at grade C, may support the reference range only** | Section 8 |
| Windred-2024-SRI · Cribb-2023-SRI · Stutz-2019-EVE-EX | Cited only in Section 6 to explain why D-01 and D-04 are deferred | Windred: Sleep 2024;47(1):zsad253 · Cribb: PMID 37995126 · Stutz: DOI 10.1007/s40279-018-1015-0 | Cohort studies; systematic review | Section 6 only — **not active relationships** |

---

## 14. Remaining evidence gaps

Documented rather than filled.

1. **Sleep and resting heart rate (R-01) rests on a single small male-only study.** A meta-analysis on this specific pairing was not located. This is the weakest evidence base among the active rows and is the reason R-01 is capped at Level 2.
2. **Sleep and SDNN specifically (R-02).** The meta-analytic evidence is for RMSSD. No source establishes the effect in the metric the product actually has.
3. **Acute training load and resting heart rate (R-04).** The cited source treats HRV more directly than resting heart rate.
4. **Alcohol (R-08) has no meta-analysis identified** for acute effects on nocturnal autonomic measures in a general population. Current sourcing is a narrative review plus small laboratory studies.
5. **No published within-person effect-size priors exist** in personal-SD units for any relationship in this catalogue. This will not be resolved by finding a better source; it is resolved by accumulating each user's own estimate.
6. **Apple-specific measurement validity needs its own curated document.** Validation data for Apple HRV, resting heart rate, sleep staging, and cardio-fitness estimation is currently referenced ad hoc rather than systematically.
7. **Age and sex reference baselines on consumer wearables are unavailable.** This document therefore performs **no demographic normalization** and relies on within-person baselines instead. That is a deliberate choice, not an omission — the evidence to support demographic adjustment on wearable data does not exist.
8. **ACSM edition currency.** R-05 and R-06 reference GETP 12, which requires page-level verification by someone with access before those citations are considered closed.

---

*Revision produced under Phase C5 content remediation. Verification status and ingestion approval are set by the reviewer, not by this document.*
