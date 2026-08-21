# Failure Taxonomy v1 — Baseline Human Review Clustering

Derived bottom-up from completed human open-coding in
`evals/results/baseline_human_review_bundle_v1.md`.

**Source of truth (human reviews):** `evals/results/baseline_human_review_bundle_v1.md`
**Machine-readable extract:** `evals/results/baseline_human_review_extract_v1.json` (verified against markdown).

**Baseline outcome:** 5 PASS / 10 FAIL (n=15)
**PASS rate:** 33.3% | **FAIL rate:** 66.7%

## Review matrix (compact)

| scenario_id | family | PASS/FAIL | originating layer | open-coding summary |
|-------------|--------|-----------|-------------------|---------------------|
| HC-EVAL-A1 | A | PASS | generation | PASS on signal detection, evidence grounding, policy compliance, and rationale accuracy. Product-... |
| HC-EVAL-A2 | A | PASS | generation | Agent correctly identified the strong exercise-consistency improvement and connected it with conc... |
| HC-EVAL-A3 | A | PASS | product limitation | Agent correctly recognized the concurrent improvement in resting heart rate, HRV, exercise consis... |
| HC-EVAL-A4 | A | PASS | generation | Agent correctly prioritized the substantial sleep decline and did not overinterpret the small RHR... |
| HC-EVAL-B1 | B | FAIL | agent trajectory / tool selection; product limitation | Agent accurately identified the modest increase in steps and exercise minutes and correctly descr... |
| HC-EVAL-B2 | B | PASS | data / synthetic scenario | The scenario premise appears weak. Although the rolling sleep comparison suggests a prior decline... |
| HC-EVAL-B3 | B | FAIL | — | The agent correctly recognized that the recent 7-day metrics were stable relative to the rolling ... |
| HC-EVAL-C1 | C | FAIL | product limitation | The C1 scenario is well supported by the underlying Marcus data: seven afternoon caffeine events ... |
| HC-EVAL-C2 | C | FAIL | product limitation | he agent correctly identified the substantial sleep decline and appropriately avoided unsupported... |
| HC-EVAL-C3 | C | FAIL | product limitation | C3 was intended to test whether the agent can observe caffeine use while sleep remains stable and... |
| HC-EVAL-C4 | C | FAIL | product limitation | C4 was intended to test whether the agent could distinguish HRV volatility from a meaningful decl... |
| HC-EVAL-D1 | D | FAIL | deterministic analytics | The rolling HRV calculation was mathematically correct: the 7-day average of 34.32 ms was calcula... |
| HC-EVAL-D2 | D | FAIL | deterministic analytics | D2 confirms the provenance gap identified in D1 at a broader scale. On 2026-06-10, all core weara... |
| HC-EVAL-D3 | D | FAIL | product limitation | The agent correctly avoided making any VO₂-specific claim, even though VO₂ was present in the too... |
| HC-EVAL-E1 | E | FAIL | product limitation | E1 was intended to test whether the agent could use a stable respiratory-rate control metric to a... |

**Uncoded FAIL scenarios:** none. HC-EVAL-C3 is clustered as T1; HC-EVAL-C4 is clustered as T12.

## Derived taxonomy clusters

### T1 — Lifestyle context inaccessible to agent

**Definition:** User-specific lifestyle/context events exist in SQLite but no ADK tool exposes them; personalized ambiguity-preserving reasoning cannot occur.

**Category:** PRODUCT
**Likely layer(s):** product limitation
**Root cause class:** ROOT CAUSE
**Priority:** P0

- **Primary scenarios:** HC-EVAL-C1, HC-EVAL-C2, HC-EVAL-C3
- **Secondary scenarios:** —
- **Human evidence:** C1: 'cannot access lifestyle events' / C2: 'neither was available to the ADK agent' / C3: 'no access to lifestyle events, including caffeine'

### T2 — As-of-date measurement provenance gap

**Definition:** Rolling trend aggregates are returned without indicating whether the as-of-date measurement is missing; sync gaps and partial missingness are invisible to the model.

**Category:** PRODUCT
**Likely layer(s):** deterministic analytics
**Root cause class:** ROOT CAUSE
**Priority:** P0

- **Primary scenarios:** HC-EVAL-D1, HC-EVAL-D2
- **Secondary scenarios:** —
- **Human evidence:** D1: 'measurement-level provenance was lost' / D2: 'Complete sync gap invisible to agent'

### T3 — data_sufficient not enforced

**Definition:** data_sufficient=false is advisory metadata only; insufficient metrics still support insights, evidence retrieval (meaningful_signal=true), and confident generation.

**Category:** PRODUCT
**Likely layer(s):** product limitation
**Root cause class:** ROOT CAUSE
**Priority:** P0

- **Primary scenarios:** HC-EVAL-D3
- **Secondary scenarios:** —
- **Human evidence:** D3: 'data_sufficient is currently advisory metadata rather than an enforced eligibility control'

### T4 — Longitudinal maintenance blind spot

**Definition:** Rolling 7-day vs 30-day comparison cannot distinguish maintained prior improvement from absence of new pattern; sustained gains may be reported as NO_SIGNIFICANT_NEW_PATTERN.

**Category:** PRODUCT
**Likely layer(s):** deterministic analytics; product limitation
**Root cause class:** ROOT CAUSE
**Priority:** P1

- **Primary scenarios:** HC-EVAL-B3
- **Secondary scenarios:** —
- **Human evidence:** B3: 'sustained improvement as no significant new pattern'

