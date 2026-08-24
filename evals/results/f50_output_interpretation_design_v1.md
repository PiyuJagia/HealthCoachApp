# F5.0 — T7 + T8 Output / Interpretation Contract

**Status:** DESIGN ONLY. No product, prompt, guard, analytics, threshold, RAG, Gemini, CODIFY, frozen-label, or taxonomy changes.

This phase moves from **what the system knows** (F4.1–F4.9) to **what the model may infer** and **how the product communicates it**.

| Cluster | Job |
|---|---|
| **T7** | Directive-first output: Notice → Prioritize → Direct → Explain |
| **T8** | Physiological inference boundary: metric facts ≠ system-health conclusions |

Do **not** treat this document as:

- directive categories
- detailed directive-selection rules
- hard-coded copy
- a giant prohibited-phrase list
- a redesign of F4.7

Working field names below (`primary_message`, `subtext`, `rationale`) are **not final**.

---

## 1. Current output-contract audit

Inspected: `HealthCoachResult` (`agent/schemas.py`), `HEALTH_COACH_INSTRUCTIONS`, `check_final_output` (`app/output_guard.py`), F4.7 (`app/recommendation_boundary.py`), F4.6 salience payload, F4.2 visible inputs, and representative frozen + post-remediation traces (A1, B1, B3, C1/C2, E1, C4).

### 1.1 Schema today

`HealthCoachResult` user-facing / eval fields:

| Field | Role today | Product surface? |
|---|---|---|
| `status` | `INSIGHT` / `RECOMMENDATION` / `NO_SIGNIFICANT_NEW_PATTERN` (+ failure statuses) | routing, not copy |
| `theme` | short title (`Sleep Duration Shortening Across Recent Week`) | report headline |
| `insight` | **the entire user-facing narrative** | yes — currently the primary surface |
| `recommendation` | optional advice | yes, when present |
| `confidence_language` | `HIGH` / `MODERATE` / `LOW` | qualification |
| `source_refs` | chunk / relationship IDs | on-demand |
| `reason_not_surfaced` | factual note when nothing is elevated | quiet path only |
| `policy_verdict` | SURFACE / QUALIFY / SUPPRESS | eval, not copy |
| `recommendation_authorized` | evidence-policy permission | F4.7 input |
| `recommendation_worthy` | F4.6 product flag | F4.7 input |
| `final_recommendation_allowed` | combined gate | F4.7 output |

`user_facing_summary()` concatenates:

```
Theme: …
Insight: …
Recommendation: …
```

That **is** a report layout. There is no field whose job is “one-line priority the user can read without the analysis.”

### 1.2 How the fields relate

```
status
  ├─ NO_SIGNIFICANT_NEW_PATTERN → reason_not_surfaced (insight usually null)
  ├─ INSIGHT                    → theme + insight; recommendation null (F4.7)
  └─ RECOMMENDATION             → theme + insight + recommendation (only if allowed)

confidence_language qualifies the whole blob.
source_refs hang off the blob.
theme labels the blob; it does not prioritize it.
insight contains Notice + Prioritize + Explain, and sometimes a disguised Direct.
```

F4.7 already distinguishes **whether** a recommendation may exist. It does **not** distinguish **where** the observation vs the explanation vs the action live. All three currently collapse into `insight`, with `recommendation` as an optional extra paragraph.

### 1.3 Instructions / generation requirements

The system prompt asks the model to:

1. identify useful **themes** (improvements, declines, recovery, ambiguity, stability, relationships)
2. return a **bounded health insight**, an authorized recommendation, or `NO_SIGNIFICANT_NEW_PATTERN`
3. fill `insight` with a “user-facing insight”
4. honor F4.6 `insight_worthy`, F4.7 `final_recommendation_allowed`, F4.8 control metrics, and F4.9 spread

It does **not** ask for a concise primary surface separate from rationale. Pattern-type examples are analytical (`sleep duration is declining meaningfully`, `cardiovascular indicators remain favorable`). Completeness is rewarded: mixed patterns, numerical comparison, qualification.

Post-F4.6/F4.7/F4.8/F4.9 honor rules are real, but they constrain **eligibility**, not **voice or structure**.

### 1.4 Guard today

Deterministic, testable checks only:

- suppressed relationship IDs
- output while policy SUPPRESS
- F4.7: no `status=RECOMMENDATION` / no recommendation field unless `final_recommendation_allowed`
- leftover rec phrases (`you should`, `i recommend`, `recommend…`, `maintain your … routine`) when not allowed
- causal phrases (`caused`, `led to`, `proves`, …)
- unsupported analytical-method claims

