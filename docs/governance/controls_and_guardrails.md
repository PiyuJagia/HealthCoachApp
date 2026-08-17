# Controls and Guardrails Inventory

Each control is labeled:

- **IMPLEMENTED** — exists in code/config and is active today
- **PARTIAL** — partially implemented or present in chunk text but not fully in metadata/pipeline
- **PLANNED** — documented intent, not built yet

---

## A. Knowledge-source governance

| Control | Status | Implementation |
|---------|--------|----------------|
| Central source registry | IMPLEMENTED | `knowledge/registry/source_registry.csv`, `rag/registry.py` |
| Unique `document_id` per curated document | IMPLEMENTED | `rag/registry.py` validation |
| `approved_for_ingestion` gate | IMPLEMENTED | `source_registry.csv`; enforced in `rag/ingest.py` |
| Curated vs raw/extracted lifecycle | IMPLEMENTED | `knowledge/raw/`, `knowledge/extracted/` gitignored; `knowledge/curated/` versioned |
| Document version tracking (`L2-CR-002`, etc.) | IMPLEMENTED | Registry `version` column; YAML `doc_id`; Pinecone `version` metadata |
| Document verification status | IMPLEMENTED | YAML `verification_status`; e.g. L2-CR `verified_with_constraints` |
| Evidence grade at document level | IMPLEMENTED | YAML `evidence_grade`; supplemental chunk/Pinecone metadata |
| Four-document approved corpus | IMPLEMENTED | HHS, L2-TD, L2-CR, L3-SF — all `approved_for_ingestion=TRUE` |

---

## B. Evidence governance

| Control | Status | Implementation |
|---------|--------|----------------|
| External evidence registry | IMPLEMENTED | `knowledge/registry/evidence_registry.csv`, `rag/evidence_registry.py` |
| Claim-to-source mappings | IMPLEMENTED | `knowledge/registry/claim_evidence_registry.csv`, `rag/claim_evidence_registry.py` |
| Source verification statuses | IMPLEMENTED | e.g. `verified`, `incomplete_metadata`, `page_verification_required`, `superseded` |
| Explicit incomplete metadata (no fabrication) | IMPLEMENTED | `SD-HRV-META-2025`, `SLEEP-RESTRICT-HR-2023` rows |
| ACSM page verification flag | IMPLEMENTED | `ACSM-GETP12` → `page_verification_required` |
| Row-level claim verification preserved | IMPLEMENTED | Claim rows retain `revision_complete_pending_review` where applicable |
| Automatic claim verification from ingest | PLANNED | Ingest does not auto-verify claims |

---

## C. Chunking / retrieval-safety controls

| Control | Status | Implementation |
|---------|--------|----------------|
| YAML excluded from embedding text | IMPLEMENTED | `rag/frontmatter.py`, `rag/chunker.py` |
| Frontmatter parsed into controlled metadata | IMPLEMENTED | Whitelisted keys in `rag/frontmatter.py` |
| Registry metadata protected from YAML override | IMPLEMENTED | `PROTECTED_METADATA_KEYS` in `rag/frontmatter.py` |
| Heading-only chunk detection and merge | IMPLEMENTED | `rag/chunker.py` `post_process_chunks()` |
| Tiny fragment merge rules | IMPLEMENTED | `rag/chunker.py` |
| Standard chunk size 1200 / overlap 200 | IMPLEMENTED | `rag/chunker.py` defaults |
| L2-CR relationship-aware Section 5 chunking | IMPLEMENTED | `rag/relationship_chunker.py` |
| Self-contained safety envelopes on L2-CR relationship chunks | IMPLEMENTED | Prepended to every R-01…R-09 child chunk |
| Relationship policy metadata on LangChain chunks | IMPLEMENTED | `relationship_id`, `max_product_level`, etc. at chunk creation |
| Relationship fields in Pinecone vector metadata | **PARTIAL** | See gap note below — fields exist in chunk metadata but are **not** whitelisted in `build_vector_metadata()` |
| Safety constraints recoverable from retrieved L2-CR text | IMPLEMENTED | Safety envelope embedded in Pinecone `text` field |

### Pinecone relationship metadata gap (PARTIAL)

At chunk creation, L2-CR relationship chunks carry:

- `relationship_id`
- `relationship_status`
- `relationship_section_title`
- `evidence_strength`
- `measurement_transfer_risk`
- `max_product_level`
- `recommendation_eligible`
- `modifier_suppressor_only`
- `mandatory_contradiction_suppression`

`rag/vector_store.py` → `build_vector_metadata()` only copies `section_heading` and `SUPPLEMENTAL_METADATA_FIELDS` (document-level frontmatter). **Relationship policy fields are not stored in Pinecone today.**

**Smallest safe fix (not applied in Phase D2):** add a `RELATIONSHIP_METADATA_FIELDS` tuple to `vector_store.py` and copy non-empty values in `build_vector_metadata()`. **Only L2-CR (89 vectors) would need re-ingestion**; HHS/L2-TD/L3-SF unchanged.

