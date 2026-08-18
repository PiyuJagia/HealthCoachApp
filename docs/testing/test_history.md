# Test History

Chronological record of major testing checkpoints. Entries are based on repository commits, test files, and scripts that exist in the project — not fabricated results.

**Current baseline (pre–Phase D2 retrieval archive):**

| Document | Pinecone vectors |
|----------|-----------------:|
| HHS | 289 |
| L2-TD | 15 |
| L2-CR-002 | 89 |
| L3-SF | 14 |
| **Total** | **407** |

**Offline test suite:** 149 tests passing (includes Phase E2.1 policy semantics corrections).

---

## Checkpoint log

| Phase / checkpoint | What was tested | Why it mattered | Result | Status | Scripts / tests |
|--------------------|-----------------|-----------------|--------|--------|-----------------|
| **A — Repository init** | Project structure, `.gitignore`, env template | Safe foundation for secrets and knowledge layout | Repo scaffold committed (`c55cfa5`) | Pass | — |
| **B — Registry foundation** | CSV parsing, approval flags, curated path resolution | All downstream pipelines depend on valid registry | Unit tests pass | Pass | `tests/test_registry.py`, `rag/registry.py` |
| **C1 — Markdown chunking** | Splitter, metadata attachment, chunk indexing | Core RAG building block | Chunker tests pass | Pass | `tests/test_chunker.py`, `rag/chunker.py` |
| **C2 — Corpus migration** | Four curated documents registered | Multi-document corpus | 4 registry rows validated | Pass | `80cd794` |
| **C3 — Chunk inspection** | Per-document chunk stats, frontmatter handling | Quality gate before embed | Inspection helpers pass | Pass | `scripts/inspect_chunks.py`, `tests/test_inspect_chunks.py` |
| **C3 — YAML / frontmatter** | YAML excluded from embed text; supplemental metadata | Prevent config leakage into embeddings | Dedicated chunker tests pass | Pass | `rag/frontmatter.py`, `tests/test_chunker.py` |
| **C3 — Tiny / heading remediation** | Heading-only merge, tiny fragment rules | Avoid unusable retrieval chunks | Post-process merge tests pass | Pass | `rag/chunker.py` |
| **E — Embedding layer** | OpenAI embedder, vector ID/metadata builders | Bridge chunks → Pinecone | Embedder/vector tests pass | Pass | `rag/embedder.py`, `tests/test_embedder.py` |
| **E — Pinecone ingestion** | Registry-driven ingest, delete-replace | Live vector corpus | Batch ingest to `healthcoach-rag` | Pass | `rag/ingest.py`, `scripts/ingest_*.py` |
| **C4 — Evidence registries** | Evidence + claim CSV validation | Provenance for L2-CR remediation | Registry tests pass | Pass | `tests/test_evidence_registries.py` |
| **C4 — L2-CR revocation** | L2-CR unapproved; vectors removed | Block unsafe corpus | L2-CR = 0 vectors; 318 total | Pass | `ab8714a` |
| **C5 — L2-CR remediation** | L2-CR-002 content + claim mappings | Replace arrow-table catalogue | Integrated | Pass | `18f134d` |
| **C5.1 — Relationship chunking** | R-01…R-09 safety envelopes | Guardrails co-located with relationship text | 54 relationship chunks all safe | Pass | `tests/test_relationship_chunker.py` |
| **C5 — Policy invariants** | Suppression, level caps, input gating | Deterministic interpretation rules | 13 policy tests pass | Pass | `tests/test_relationship_policy.py` |
| **MVP — L2-CR re-ingestion** | Approve + ingest L2-CR-002 | Complete 407-vector corpus | 89 L2-CR vectors; version L2-CR-002 | Pass | `638c4f2` |
| **Regression — Non-L2-CR chunking** | HHS/L2-TD/L3-SF counts unchanged | L2-CR special path must not affect others | 289 / 15 / 14 chunks | Pass | `tests/test_relationship_chunker.py` |
| **D2 — Retrieval (offline)** | Score filter, top_k, metadata mapping, no LLM | Retrieval layer correctness | 12 unit tests pass | Pass | `tests/test_retrieval.py`, `rag/retrieval.py` |
| **D2 — Retrieval (live smoke)** | 6 representative queries vs Pinecone | Validate 407-vector corpus retrieval | 5/6 pass; 1 partial — see below | Pass (with notes) | `scripts/test_retrieval.py` |
| **D2.1 — Relationship metadata in Pinecone** | Whitelist + L2-CR-only re-ingestion | Machine-readable policy fields at retrieval time | 54/89 L2-CR vectors carry relationship metadata; corpus 407 | Pass | `rag/vector_store.py`, `scripts/verify_l2cr_relationship_metadata.py` |
| **D2.1 — Retrieval regression** | Re-run representative queries post re-ingest | Confirm structured metadata + envelope text | Same pass pattern as D2; L2-CR results expose `relationship_metadata` | Pass | `scripts/test_retrieval.py` |
| **E1 — Health-data foundation** | SQLAlchemy models, seed script, trend engine, agent tool | Relational user truth separate from Pinecone knowledge | 25 new offline tests pass | Pass | `tests/test_database.py`, `tests/test_seed_data.py`, `tests/test_trends.py` |
| **E1.1 — Synthetic demo narrative** | 3-phase story, ambiguity, inspection script | Product demo + future agent/TRACE scenarios | 8 additional seed/trend tests pass | Pass | `data/demo_seed.py`, `scripts/inspect_demo_health_story.py` |
| **E1.1 — Spec reconciliation** | Marcus Chen profile, spec missing-data days, baseline ranges | Align canonical demo user with attached 90-day specification | Profile + seed tests pass; suite 129 | Pass | `data/demo_seed.py` |
| **E2 — Agent readiness** | Retrieval→policy adapter, agent tools, trace schema, output guard | Enforced evidence path before future ADK | 18 new offline tests pass | Pass | `rag/evidence_policy.py`, `app/agent_tools.py`, `evals/trace_schema.py`, `app/output_guard.py` |
| **E2.1 — Policy semantics correction** | Remove auto-contradiction; separate evidence vs recommendation auth | Fix over-broad multi-relationship suppression | Policy tests updated; suite 149 | Pass | `rag/evidence_policy.py` |