The guard **cannot** currently fail:

- report-like `insight`
- missing priority
- mixed-signal collapse
- “cardiovascular indicators remained stable”
- “respiratory health is good”
- “this indicates stress”

That is correct for a hard guard. T7/T8 quality is not a regex problem.

### 1.5 Representative current copy

| Case | Source | status | What the user actually gets |
|---|---|---|---|
| **A1 frozen** | human bundle | INSIGHT | Theme + long insight: 7.14→5.83 (−18.4%), activity/HRV “stable to slightly improved,” qualified autonomic correlations. No rec (R-07 suppressed). Human **PASS** on grounding; T7: report-first. |
| **A1 live (F4.7)** | `f33a3b61…` | RECOMMENDATION | Insight still a paragraph of numbers + caffeine co-occurrence. Rec: shift caffeine earlier. F4.7 permits. Still not directive-first. |
| **B1 live (F4.8.1)** | `70333797…` | NO_SIGNIFICANT_NEW_PATTERN | `reason_not_surfaced` lists minor steps/exercise and stable sleep/RHR/HRV/RR. Correct T5 honor. No primary card. |
| **B3 live (F4.7)** | `a9a79976…` | INSIGHT | “Your **cardiovascular metrics**—RHR, HRV, and VO2 max—continue to maintain their improved levels…” Rec null. F4.7 honored. Names metrics (safer) but still a report, and “cardiovascular metrics” is a bundling step T8 must watch. |
| **C2 frozen** | human bundle | INSIGHT | Sleep −16.3%; “activity levels and **key cardiovascular indicators** such as RHR and HRV remained relatively stable.” No lifestyle (T1). T8 collapse already present. |
| **C2 live (F4.4)** | `98d41dd1…` | RECOMMENDATION | Sleep numbers + caffeine only. Late-work/alcohol visible, unused. Rec: consume caffeine earlier. Ambiguity collapsed. |
| **E1 frozen** | human bundle | INSIGHT | Sleep decline + “physical activity levels and **cardiovascular indicators have remained stable**” despite HRV improving. Canonical T8. RR invisible (T6, now closed). |
| **E1 live (F4.8.1)** | `0bffd8bc…` | RECOMMENDATION | Sleep 5.8 vs 7.1 + afternoon caffeine. **No** “cardiovascular indicators remained stable.” T8 did not recur on this run. RR visible, unused in prose (allowed). Rec is the A1 caffeine latch, not T6. |
| **C4 frozen** | human bundle | INSIGHT | Sleep 7.24→6.39; “RHR and HRV remained relatively stable.” Did not invent HRV decline (narrow rubric). Could not see spread (T12, now closed). Still report-first. |

### 1.6 Why output is rationale/report-first

Not because Gemini “ignores” the product. The contract **asks for a report**:

1. **One field does three jobs.** `insight` is notice, priority, explanation, mixed-signal inventory, and sometimes a soft directive.
2. **`theme` is a title, not a directive.** “Sleep Duration Shortening Across Recent Week” is catalog copy.
3. **Instructions privilege analytical completeness** over a primary sentence the user can act on without opening the analysis.
4. **`user_facing_summary()` presents Theme / Insight / Recommendation.** Downstream UI and eval read a briefing.
5. **Grounding pressure.** Human review and policy both punish invented causes. The safe model move is to dump visible numbers into `insight`. That passes T2–T5 style checks and fails T7.
6. **Guard and F4.7 check permission, not shape.** A perfect report with a null rec still PASSes.
7. **F4.1–F4.9 expanded what the model can see.** Without a primary/rationale split, more facts make **longer** insights (lifestyle, longitudinal, RR, spread), not sharper ones.

T7 is therefore a **structural** gap, not a missing analytics feature. T8 is a **generation** gap that the new structure must make evaluable.

---

## 2. Product job

```
NOTICE        what changed / is being held
    ↓
PRIORITIZE    which eligible salient signal matters now
    ↓
DIRECT        observation or (only if F4.7 allows) an action
    ↓
EXPLAIN       why, with numbers, caveats, context
```

Eventual UI (not designed here):

| Layer | Job | Lives in |
|---|---|---|
| **PRIMARY SURFACE** | concise, high-impact observation or priority | new short fields |
| **ON-DEMAND EXPLANATION** | rationale, metric facts, coverage/provenance, evidence | rationale + structured facts + refs |

