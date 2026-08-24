# F5.1 — T7/T8 output + interpretation MVP

Deterministic implementation of the approved F5.0 design, with the F5.1 refinement that MVP generation stays at **Level A / Level B**. No Gemini. No CODIFY. Frozen labels unchanged. F4.1–F4.9 analytics, salience knobs, evidence relationships, and F4.7 gate logic were not redesigned.

## 1. Schema changes

`HealthCoachResult` now distinguishes product surfaces:

| Field | Job |
|---|---|
| `primary_message` | concise prioritized observation |
| `subtext` | optional one-line qualifier |
| `insight` | supporting rationale (JSON key **unchanged**) |
| `recommendation` | action only if F4.7 allows |
| `supporting_metric_facts` | system-stamped F4.1–F4.9 facts |
| existing status / theme / confidence / source_refs / reason_not_surfaced / F4.7 flags | unchanged |

Legacy payloads without the new keys still parse (`primary_message=null`, empty facts).

`user_facing_summary()` uses `format_health_coach_output()`:

```
PRIMARY MESSAGE
SUBTEXT
RATIONALE
RECOMMENDATION
SUPPORTING FACTS
```

Quiet / failure statuses keep their previous short messages.

## 2. Prompt changes

`HEALTH_COACH_INSTRUCTIONS` (and the trend-tool docstring) gained the smallest honor block:

- fill `primary_message` separately from `insight`
- require `primary_message` on INSIGHT / RECOMMENDATION
- quiet path when `insight_worthy=false`
- stay at metric-level or named multi-metric summaries
- do not mint cardiovascular / respiratory / recovery / stress **state** conclusions
- authorized evidence ≠ license for that broader conclusion
- preserve mixed signals by naming metrics
- control metrics bound; they must not become `primary_message`
- spread is structure, not decline/stress
- advice only in `recommendation`, including no leak into primary/subtext/insight
- do not invent `supporting_metric_facts`

Pattern examples that said “cardiovascular indicators remain favorable” were rewritten to named metrics. No directive categories. No canned coaching copy.

## 3. Guard changes

Reliable structural checks only (`app/output_guard.py`):

- INSIGHT / RECOMMENDATION requires non-empty `primary_message`
- `NO_SIGNIFICANT_NEW_PATTERN` may not keep a primary card
- existing F4.7 rec status/field checks
- existing rec-phrase leak scan now also reads `primary_message` and `subtext` via `_guard_text`

No T8 physiological-state phrase dictionary. Broad interpretation remains a future CODIFY / LLM-as-judge item.

Quiet-path **rewrites** (`insight_worthy=false` → status + null primary) live in the output-contract sanitizer, not in the guard. Same pattern as F4.7.

## 4. Supporting-fact stamping

`app/output_contract.py` stamps facts from `get_trend_signals` after the model returns. Gemini’s list, if any, is overwritten.

Roles, from existing fields only:

| Role | Source |
|---|---|
| `primary` | `insight_salience.primary_metrics` when `insight_worthy=true`; never a control |
| `supporting` | other `insight_candidate` rows, or the HRV **level** row when spread is observed |
| `control` | `control_metric=true` / `control_metrics` |
| `spread_context` | HRV `within_window_spread` when `spread_observation_allowed` |

Each level fact copies current/baseline, direction, %, coverage/maturity, candidate/maintenance flags, `origin=deterministic_analytics`, `source=get_trend_signals`. Spread facts copy n/mean/SD/min/max/range/ratio/allow-flags, `origin=deterministic_spread_analytics`.

This is not a second analytics engine.

## 5. Interpretation ceiling

MVP may produce:

- **A.** a metric fact (“Sleep duration decreased about 18% versus the recent baseline.”)
- **B.** a named multi-metric summary (“Resting heart rate, HRV, and VO2 remain improved compared with the earlier personal baseline.”)

MVP must not produce a broad physiological-state conclusion (“cardiovascular health is improving,” “respiratory health is good,” “recovery is poor,” “your body is under stress”). Evidence authorization does not lift that ceiling.

Enforced by prompt + structure. Not by a phrase blacklist.

## 6. Mixed-signal handling

Stamped facts keep **per-metric** directions. There is no collapsed `overall_direction`. Prompt tells the model to name metrics when they disagree.

E1/A1 example (same as-of): sleep `decreasing` −18.0 sits next to HRV `improving` +11.72, exercise `improving` +29.02, RR `stable` control. Compressing that to “cardiovascular indicators remained stable” is prompt-forbidden and later CODIFY, not a regex.

## 7. T6 handling

Respiratory rate is stamped `role=control` only. It is never `primary`. Prompt forbids using it as reassurance or as `primary_message`. Salience still marks it `insight_candidate=false`.

## 8. T12 handling

HRV spread is a separate `spread_context` row. C4: level `improving` +5.56% (`supporting`, not insight-candidate) vs spread ratio **2.61**, min/max 24.7–48.9. Sleep remains a `primary` level story (−10.58%). Spread does not authorize decline/stress/poor recovery/instability.

## 9. Recommendation separation

`apply_recommendation_boundary` is unchanged. Order in the runner:

1. parse model JSON (`raw_model_output`)
2. F4.7 sanitizer
3. output-contract stamp + quiet-path sanitizer
4. guard

If `final_recommendation_allowed=false`, recommendation is null and rec-like language in primary/subtext/insight still fails the existing phrase scan.

## 10. TRACE changes

F4.2 model-call capture is unchanged. No hidden CoT.

New run-level fields:

