# Remediation Priority v1

Prioritization from F3 cluster analysis (frequency × product impact × architectural leverage).

## Priority ranking

### P0 — Must address before trusting eval behavior
- **T1** Lifestyle context inaccessible (C1, C2, C3; blocks Family C intent)
- **T2** As-of-date provenance gap (D1, D2; missingness invisible)
- **T3** data_sufficient not enforced (D3; eligibility metadata only)

### P1 — High-value architecture improvements
- **T4** Longitudinal maintenance blind spot (B3)
- **T5** Low-salience insight surfacing (B1)
- **T6** Control metric excluded from contract (E1)
- **T12** Within-window variability not exposed (C4)

### P2 — Important but lower immediate priority
- **T7** Directive-first output gap (PASS scenarios A1/A2/A4)
- **T8** Physiological over-generalization (E1 secondary)
- **T10** Eval scenario design mismatch (B2)

### P3 — Polish / future
- **T9** Redundant evidence retrieval (A1/A4 secondary)
- **T11** Eval overlap / ambiguous discrimination (A3)

## Remediation themes

### Lifestyle context tool + policy input wiring
- Clusters: T1
- Scenarios: HC-EVAL-C1, HC-EVAL-C2, HC-EVAL-C3

### Analytics/tool data contract (as-of provenance)
- Clusters: T2
- Scenarios: HC-EVAL-D1, HC-EVAL-D2

### Deterministic eligibility control for data_sufficient
- Clusters: T3
- Scenarios: HC-EVAL-D3

### Longitudinal context beyond rolling 7/30 windows
- Clusters: T4
- Scenarios: HC-EVAL-B3

### Product salience / insight-worthiness gate
- Clusters: T5
- Scenarios: HC-EVAL-B1

### Control-metric exposure in analytics contract
- Clusters: T6
- Scenarios: HC-EVAL-E1

### Within-window variability in analytics contract
- Clusters: T12
- Scenarios: HC-EVAL-C4

### Directive-first output contract / generation grounding
- Clusters: T7, T8
- Scenarios: HC-EVAL-A1, HC-EVAL-A2, HC-EVAL-A4, HC-EVAL-E1

### Eval dataset refinement
- Clusters: T10, T11
- Scenarios: HC-EVAL-B2, HC-EVAL-A3

## Highest-leverage changes (3–5) before rerun

1. **Add lifestyle context tool** (`get_lifestyle_context`) and wire caffeine/alcohol/mood into evidence-policy `available_inputs` → addresses T1 (C1/C2/C3).
2. **Extend trend contract with as-of provenance** (`as_of_date_available`, `as_of_date_value`, missing counts, latest observation date) → addresses T2 (D1/D2).
3. **Enforce data_sufficient as eligibility gate** in tools, evidence path, and/or output guard → addresses T3 (D3).
4. **Add longitudinal maintenance signal** (phase-aware or longer-horizon comparison) → addresses T4 (B3).
5. **Expose selected control metrics + salience gate** (respiratory_rate read-only; insight-worthiness threshold) → addresses T6 (E1) and T5 (B1).

Related P1 contract gap: expose within-window variability (standard deviation, range, or volatility) on metrics already in `get_trend_signals` → addresses T12 (C4). Redesign the C4 eval after that signal exists; the original negative rubric (do not invent an HRV decline) already passed.

Directive-first output formatting (T7) is high product value but likely follows once grounding/contracts are corrected.