---

## Phase E2.1 — Policy semantics correction (2026-08-17)

**Why it matters:** E2 initially treated ≥2 relationship_ids as automatic contradiction.
That was too broad and could suppress compatible evidence (e.g. R-05 + R-06).

**Corrections:**

- Relationships evaluated **independently**; `contradictory_candidates` is explicit only
- R-03 / mandatory suppression applies when upstream context sets `contradictory_candidates=True`
- Multiple relationships without explicit contradiction → **QUALIFY** (ambiguous), not SUPPRESS
- `evidence_authorized` vs `recommendation_authorized` separated on decision objects
- General HHS/L2-TD/L3-SF evidence usable for grounding but does not grant recommendation authority

**Verification:** 149 offline tests pass.

---

## Phase E2 — Agent readiness (2026-08-17)

**Why it matters:** Retrieval relevance is not authorization. Assignment 3 needs a
deterministic enforcement layer between Pinecone retrieval and any future LLM output.

**Implemented:**

- `evaluate_retrieved_evidence()` — SURFACE / QUALIFY / SUPPRESS from `RetrievalResult[]`
- `retrieve_authorized_evidence()` — enforced retrieve + policy composition
- `evals/trace_schema.py` — JSON trace helpers with secret sanitization
- `check_final_output()` — minimal deterministic output guard

**Not implemented:** Google ADK, agent orchestration, eval runner, fake traces.

**Verification:**

| Check | Result |
|-------|--------|
| Offline tests added | 18 |
| Total offline suite | 147 pass |
| Network calls in new tests | none |