Eval/backend must receive **both** structurally. The primary must be understandable **without** opening the rationale. The rationale must remain inspectable even if the UI hides it.

This phase does **not** define directive categories (celebrate / warn / investigate / maintain / …) and does **not** specify selection rules among them. Status + F4.6 + F4.7 already say whether something may be an INSIGHT, a RECOMMENDATION, or quiet.

---

## 3. Proposed structured output (smallest)

### 3.1 Evolve vs replace

| Existing field | Verdict |
|---|---|
| `status` | **Keep.** Routing. |
| `theme` | **Keep as eval/internal label.** Do not promote it to the primary surface. |
| `insight` | **Do not keep as the primary surface.** Today it is the report. Overloading it as the one-liner would hide rationale from eval. |
| `recommendation` | **Keep.** Only when `final_recommendation_allowed=true`. |
| F4.7 flags | **Keep, unchanged semantics.** |
| `confidence_language` | **Keep.** Qualifies the review, not a hidden score. |
| `source_refs` | **Keep.** |
| `reason_not_surfaced` | **Keep** for `NO_SIGNIFICANT_NEW_PATTERN`. |
| `policy_verdict` | **Keep.** |

**Cleaner fields are needed** for the primary surface. Evolving `insight` in place cannot serve both “one-line priority” and “supporting rationale.”

Recommended MVP (working names):

```
status
theme                         # optional internal/eval label
primary_message               # PRIMARY SURFACE (null when not insight-worthy)
subtext                       # optional one-line qualifier
insight                       # ON-DEMAND rationale (same JSON key; new meaning)
recommendation                # null unless final_recommendation_allowed
supporting_metric_facts       # system-stamped; not model-invented
confidence_language
source_refs
reason_not_surfaced
recommendation_worthy
recommendation_authorized
final_recommendation_allowed
policy_verdict
```

Compatibility: keep the JSON key `insight` in MVP so TRACE / parsers do not fork. Document that **`insight` becomes rationale**, not the card title. A later rename to `rationale` can alias `insight`. Do not require both `insight` and `rationale` in MVP.

### 3.2 Field jobs

**`primary_message`** (model-authored, short)

- Brief, specific, prioritized.
- Faithful to the strongest **eligible salient** signal (`insight_worthy` + `insight_candidate` / `primary_metrics` / maintenance flags).
- Understandable without the rationale.
- Not a string of numbers, not a theme title, not a recommendation.
- Null when `insight_worthy=false` (B1). Do not invent a quiet-period “you’re doing great” card.

**`subtext`** (optional, model-authored, one line)

- Magnitude or qualifier the card may show under the primary (`Down about 18% across the available week`).
- Still not the explanation dump.
- Null when it would only repeat the primary or when status is quiet.

**`insight` / rationale** (model-authored)

- Why the primary is warranted.
- May include numerical comparison, coverage, maturity, lifestyle co-occurrence, evidence relationship, control observations, longitudinal context, within-window spread.
- Must not become a data dump of every visible metric.
- Must not hide advice when `final_recommendation_allowed=false`.

**`recommendation`** (model-authored, F4.7)

- The Direct **action**, only if allowed.
- Never duplicated as a workaround inside `primary_message`, `subtext`, or `insight`.
- When allowed=true, the model **may** emit it; F4.7 does not require it. UX of A1/C2/E1 caffeine latch remains an open product question (see §14).

**`supporting_metric_facts`** (system-stamped from F4.1–F4.9)

Do **not** ask Gemini to invent this list. Stamp it from `get_trend_signals` after the run (or attach the already-visible payload slice). Each row carries a **role** derived from existing contracts:

| Role | Source | Use |
|---|---|---|
| `primary` | `insight_salience.primary_metrics` / `insight_candidate` that the review is actually about | primary evidence |
| `supporting` | other eligible visible facts (other candidates, lifestyle summary, authorized relationship ids) | supporting evidence |
| `control` | `control_metric=true` (F4.8 RR) | bounding context |
| `spread_context` | HRV `within_window_spread` when observation/comparison flags allow | T12 context, not a second primary |

Facts stay metric-level (direction, current, baseline, %, coverage, allow-flags). This is the structured “metrics” layer the UI/eval can show without parsing prose.

MVP size: stamp the **salient + control + spread** slice, not all eight metrics as a wall. Quiet metrics can remain in the raw tool payload / TRACE.

### 3.3 What this is not

