# F4.7 Recommendation boundary inspection

Deterministic only. No Gemini. Frozen labels unchanged. F4.1/F4.5/F4.6 knobs and RAG `recommendation_eligible` metadata unchanged.

## A. Audit

Before this phase, two independent flags never met:

```
insight_salience.recommendation_worthy     (F4.6 product salience)
        ↓ get_trend_signals payload / TRACE
retrieve_authorized_evidence
        ↓ evidence policy
recommendation_authorized                  (scientific/policy permission)
        ↓ Gemini treated this as enough
structured status / recommendation field
        ↓ output guard used policy authorization only
PASS (B3 rec field survived)
```

**B3 live finding that triggered this:** `insight_worthy=true`, `recommendation_worthy=false`, R-05 `recommendation_authorized=true`, status=`INSIGHT`, recommendation=`Maintain your regular aerobic exercise habit`, guard PASS.

The concepts were independent at Gemini and at the guard.

## B. Combined gate

```
final_recommendation_allowed
    = recommendation_worthy
      AND recommendation_authorized
```

Meanings kept distinct. Upstream fields are not collapsed.

## C. Output semantics

| Case | worthy | authorized | allowed | Output |
|---|---|---|---|---|
| 1 B3 | false | true | false | INSIGHT ok; rec field null |
| 2 | true | false | false | no rec; qualified INSIGHT ok |
| 3 A1 if both true | true | true | true | RECOMMENDATION may be emitted |
| 4 B1 | false | false | false | no rec |

Runner **sanitizes** unauthorized rec status/field rather than discarding a valid INSIGHT.

## D. Insight vs recommendation

Primary enforcement is **structure**: null `recommendation` and block `status=RECOMMENDATION` when the gate is false.

Prose leakage into `insight` is only caught by the existing small `RECOMMENDATION_PHRASES` list (`you should`, `i recommend`, `recommend…`, `maintain your … routine`). B3's actual leak was in the recommendation field, which this gate now strips. A phrase such as “Maintain your regular aerobic exercise habit” inside insight would still not match. That limitation is documented, not over-engineered.

## E–J. Deterministic scenario results

### B3
- `insight_worthy=true`
- `recommendation_worthy=false`
- R-05 `recommendation_authorized=true` (policy unchanged)
- `final_recommendation_allowed=false`
- INSIGHT preserved; recommendation field forced null
- maintenance-of-gain insight remains allowed

### A1
- `insight_worthy=true`
- `recommendation_worthy=true`
- lifestyle inputs include `caffeine_mg` / `alcohol_units`
- R-07 `recommendation_authorized=true`
- `final_recommendation_allowed=true`
- Architecture **permits** RECOMMENDATION. This phase does not judge A1 UX.

### B1
- `insight_worthy=false`
- `recommendation_worthy=false`
- steps/exercise remain `improving` (detectable, not worthy)
- a model RECOMMENDATION would be rewritten to `NO_SIGNIFICANT_NEW_PATTERN`
- F4.7 does not reintroduce B1 surfacing

## TRACE

- Evidence tool returns `recommendation_worthy`, `recommendation_authorized`, `final_recommendation_allowed`
- `recommendation_boundary` on the run TRACE with origins:
  - worthy → `deterministic_salience_analytics`
  - authorized → `evidence_policy`
  - combined → `deterministic_recommendation_boundary`
- F4.2 `recommendation_boundary_visible` on model calls after evidence
- `model_respected_boundary` vs `final_output_respects_boundary`
- No CoT

## Tests

`tests/test_recommendation_boundary.py` (22). Focused related suite 110 passed. Full pytest **337 passed**.