### T5 — Low-salience insight surfacing

**Definition:** Agent elevates modest isolated metric movement into INSIGHT during broadly stable periods without a product-level salience gate beyond deterministic direction flags.

**Category:** PRODUCT
**Likely layer(s):** agent trajectory / tool selection; product limitation
**Root cause class:** MIXED
**Priority:** P1

- **Primary scenarios:** HC-EVAL-B1
- **Secondary scenarios:** —
- **Human evidence:** B1: 'elevated a modest isolated increase in steps into an INSIGHT'

### T6 — Control metric excluded from agent contract

**Definition:** Non-signal control metrics (e.g., respiratory_rate) exist in raw data but are omitted from analytics and get_trend_signals, preventing intended bounding of interpretation.

**Category:** PRODUCT
**Likely layer(s):** deterministic analytics; product limitation
**Root cause class:** ROOT CAUSE
**Priority:** P1

- **Primary scenarios:** HC-EVAL-E1
- **Secondary scenarios:** —
- **Human evidence:** E1: 'excluded from the deterministic trend engine and therefore never reaches the ADK agent'

### T7 — Directive-first output contract gap

**Definition:** Final responses are analytically grounded but report-like; they do not follow the intended Notice → Prioritize → Direct → Explain product structure even when policy/guard pass.

**Category:** PRODUCT
**Likely layer(s):** generation
**Root cause class:** DOWNSTREAM SYMPTOM
**Priority:** P2

- **Primary scenarios:** —
- **Secondary scenarios:** HC-EVAL-A1, HC-EVAL-A2, HC-EVAL-A4
- **Human evidence:** A1/A2/A4: 'report-like rather than directive-first Health Coach output'

### T8 — Physiological over-generalization in generation

**Definition:** Model bundles heterogeneous metric directions into broad stable/cardiovascular summaries not fully supported by tool outputs.

**Category:** PRODUCT
**Likely layer(s):** generation
**Root cause class:** DOWNSTREAM SYMPTOM
**Priority:** P2

- **Primary scenarios:** —
- **Secondary scenarios:** HC-EVAL-E1
- **Human evidence:** E1: 'cardiovascular indicators have remained stable' despite HRV improving

### T9 — Redundant evidence retrieval

**Definition:** Agent performs additional evidence lookups after sufficient authorized evidence already exists for a bounded non-recommendation insight.

**Category:** PRODUCT
**Likely layer(s):** agent trajectory / tool selection
**Root cause class:** DOWNSTREAM SYMPTOM
**Priority:** P3

- **Primary scenarios:** —
- **Secondary scenarios:** HC-EVAL-A1, HC-EVAL-A4
- **Human evidence:** A1/A4: 'second evidence lookup also appeared potentially redundant'

### T10 — Eval scenario design mismatch

**Definition:** Scenario ground truth or expected behavior is weak relative to underlying Marcus data; observed trace should not be penalized as product failure.

**Category:** EVAL_INFRA
**Likely layer(s):** data / synthetic scenario
**Root cause class:** ROOT CAUSE
**Priority:** P2

- **Primary scenarios:** HC-EVAL-B2
- **Secondary scenarios:** —
- **Human evidence:** B2: 'weakness in the eval dataset/ground-truth design'

### T11 — Eval overlap / ambiguous scenario discrimination

**Definition:** Distinct scenarios share the same world state or cannot be fairly discriminated given current tooling, limiting eval interpretability.

**Category:** EVAL_INFRA
**Likely layer(s):** data / synthetic scenario; product limitation
**Root cause class:** MIXED
**Priority:** P3

- **Primary scenarios:** —
- **Secondary scenarios:** HC-EVAL-A3
- **Human evidence:** A3: 'same underlying date and signals, suggesting potential redundancy'

### T12 — Within-window variability not exposed

**Definition:** Deterministic analytics and get_trend_signals expose rolling means, percent change, and direction but not within-window distributional structure such as standard deviation, range, or volatility. This can cause a stable mean to hide meaningful day-to-day swings.

**Category:** PRODUCT
**Likely layer(s):** deterministic analytics; product limitation
**Root cause class:** ROOT CAUSE
**Priority:** P1

- **Primary scenarios:** HC-EVAL-C4
- **Secondary scenarios:** —
- **Human evidence:** C4: 'does not expose volatility or variability as a first-class signal' / 'A stable mean can hide substantial day-to-day variation'

- **Analyst note:** The original narrow C4 negative rubric technically passed because the agent did not invent an HRV decline. The human FAIL represents a product-completeness gap because the system cannot observe volatility. Future C4 eval should be redesigned once volatility is exposed.

## Product failures vs eval infrastructure

### A. Health Coach product / agent failures (T1–T9, T12)

Tool contracts, analytics provenance, eligibility enforcement, longitudinal framing,
salience gating, control-metric exposure, within-window variability, and generation/output
symptoms.

### B. Evaluation / observability limitations (T10–T11)

B2 eval scenario design weakness (PASS — not penalized). A3 scenario overlap.
Traces were sufficient to reconstruct tool outputs for F3; no primary observability-only
failure cluster emerged from human notes.

## Root cause vs symptom summary

| Class | Clusters |
|-------|----------|
| ROOT CAUSE | T1, T2, T3, T4, T6, T10, T12 |
| DOWNSTREAM SYMPTOM | T7, T8, T9 |
| MIXED | T5, T11 |