- Not directive categories.
- Not a second salience engine.
- Not a new recommendation policy.
- Not UI components.
- Not a requirement that every INSIGHT contain a recommendation-shaped imperative. An observation **is** a valid primary (`Sleep needs attention.`).

### 3.4 `user_facing_summary()` (future)

Primary + optional subtext. Recommendation only if present. Rationale is available on demand / in TRACE, not prepended as `Insight:`.

---

## 4. Notice → Prioritize → Direct → Explain mapping

| Step | Who decides | Where it lives | What it is not |
|---|---|---|---|
| **Notice** | Model, constrained by F4.1 eligibility + F4.6 `insight_worthy` | `primary_message` | a metric table |
| **Prioritize** | Model, constrained by `primary_metrics` / `insight_candidate` / maintenance flags | same primary (one priority); optional `subtext` for the magnitude | averaging mixed signals into one system label |
| **Direct** | Observation always; **action** only if F4.7 `final_recommendation_allowed` | observation → `primary_message`; action → `recommendation` | advice inside rationale |
| **Explain** | Model, grounded in visible F4.2 inputs | `insight` (rationale) + stamped facts + `source_refs` + confidence | the thing the user must read first |

Quiet path (`insight_worthy=false`): skip Notice/Prioritize/Direct. `status=NO_SIGNIFICANT_NEW_PATTERN`. `reason_not_surfaced` may factually mention detectable-but-unworthy direction. That is Explain-without-a-card, not a reassurance directive.

---

## 5. T8 inference hierarchy

Three levels. Climbing a level requires **more** than more numbers.

### A. Metric-level fact

A statement about **one** published metric (or one published spread object), using that row’s allow-flags.

Examples:

- Sleep decreased from ~7.1 h to ~5.8 h (−18%).
- RHR is stable (+0.18%).
- HRV **mean** is improving (+5.56% / +11.72% depending on as-of).
- RR is stable (14.3 vs 14.54, control).
- HRV day-to-day spread is larger than this person’s F4.1 baseline (ratio 2.61), while the mean is not declining.

**Permitted when:** the corresponding F4.1 / F4.3 / F4.5 / F4.9 flag allows that claim (`trend_allowed`, snapshot/early-pattern rules, `spread_comparison_allowed`, etc.). Missingness weakens; it does not invent a fact.

**Not a diagnosis.** “Sleep decreased” ≠ “you have insomnia.” “HRV spread rose” ≠ “you are stressed.”

### B. Multi-metric summary

A **list** of metric-level facts that remain distinct. Directions may differ. Concordant facts may be grouped **by naming the metrics**, not by inventing a body-system verdict.

Allowed conceptually:

- “Sleep declined, while RHR stayed stable and HRV improved.”
- B3: “Resting heart rate, HRV, and VO2 max remain improved versus your earlier long-term baseline.” (three `maintenance_of_gain` flags, named)

Not allowed as a B-summary:

- Collapsing mixed directions into one direction (`cardiovascular indicators remained stable` while HRV is improving and sleep is falling).
- Treating a control metric as equal to the salient change.
- Treating spread as if it were a mean decline.

**Permitted when:** every component is an allowed A-fact, and disagreement is preserved.

B is still observational. It is not “cardiovascular health.”

### C. Physiological interpretation

An abstraction that names a **health state, system, or mechanism** beyond the published metric labels.

Examples (not authorized by facts alone):

- “Cardiovascular health is stable / good / unstable.”
- “Respiratory health is good.”
- “Cardiorespiratory health is stable.”
- “You are stressed.” / “Your recovery is poor.”
- “Your autonomic system is dysfunctional.”

**Permitted only if all of:**

1. Authorized evidence actually supports **that** relationship (not merely any nearby R-id).
2. Policy allows the claim at the stated strength (SURFACE vs QUALIFY). `QUALIFY` may mention association; it does not mint a diagnosis.
3. The named metrics **agree** enough to bear the abstraction. Mixed sleep-down / HRV-up / RHR-stable / RR-stable does **not**.
4. The interpretation is **not** licensed by a control metric alone (T6).
5. The interpretation is **not** licensed by spread alone (T12).
6. Language stays association-grade. Causation remains forbidden (existing guard).

If those conditions fail, stay at A or B.

```
A  metric fact          ← default
B  named multi-metric   ← only if each A is allowed and disagreement is kept
C  physiological call   ← evidence + policy + concordance; never from control or spread alone
```

T8 does **not** need a new analytics object. F4.1–F4.9 already expose the facts. T8 constrains **inference from those facts**.

---

## 6. Mixed-signal rules