- `raw_model_output` — structured JSON before sanitizers
- `output_contract` — `insight_worthy`, primary presence, stamped facts, origin `deterministic_output_contract`, quiet-path violations
- `structured_result` / `final_output` — post-sanitizer system output, including `primary_message`, `subtext`, `insight`, `recommendation`, `supporting_metric_facts`
- `generation` also records primary/subtext/recommendation
- `recommendation_boundary` unchanged

## 11. A1 / B1 / B3 / C2 / E1 / C4 offline results

Deterministic stamping on demo seed (2026-08-22). No Gemini.

### A1 — 2026-08-02

- `insight_worthy=true`, `recommendation_worthy=true`
- Sleep is a primary fact: `decreasing` −18.0
- Also stamped primary: exercise +29.02, workouts +21.43, HRV +11.72, steps stable (maintenance_of_decline candidate)
- RR control `stable` −1.67; HRV spread_context ratio 2.21
- Contract: INSIGHT with a sleep `primary_message` keeps rationale separate; invented model facts are dropped
- Rec permission is still F4.7 (architecture may allow). UX of the caffeine latch is unchanged

### B1 — 2026-06-18

- `insight_worthy=false`, `primary_metrics=[]`
- No `primary` facts
- RR control only; HRV supporting+spread because observation is allowed (ratio 1.47), not because it is salient
- Model INSIGHT + primary card is rewritten to `NO_SIGNIFICANT_NEW_PATTERN` with `primary_message=null`

### B3 — 2026-08-17

- `insight_worthy=true`, `recommendation_worthy=false`
- Primary facts: HRV / VO2 / RHR with `maintenance_of_gain=true`; steps is a held decline, not praise
- Named RHR/HRV/VO2 summary is allowed as Level B
- F4.7 still nulls a recommendation field

### C2 — 2026-07-31

- Sleep is primary: `decreasing` −15.42
- Other primaries exist (exercise/workouts/HRV); lifestyle is **not** stamped and has no `cause` field
- Multiple lifestyle events remain in `get_lifestyle_context` only. The contract does not pick a single cause

### E1 — 2026-08-02 (same world state as A1)

- Sleep primary `decreasing` −18.0
- RR `control` `stable` −1.67, not primary
- HRV primary `improving` +11.72 — mixed with sleep; directions are not collapsed
- No respiratory/cardiorespiratory reassurance object exists to mint

### C4 — 2026-07-28

- Sleep primary `decreasing` −10.58
- HRV level `supporting` `improving` +5.56 (not declining, not insight-candidate)
- HRV `spread_context` ratio **2.61**, 24.7–48.9
- Level and spread remain distinct rows

## 12. Focused tests

`tests/test_output_interpretation.py` plus existing guard / F4.7 / schema / prompt-honor / TRACE tests.

Covered: schema compatibility, primary-message requirement, quiet path, rec separation / leak into primary, fact stamping, role assignment, T6 control, T12 spread, mixed-signal directions, TRACE visibility, display order.

Focused related suite: **78 passed**.

## 13. Full pytest

**387 passed** (2026-08-22). Prior baseline was 370; +17 new F5.1 tests.

## 14. Files changed

- `app/output_contract.py` (new)
- `agent/schemas.py`
- `agent/instructions.py`
- `agent/display.py`
- `agent/runner.py`
- `agent/tools.py`
- `app/output_guard.py`
- `evals/trace_schema.py`
- `tests/test_output_interpretation.py` (new)
- `tests/test_recommendation_boundary.py` (primary_message on two existing fixtures)
- `evals/results/assignment4_tracker_v1.md`
- `evals/results/f51_output_interpretation_mvp_v1.md`

F4.1–F4.9 analytics modules, salience knobs, evidence policy, and `apply_recommendation_boundary` logic were not changed.

## 15. Remaining risks

1. **Several `primary` facts.** F4.6 `primary_metrics` is a set. The model must still choose the strongest observation for `primary_message` (sleep on A1/E1/C2/C4). Structure does not pick a single winner. That is prompt + later judge, not a new salience engine.
2. **T8 Level C** is not deterministically blocked. A model can still write “cardiovascular health is stable.” Guard will not catch it.
3. **A1 / E1 / C2 caffeine latch** is unchanged. F4.7 may still permit a recommendation; T7 only separates the fields.
4. **C2 unused confounders** remain a generation/retrieval issue. Facts do not force mentioning late-work/alcohol.
5. **B1 HRV supporting-from-spread** is debug/eval output only (stamped after generation). It must not be read as a new insight.
6. **`insight` semantic shift** for older TRACE consumers: the key still exists, but display no longer treats it as the card title.
7. Streamlit demo still prints Theme / Insight (UI out of scope).

## 16. Recommended targeted Gemini validation

Do **not** run a 15-scenario baseline yet. After this MVP, a targeted live check of:

| Scenario | Look for |
|---|---|
| A1 | sleep `primary_message`; rationale in `insight`; rec only if F4.7 allows and only in `recommendation` |
| B1 | `NO_SIGNIFICANT_NEW_PATTERN`; null primary |
| B3 | named RHR/HRV/VO2 INSIGHT; rec null; no “cardiovascular health improved” requirement |
| C2 | sleep primary; lifestyle stays contextual; no forced single cause |
| E1 | sleep primary; RR not a reassurance card; mixed directions not collapsed |
| C4 | sleep primary; HRV mean not called declining; spread not called stress |

Then CODIFY graders from F5.0 §14.

## Stop

No Gemini. No CODIFY. No directive categories. No frozen-label edits. No commit.
