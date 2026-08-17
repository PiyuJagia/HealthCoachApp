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

**Offline test suite:** 97 tests passing (includes Phase D2 retrieval + D2.1 metadata tests).

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