Canonical mixed packet (E1 / A1 as-of 2026-08-02, current contract):

| Metric | Direction | Role |
|---|---|---|
| Sleep | decreasing −18% | primary / insight candidate |
| RHR | stable | not candidate |
| HRV | improving | candidate, **not** the priority vs sleep |
| Exercise | improving | candidate |
| RR | stable | **control**, not candidate |
| VO2 | stable | not candidate |

**Must not compress to:**

- “Your cardiovascular indicators remained stable.”
- “Your recovery is deteriorating.”
- “Your cardiorespiratory health is stable.”

**Prefer:** metric-specific language. Sleep is the priority. Other rows are supporting or control, stated as themselves.

### Does T8 need extra output-validation?

| Need | Already exists? |
|---|---|
| Per-metric direction, %, coverage, maturity | F4.1 |
| Which metric is insight-worthy | F4.6 `insight_candidate`, `primary_metrics` |
| Control vs signal | F4.8 `control_metric` |
| Level vs spread | F4.9 `within_window_spread` |
| Lifestyle co-occurrence without causation | F4.4 |
| Rec permission | F4.7 |

**Inputs are sufficient.** What is missing is **output structure + generation constraint + later graders**, not another trend engine.

Do **not** add:

- a giant banned-phrase list
- a deterministic “mixedness score”
- a new physiological-interpretation flag the analytics invents (that would be a fake C-license)

Optional later (not MVP): if `supporting_metric_facts` show **discordant** directions among non-control metrics, a **CODIFY** grader (LLM-as-judge) checks that prose did not emit a single-system verdict. That is evaluation, not a new contract object.

---

## 7. T12 interaction

T12 provides **structure**. T8 controls **interpretation**.

Visible on C4 (2026-07-28):

- HRV **level:** improving +5.56% (not declining); `insight_candidate=false`
- HRV **spread:** sample SD 10.25 vs baseline 3.94, ratio **2.61**, min/max 24.7 / 48.9, comparison allowed
- Sleep **level:** decreasing −10.58%, insight candidate — still the level story

| Allowed (A/B) | Not allowed (C, or false A) |
|---|---|
| “Average HRV has not declined, although readings have varied more than your recent baseline.” | “HRV is declining.” |
| Publish min/max as facts in rationale / stamped facts | “This indicates stress.” |
| Keep sleep as the primary if it is the salient level change | “Your recovery is poor.” |
| Say nothing about spread if the card is correctly about sleep, as long as HRV is not called a decline | “Your cardiovascular system is unstable.” |

Primary message for C4 should follow **sleep** (eligible salient level), not spread. Spread is Explain / `spread_context`, never a backdoor INSIGHT (F4.9 salience rule unchanged).

Honor `spread_comparison_allowed` before “more than your usual.” If false, describe current min/max only, or omit the comparison.

---

## 8. T6 control-metric interaction

Stable control metrics **bound** a conclusion. They do **not** independently create reassurance.

E1: sleep decline + RR stable (−1.67%, 14.3 vs 14.54, `control_metric=true`, `insight_candidate=false`).

| Allowed | Not automatically allowed |
|---|---|
| Sleep is the more specific change in the available data | “Respiratory health is normal / good” |
| Optional rationale: RR remained stable as bounding context | “Cardiorespiratory health is stable” |
| Omit RR from prose entirely (live E1 did; allowed) | Promote RR into `primary_message` |
| Use RR to **avoid** a whole-system story | Treat stable RR as proof that sleep decline is harmless |

B1: RR stable must not reopen T5 or mint a wellness card.

---

## 9. Recommendation-boundary interaction

F4.7 remains authoritative. Do not redesign it.

```
final_recommendation_allowed
  = recommendation_worthy AND recommendation_authorized
```

| `allowed` | Primary | Rationale | `recommendation` | status |
|---|---|---|---|---|
| false, `insight_worthy=true` | useful **INSIGHT** / observation | may explain | **null** | `INSIGHT` |
| false, `insight_worthy=false` | **null** | `reason_not_surfaced` only | **null** | `NO_SIGNIFICANT_NEW_PATTERN` |
| true | still the observation/priority | may explain | **may** be filled | `RECOMMENDATION` only if a rec is actually emitted |

Hard rules:

- If `allowed=false`, no recommendation field.
- Do not hide advice in `primary_message`, `subtext`, or `insight`.
- Do not put the action in `primary_message` even when `allowed=true`. Keep Direct-as-action in `recommendation` so F4.7 stays a **field** check.
- F4.7 still does not **require** a recommendation when allowed (A1/C2/E1 UX remains open).