Basic semantic retrieval remains viable because safety envelopes are in chunk text.

---

## D. Correlation / interpretation guardrails

Policy representation is **IMPLEMENTED** in code and curated content; automated correlation engine is **PLANNED**.

| Control | Status | Implementation |
|---------|--------|----------------|
| Association-only language (no causal arrows in L2-CR-002) | IMPLEMENTED | Curated document content |
| Nine active relationships R-01…R-09 | IMPLEMENTED | L2-CR Section 5; `claim_evidence_registry.csv` |
| Evidence strength per relationship | IMPLEMENTED | Document rows; claim registry; safety envelopes |
| Measurement-transfer risk | IMPLEMENTED | R-02, R-06 flagged high; policy + envelopes |
| Max product level caps | IMPLEMENTED | Per-relationship; tested in `tests/test_relationship_policy.py` |
| Recommendation eligibility (only R-05, R-07 Level 4) | IMPLEMENTED | `rag/relationship_policy.py` |
| Modifier/suppressor-only (R-09) | IMPLEMENTED | `MODIFIER_ONLY_RELATIONSHIPS`; policy tests |
| Mandatory contradiction suppression (R-03) | IMPLEMENTED | `should_suppress_contradictory_interpretation()` |
| No recommendation for R-06 (high transfer) | IMPLEMENTED | `NO_RECOMMENDATION_RELATIONSHIPS` |
| No alcohol advice (R-08) | IMPLEMENTED | Policy + L2-CR content cap at Level 2 |
| Input-gated relationships (R-07, R-08, R-09) | IMPLEMENTED | `INPUT_GATED_RELATIONSHIPS` in policy |
| Unregistered relationship blocked | IMPLEMENTED | `is_registered_relationship()` |
| Runtime correlation/analytics engine | PLANNED | Policy tests validate representation only |

---

## E. Ingestion controls

| Control | Status | Implementation |
|---------|--------|----------------|
| Only approved registry documents ingestable | IMPLEMENTED | `rag/ingest.py` |
| Replace-on-ingest (delete then upsert) | IMPLEMENTED | `delete_document_vectors()` before upsert |
| Stable vector IDs | IMPLEMENTED | `{document_id}__chunk_{index:04d}` |
| Index/namespace from environment | IMPLEMENTED | `PINECONE_INDEX_NAME`, `PINECONE_NAMESPACE` |
| Embedding model consistency | IMPLEMENTED | `text-embedding-3-small` in `rag/embedder.py` |
| Full corpus re-ingestion script | IMPLEMENTED | `scripts/ingest_all_approved.py` |

---

## F. Testing controls

| Control | Status | Implementation |
|---------|--------|----------------|
| Deterministic unit test suite | IMPLEMENTED | `tests/` (82 tests at Phase D2 start) |
| Registry/evidence validation tests | IMPLEMENTED | `tests/test_registry.py`, `tests/test_evidence_registries.py` |
| Chunking regression tests | IMPLEMENTED | `tests/test_chunker.py`, `tests/test_relationship_chunker.py` |
| Relationship policy invariant tests | IMPLEMENTED | `tests/test_relationship_policy.py` |
| Retrieval unit tests (mocked) | IMPLEMENTED | `tests/test_retrieval.py` (Phase D2) |
| Live retrieval smoke script | IMPLEMENTED | `scripts/test_retrieval.py` (Phase D2) |
| TRACE / eval automation | PLANNED | `evals/` placeholders only |

---

## G. Known gaps / future controls

| Gap | Status | Notes |
|-----|--------|-------|
| Evidence bibliographic gaps | IMPLEMENTED (visible) | Incomplete metadata intentionally explicit |
| ACSM page-level verification | IMPLEMENTED (visible) | Flagged, not silently treated as verified |
| Relationship fields in Pinecone metadata | PARTIAL | Re-ingest L2-CR only if whitelist added |
| Retrieval quality baselines | PARTIAL | Phase D2 live smoke; not full eval suite |
| Answer generation guardrails | PLANNED | No `/ask` or agent yet |
| TRACE traces and failure taxonomy | PLANNED | `evals/traces/` placeholder |
| Persistent user memory | PLANNED | Not in scope |
| Streamlit / deployment controls | PLANNED | Not in scope |
| Automated post-retrieval policy enforcement | PLANNED | Policy exists; not wired to retrieval layer yet |

---

## File reference map

```
knowledge/registry/source_registry.csv     → document approval
knowledge/registry/evidence_registry.csv   → external sources
knowledge/registry/claim_evidence_registry.csv → claim mappings
rag/registry.py                            → source parsing
rag/evidence_registry.py                   → evidence parsing
rag/claim_evidence_registry.py             → claim parsing
rag/chunker.py                             → generic chunking
rag/relationship_chunker.py                → L2-CR relationship chunking
rag/relationship_policy.py               → interpretation policy
rag/embedder.py                            → embeddings
rag/vector_store.py                        → Pinecone I/O
rag/ingest.py                              → ingest pipeline
rag/retrieval.py                           → retrieval layer (Phase D2)
```