---

## Phase E1.1 — Spec reconciliation (2026-08-17)

**Why it matters:** Canonical demo user and missing-data schedule now match the attached
*AI Health Coach: 90-Day Synthetic Dataset Specification* without redesigning E1 architecture.

**Changes:** Marcus Chen profile (36M, 177 cm, 84 kg); missing-data days 22–23, 47, 54–55;
RHR/HRV baseline centers aligned to spec ranges; caffeine/mood event timing adjusted.

**Deferred:** sleep efficiency/latency fields, insight-candidate labels, multi-horizon analytics,
expected trend-engine prose from spec section 7 (documentation only).

**Verification:** 129 offline tests pass; `scripts/inspect_demo_health_story.py --reset`.

---

## Phase E1.1 — Synthetic demo narrative (2026-08-17)

**Why it matters:** Replaces the simple E1 seed with a capstone-aligned 90-day story
supporting trend detection, ambiguity, suppression, and recovery scenarios for
Assignment 3 (agent) and Assignment 4 (TRACE/evals).

**Narrative:** Phase 1 baseline → Phase 2 structured exercise/fitness → Phase 3
disruption + recovery. Observations only — no causal labels in storage.

**Key controls:**

- Caffeine inside and outside disruption window (confounded scenario)
- HRV disruption implemented as increased **volatility**, not merely lower mean
- `respiratory_rate` stable non-signal control
- Realistic missing-data gaps (sync gaps, incomplete sleep, sparse HRV/VO2 nulls)

**Inspection:** `python scripts/inspect_demo_health_story.py --reset`

**Verification:**

| Check | Result |
|-------|--------|
| Offline tests added/modified | 8 seed + trend story tests |
| Total offline suite | 129 pass |
| Trend checkpoints | Day 30, 60, 75, 90 reported by inspection script |

---

## Phase E1 — Health-data foundation (2026-08-17)

**Why it matters:** Establishes the relational store for user longitudinal data and a
deterministic trend layer that a future ADK agent can call without mixing user
observations into Pinecone.

**Architecture:** `relational DB → analytics/trends → app/health_tools` (framework-independent JSON).

**Database:** SQLAlchemy 2.x with `DATABASE_URL`. Local default `sqlite:///./data/healthcoach.db`;
PostgreSQL planned for production using the same models.

**Tables:** `users`, `health_daily` (unique `user_id` + `date`), `lifestyle_events`.

**Synthetic demo:** `scripts/seed_demo_health_data.py` — 90 days for fictional user
"Marcus Chen" with intentional patterns (baseline stability, exercise consistency,
disruption/recovery, caffeine ambiguity). Fixed seed `42`.
No causal labels in stored data.

**Trend engine:** 7-day recent average vs prior 30-day baseline; observational directions only.

**Agent interface:** `get_health_trends_for_agent()` — JSON-serializable, no ADK/LLM/Pinecone.

**Verification:**

| Check | Result |
|-------|--------|
| Offline tests added | 25 (database + seed + trends) |
| Total offline suite | 122 pass |
| Demo days seeded | 90 |
| Uniqueness constraint | `health_daily (user_id, date)` enforced |
| Missing data handling | HRV/VO2 gaps tolerated; `data_sufficient` when baseline too short |

---

## Phase D2.1 — Relationship metadata persistence (2026-08-17)

**Why it matters:** Post-retrieval policy enforcement and future TRACE/evals need structured fields (e.g. `max_product_level`, `recommendation_eligible`) without parsing safety-envelope prose.

**Change:** Added `RELATIONSHIP_METADATA_FIELDS` whitelist to `build_vector_metadata()` with Pinecone-safe types (string / int / bool).

**Re-ingestion:** `healthcoach_correlation_modeling` only — 89 vectors replaced. HHS (289), L2-TD (15), L3-SF (14) untouched. Namespace total **407**.

**Verification:**