Extend the existing rec-phrase scan to the new primary/subtext/rationale fields. Do not grow a new blacklist for T8.

---

## 10. Representative output shapes

Shapes, **not** mandatory copy. Wording is illustrative.

### A1 — large sleep decline + caffeine/evidence path

| | |
|---|---|
| **Primary signal** | Sleep −18% / ~−1.28 h (`insight_candidate`, high salience) |
| **status** | `INSIGHT` or `RECOMMENDATION` if F4.7 both-true **and** model emits a rec (architecture permits; UX not decided here) |
| **primary-message role** | Notice + prioritize sleep. Not a caffeine lecture. Not a metric dump. |
| **subtext role** | Magnitude across the available week. |
| **rationale role** | 7.1→5.8 h; mixed/stable/improving neighbors; caffeine **co-occurs**; late-work may be named as additional context without ranking a cause |
| **recommendation allowed?** | **Yes** on current F4.4+F4.7 path (R-07 + lifestyle inputs). Whether it *should* fire is a later product question. |
| **T8** | Do not call cardiovascular/recovery “stable” or “good.” HRV improving is an A-fact, not “health is fine.” Sleep decline is not “your physiology is collapsing.” |

### B1 — low salience → `NO_SIGNIFICANT_NEW_PATTERN`

| | |
|---|---|
| **Primary signal** | None. Steps/exercise detectable, not insight-worthy. |
| **status** | `NO_SIGNIFICANT_NEW_PATTERN` |
| **primary-message role** | **null** (no card) |
| **rationale role** | `reason_not_surfaced` may note minor activity and otherwise stable rows, including RR as a fact — not an INSIGHT |
| **recommendation allowed?** | **No** |
| **T8** | Do not convert “everything is pretty quiet” into “your health is good” / “respiratory health is normal.” |

### B3 — `maintenance_of_gain` INSIGHT, no recommendation

| | |
|---|---|
| **Primary signal** | Held RHR / HRV / VO2 vs older prefix (F4.5 + F4.6). Exercise still recent improving (not the maintenance story). Steps = held decline, not praise. |
| **status** | `INSIGHT` |
| **primary-message role** | Notice that prior gains are being held. Not a celebration category. Not “keep doing X.” |
| **rationale role** | Named metrics + older-reference deltas; recent 7-vs-60 stable; steps as separate A-fact if mentioned |
| **recommendation allowed?** | **No** (`recommendation_worthy=false` even if R-05 authorizes) |
| **T8** | Naming RHR+HRV+VO2 as held (B) is allowed. “Cardiovascular health is good / stable” (C) is not licensed by maintenance flags alone. Do not smuggle “maintain your aerobic routine” into primary or rationale. |

### C2 — multiple lifestyle factors; caffeine relationship surfaced

| | |
|---|---|
| **Primary signal** | Sleep decline (same family as A1, earlier as-of) |
| **status** | `INSIGHT` preferred for ambiguity; live F4.4 emitted `RECOMMENDATION` via R-07 latch — structure must not *require* that latch |
| **primary-message role** | Sleep priority. Not “fix caffeine.” |
| **rationale role** | Sleep numbers **plus** co-occurring caffeine, late-work, alcohol as **unordered** context. Evidence may surface R-07 as *a* relationship, not *the* cause. |
| **recommendation allowed?** | Architecture may say true if R-07 + worthy; **product intent is to preserve ambiguity.** If a rec is emitted, it still must not erase other visible factors from rationale. |
| **T8** | No single-cause physiological story. No “cardiovascular indicators remained stable” wrap-up (frozen C2). |

### E1 — sleep decline + stable RR control

| | |
|---|---|
| **Primary signal** | Sleep −18% |
| **status** | Same F4.7/A1 latch as live E1 if caffeine path fires; T6 success does **not** depend on rec vs insight |
| **primary-message role** | Sleep. |
| **rationale role** | Mixed neighbors as A-facts; RR optional as **control** bound (“sleep is the more specific change”) |
| **recommendation allowed?** | Same as A1 on this as-of. Orthogonal to T6/T8. |
| **T8** | Frozen failure mode forbidden: “cardiovascular indicators have remained stable.” Stable RR ≠ respiratory/cardiorespiratory wellness. |

### C4 — HRV level vs spread

