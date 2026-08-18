# Health Coach Testing Documentation

This folder records **how we test** the Health Coach capstone and **what we have already verified**. It is meant to stay useful as the project grows into TRACE evaluations and production use.

## Philosophy

We split testing into layers because health-related software needs both **correct machinery** and **useful behavior**:

| Layer | Question it answers |
|-------|---------------------|
| **Tests** | Does the software behave according to deterministic expectations? |
| **Evals (future)** | Does the AI system produce useful, reliable behavior on representative cases? |

Tests are automated, repeatable, and should pass in CI without human judgment. Evals (TRACE, human review, failure taxonomy) come later and measure end-to-end quality.

## Test categories

### 1. Unit tests

Deterministic code-level checks on pure logic and parsing.

**Examples in this repo:**

- Registry CSV parsing and validation (`tests/test_registry.py`)
- Evidence and claim registry validation (`tests/test_evidence_registries.py`)
- Chunking invariants, YAML exclusion, merge rules (`tests/test_chunker.py`)
- L2-CR relationship policies and safety constraints (`tests/test_relationship_policy.py`, `tests/test_relationship_chunker.py`)
- Retrieval score filtering and metadata mapping (`tests/test_retrieval.py`)

**When to add:** whenever you introduce a rule that must never break silently (parsers, validators, policy gates).

### 2. Integration / smoke tests

Verify that components work together with real or stubbed external services.

**Examples:**

- OpenAI embedding generation (`rag/embedder.py`, smoke scripts)
- Pinecone upsert and query (`rag/vector_store.py`, `rag/ingest.py`)
- End-to-end document ingest (`scripts/ingest_document.py`)
- Live retrieval smoke queries (`scripts/test_retrieval.py`)

**When to add:** after wiring a new external dependency or pipeline stage.

### 3. Regression tests

Protect behavior we already validated when the codebase changes.

**Examples:**

- HHS, L2-TD, and L3-SF chunk counts unchanged after L2-CR relationship-aware chunking was added (`tests/test_relationship_chunker.py`)
- Approved-document gating in the source registry
- Four-document corpus structure in chunk inspection helpers

**When to add:** after fixing a bug or accepting a checkpoint you never want to accidentally undo.

### 4. Retrieval tests

Verify that relevant evidence is returned from Pinecone for representative queries.

**Phase D2 focus.** These tests check:

- correct index/namespace configuration
- score thresholding
- metadata preservation
- expected source documents for known query types

Retrieval tests validate **evidence fetch**, not answer generation. No LLM completion is involved.

See `scripts/test_retrieval.py` and `tests/test_retrieval.py`.

### 5. Evaluation / TRACE

**PARTIAL (Phase E2).** Trace schemas exist; eval runner does not.

Implemented:

- structured trace schema (`evals/trace_schema.py`)
- secret sanitization for trace payloads

Future work:

- trace capture from Assignment 3 agent runs
- human review workflows
- failure taxonomy and eval datasets under `evals/datasets/` and `evals/results/`

Do not commit fabricated trace files.

## Running tests

From the project root with the virtual environment activated:

```bash
python -m unittest discover -s tests -v
```

Live retrieval smoke (requires `.env` with OpenAI and Pinecone keys):

```bash
python scripts/test_retrieval.py
python scripts/test_retrieval.py --query "your question here"
```

## Related documentation

- [test_history.md](test_history.md) — chronological record of major checkpoints
- [../governance/controls_and_guardrails.md](../governance/controls_and_guardrails.md) — implemented controls inventory