| Check | Result |
|-------|--------|
| L2-CR vector count | 89 |
| All versions | `L2-CR-002` |
| Vectors with `relationship_id` | 54 / 89 (relationship chunks only) |
| R-02 sample | `measurement_transfer_risk=high`, `max_product_level=2`, `recommendation_eligible=false` |
| R-03 sample | `mandatory_contradiction_suppression=true` |
| R-05 sample | `max_product_level=4`, `recommendation_eligible=true` |
| R-06 sample | `measurement_transfer_risk=high`, `recommendation_eligible=false` |
| R-08 sample | `max_product_level=2`, `recommendation_eligible=false` |
| R-09 sample | `modifier_suppressor_only=true` |

**Retrieval regression:** Representative D2 queries unchanged in pass/fail pattern. L2-CR hits now include structured `relationship_metadata` alongside safety-envelope text previews.

---

## Phase D2 — Retrieval checkpoint (2026-08-17)

**Settings:** `RAG_TOP_K=3`, `RAG_MIN_RELEVANCE_SCORE=0.35`, index `healthcoach-rag`, namespace `healthcoach-knowledge-base`, corpus **407 vectors** (unchanged).

| Query ID | Query (summary) | Expected source | Top result(s) | Score range | Pass? | Notes |
|----------|-----------------|-----------------|---------------|-------------|-------|-------|
| D2-A | Moderate PA for adults per week | HHS | 3× HHS (`Aerobic Activity`, `Cardiorespiratory Health`) | 0.69–0.73 | **Pass** | Strong HHS dominance |
| D2-B | Real trend vs day-to-day variation | L2-TD | 3× L2-TD (`Detecting change`, trend vocabulary) | 0.53–0.67 | **Pass** | L2-TD exclusively in top 3 |
| D2-C | Aerobic consistency + RHR decrease | L2-CR R-05 | 3× L2-CR R-05 chunks | 0.60–0.63 | **Pass** | Safety envelope present in all previews |
| D2-D | Sleep less → HRV decrease (causal) | L2-CR with association limits | L2-CR R-01 (#1), R-02 (#2), R-01 (#3) | 0.53–0.55 | **Pass*** | R-02 (HRV) retrieved; R-01 (RHR) also ranked — causal query still returns **association-only** envelopes |
| D2-E | Avoid recommendation / escalate | L3-SF | L3-SF (#1), L2-CR levels (#2), HHS (#3) | 0.51–0.57 | **Partial** | L3-SF is top hit; L2-CR interpretation-level chunk at #2 is plausible but worth monitoring |
| D2-F | Off-topic (FIFA World Cup) | None above threshold | 0 results | — | **Pass** | Threshold 0.35 blocked all matches |

**Threshold assessment:** 0.35 appears reasonable — blocks off-topic noise (D2-F) while retaining domain queries in the 0.51–0.73 range. Not tuned to force passes.

**Pinecone relationship metadata:** **IMPLEMENTED** in Phase D2.1 — structured fields on L2-CR relationship chunks; safety envelopes remain in `text`.

**Notable retrieval risks:**

1. Causal-framed queries may rank adjacent sleep/RHR relationships alongside sleep/HRV (D2-D).
2. Safety/escalation queries may co-retrieve L2-CR interpretation-level content (D2-E #2).
3. Post-retrieval policy enforcement (suppression, level caps) is not yet wired — retrieval returns evidence only.

---

## Future TRACE linkage

When TRACE is implemented, failures discovered in production or eval runs should link back to:

1. **Failure category** — e.g. wrong document retrieved, guardrail missing in context, over-threshold noise
2. **Automated assertion** — unit or retrieval test added where the fix is deterministic
3. **Remediation** — code/doc/registry change with commit reference
4. **Before/after result** — metric or pass/fail on the same eval case

Placeholder directories:

- `evals/traces/` — raw trace logs (empty)
- `evals/datasets/` — eval query sets (empty)
- `evals/results/` — scored eval runs (empty)

Do not create fake trace data until TRACE is built.