| | |
|---|---|
| **Primary signal** | Sleep level (−10.58%), not HRV spread |
| **status** | `INSIGHT` (sleep worthy); rec only if F4.7 independently allows |
| **primary-message role** | Sleep. |
| **rationale role** | Sleep comparison; HRV mean not declining; spread 2.61× / 24.7–48.9 as `spread_context` if mentioned |
| **recommendation allowed?** | Unchanged F4.7; spread never authorizes |
| **T8** | Level ≠ spread. No HRV decline, stress, poor recovery, cardiovascular instability. |

---

## 11. Prompt responsibilities

Prompt tells the model **how to prioritize and speak allowed facts**. It does not enforce field presence by itself.

Honor existing F4.6–F4.9 rules, plus smallest T7/T8 additions:

1. Put the priority in `primary_message`; put the analysis in `insight`.
2. `primary_message` is short, specific, and not a number dump.
3. When directions differ, stay at metric-level language (A/B). Do not mint a system-health sentence.
4. Control metrics bound; they do not reassure.
5. Spread is not a mean change and not a diagnosis.
6. Advice only in `recommendation`, and only if `final_recommendation_allowed`.
7. When `insight_worthy=false`, emit the quiet status; do not write a wellness primary.
8. Do not invent physiological interpretations (level C) without authorized evidence that actually supports them.

Do **not** encode directive categories or canned sentences in the prompt.

---

## 12. Structured-schema responsibilities

Schema makes Notice / Explain / action **distinguishable** so eval and UI do not parse one paragraph.

| Requirement | Schema |
|---|---|
| Concise primary exists when insight-worthy | `primary_message` required for `INSIGHT` / `RECOMMENDATION` |
| Quiet path has no fake card | `primary_message` null on `NO_SIGNIFICANT_NEW_PATTERN` |
| Rationale inspectable | `insight` retained as explanation |
| Rec separable and F4.7-checkable | existing `recommendation` + flags |
| Metric facts not only in prose | system-stamped `supporting_metric_facts` with roles |
| Confidence / sources | existing fields |
| Internal label | `theme` optional |

Structural requirements must **not** live only as prose instructions. If the primary is missing, that is a schema/guard miss, not a style nit.

---

## 13. Guard responsibilities

Guard enforces **hard, reliable** boundaries. It should not become an NLP interpreter.

**Keep (extend field coverage to primary/subtext/insight/recommendation):**

- F4.7 status/field gate
- existing rec-phrase leak check when `allowed=false`
- causal phrases
- suppressed IDs / modifier-only IDs
- unsupported method claims

**Add (small, checkable):**

- `INSIGHT` / `RECOMMENDATION` without a non-empty `primary_message`
- `NO_SIGNIFICANT_NEW_PATTERN` with a non-empty `primary_message` (optional but useful)
- `recommendation` present or `status=RECOMMENDATION` when `allowed=false` (already)

**Do not put in the guard:**

- T8 physiological semantics (“cardiovascular health is stable”)
- mixed-signal collapse
- concision / directive-first quality
- whether A1 *should* recommend caffeine
- C2 ambiguity preservation
- T12 “did they confuse level and spread” except a **narrow** false-A check: if published HRV direction is not declining, prose in scanned fields matching a tiny existing-style pattern for “HRV … declin” could be considered later — still easy to get wrong. Prefer CODIFY.

Do not solve T8 with a phrase dictionary.

---

## 14. Future CODIFY grader map

Identify only. **Do not implement.**

| Future grader | Why | Class |
|---|---|---|
| `primary_message` present iff `insight_worthy=true` and status is INSIGHT/RECOMMENDATION | T7 structure | **deterministic** |
| B1 / `insight_worthy=false` is not `INSIGHT` or `RECOMMENDATION` | T5 honor | **deterministic** |
| F4.7: rec field/status iff `final_recommendation_allowed` | already system-enforced; still grade traces | **deterministic** |
| Rec-like advice absent from primary/subtext/insight when `allowed=false` | leak | **deterministic** (existing phrases) + **human** for novel wording |
| `primary_message` is short (e.g. char/sentence cap) | anti-report | **deterministic** (length only) + **LLM-as-judge** / **human** for quality |
| Primary faithful to strongest eligible salient signal (not a random secondary) | T7 prioritize | **LLM-as-judge** (primary_metrics as hint) + **human** |
| Rationale grounded in F4.2-visible numbers / flags | no invented means | **LLM-as-judge** with visible payload; light **deterministic** (cited numbers ⊆ visible set) is possible later |
| No unsupported physiological generalization (level C) | T8 | **LLM-as-judge** + **human** |
| Mixed signals not collapsed to one direction/system | T8 / E1 | **LLM-as-judge** + **human** |
| T12: mean not called declining when direction isn’t; spread not called stress/recovery/instability | T12+T8 | **LLM-as-judge**; optional **deterministic** contradiction vs published `direction` |
| T6: stable RR not converted to respiratory/cardiorespiratory reassurance | T6+T8 | **LLM-as-judge** + **human** |
| Missing-data / coverage caveats when `gap_caveat_required` / partial coverage / early pattern | F4.1/F4.3 | **deterministic** flags present + **LLM-as-judge** that prose honors them |
| Association ≠ causation | already guard | **deterministic** + **human** for paraphrase |
| C2-style unused confounders | not T7 core | **LLM-as-judge** / **human** — do not block F5.0 MVP |

Primary-message “directive-first quality” is **not** fully deterministic. Length caps catch dumps; voice needs a judge or a human.

---

## 15. Risks / open questions

1. **`insight` semantic shift.** TRACE, demos, and tests treat `insight` as the user-facing blob. MVP must update `user_facing_summary` / Streamlit **in the implementation phase**, not now. Alias vs rename is the main compatibility choice.
2. **A1 / E1 / C2 caffeine latch.** F4.7 *permits* a rec when both gates are true. T7 structure will make the rec more visually dominant. This design does **not** decide whether that rec is the right product. Separate UX/policy question.
3. **C2 ambiguity** is generation/retrieval (R-07-only query), not solved by new fields. Structure can *host* unordered lifestyle facts; it cannot force Gemini to retrieve or mention them.
4. **B3 “cardiovascular metrics”** sits on the B/C border. Named metrics + maintenance_of_gain = B. “Cardiovascular health/fitness is good” = C. Prompt examples must not push the latter.
5. **More visible facts → longer rationale.** Stamped `supporting_metric_facts` should reduce the urge to paste every row into prose. Still a prompt-quality risk.
6. **Guard overreach.** Tempting to ban “cardiovascular.” That would punish legitimate B-summaries and R-05 exercise copy. Don’t.
7. **Primary becomes a number string** (`Sleep −18.37% (5.83 vs 7.14)`). Length grader ≠ quality. LLM-as-judge later.
8. **Advice in primary when allowed=true.** If UI shows only `primary_message`, users might miss the rec — or authors might stuff the rec into primary. Implementation should show primary **and** rec on the card when both exist; eval should treat rec-in-primary as a leak even when allowed (duplicate channel). Open: whether to guard that strictly.
9. **Quiet-path copy.** `reason_not_surfaced` can still sound like a wellness report. Keep it eval/debug-facing unless product later wants a calm empty state.
10. **No Gemini in this phase.** Live T8 recurrence is currently **absent** on E1 F4.8.1; frozen E1 still shows the failure. Design against both. Do not treat one live run as T8 closed.
11. **Directive categories** were explicitly out of scope. A later T7 copy system could add them; F5.0 must not.

---

## 16. Recommended MVP implementation (next phase, not now)

Smallest balanced slice after this design is approved:

1. **Schema:** add `primary_message`, optional `subtext`; keep `insight` as rationale; keep F4.7 fields; stamp `supporting_metric_facts` from existing salience/control/spread (no new knobs).
2. **Prompt:** smallest honor block for field jobs + T8 A/B/C + mixed signals + T6/T12 (no categories, no canned copy).
3. **Guard:** require `primary_message` on INSIGHT/RECOMMENDATION; extend rec/causal scans to new fields; **no** T8 phrase list.
4. **Display:** `user_facing_summary()` = primary + subtext (+ rec if any).
5. **Tests:** parse/defaults; B1 null primary; B3 rec still stripped; A1 primary allowed with/without rec; mixed-signal facts stamp roles; no analytics/threshold/RAG changes.
6. **Stop.** No Gemini rerun, no CODIFY implementation, no frozen-label edits, no directive taxonomy.

**Out of scope for that MVP:** UI mockups, caffeine-latch policy, C2 retrieval strategy, physiological-interpretation classifier, spread salience, extra metrics’ spread objects.

**Suggested review decisions before coding:**

- Keep JSON key `insight` as rationale (yes/no).
- System-stamp metric facts rather than model-author them (yes — recommended).
- Guard T8 with phrases (no — recommended).
- Treat A1 rec permission as unchanged F4.7 (yes).

---

## Stop

Design only. No implementation, no Gemini, no CODIFY, no directive categories, no frozen eval edits, no commit.
