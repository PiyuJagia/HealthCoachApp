# Health Coach AI

Independent capstone project for an AI-powered Health Coach that will eventually
combine personal health signals with evidence-based guidance.

## Purpose

Health Coach AI is being built to:

- consume Apple Health / HealthKit data (future);
- analyze trends such as resting heart rate, heart-rate recovery, HRV, sleep,
  workouts, exercise frequency, VO2 max, and related lifestyle signals (future);
- retrieve evidence from a curated health knowledge base;
- make grounded observations and recommendations (future);
- later add persistent memory, TRACE evaluations, alerts, trends, and a richer frontend.

**Current status:** L2-CR-002 is approved for MVP ingestion with
`verified_with_constraints` status. All four corpus documents are embedded in
Pinecone (`healthcoach-rag` / `healthcoach-knowledge-base`). Retrieval is not yet
implemented.

## Implementation Status

| Component | Status |
|-----------|--------|
| Chunking | implemented |
| Document ingestion | implemented (registry-driven) |
| Embeddings | implemented |
| Pinecone | implemented (`healthcoach-rag`) |
| Retrieval | not yet implemented |

### Approved RAG corpus

- HHS Physical Activity Guidelines (`hhs_physical_activity_guidelines_2e`)
- Health Coach Trend Detection (`healthcoach_trend_detection`)
- Health Coach Safety / Scope / Escalation (`healthcoach_safety_scope_escalation`)

- Health Coach Correlation Modeling (`healthcoach_correlation_modeling`)

Default chunking settings: `chunk_size=1200`, `chunk_overlap=200`. L2-CR uses
relationship-aware chunking for Section 5 active relationships (R-01…R-09).

## Knowledge Base Management

The project supports **multiple RAG documents** from day one. Each source is tracked in
`knowledge/registry/source_registry.csv` with metadata, provenance, and an ingestion
approval flag.

The registry exists so ingestion can be:

- registry-driven rather than hardcoded
- safe for batch processing across many documents
- explicit about which curated sources are trusted

**Intended workflow for adding a new knowledge source** *(ingestion not implemented yet)*:

1. Add curated Markdown to `knowledge/curated/`
2. Add a registry row with metadata
3. Set `approved_for_ingestion=TRUE`
4. Run the future ingestion command for one document or all approved documents

No application-code changes should be required when a new approved document is added.

See `knowledge/README.md` for the full knowledge-engineering lifecycle and registry rules.

## Architecture

```text
Knowledge engineering          RAG pipeline                 Application (future)
raw → extracted → curated  →  chunk → embed → Pinecone  →  retrieve → reason → respond
         ↑                           ↑
    source_registry.csv         registry-driven ingest
```

| Layer | Responsibility |
|-------|----------------|
| `knowledge/` | Source documents, curation workflow, registry metadata |
| `rag/` | Chunking, embeddings, vector store, ingestion, retrieval |
| `app/` | FastAPI HTTP boundary (backend source of truth) |
| `scripts/` | CLI tools for ingest and retrieval testing |

Curated Markdown in `knowledge/curated/` is the trusted source of truth for ingestion.
The RAG pipeline does not perform PDF cleaning, OCR, or substantive content rewriting.

## Knowledge Engineering Lifecycle

1. **raw/** — original downloaded PDFs or source files (local reference; gitignored)
2. **extracted/** — automated Markdown/text extraction; may contain layout artifacts (gitignored)
3. **curated/** — manually reviewed, approved Markdown (tracked in Git)
4. **registry/** — `source_registry.csv` defines metadata and ingestion approval

Only documents with `approved_for_ingestion=TRUE` are eligible for batch ingestion.

## RAG Ingestion Lifecycle

*(Not implemented yet — placeholder for upcoming phases.)*

1. Look up document in `source_registry.csv`
2. Confirm approval status
3. Read curated Markdown
4. Chunk with overlap and metadata
5. Embed with `text-embedding-3-small`
6. Safely replace existing Pinecone vectors for the same `document_id`
7. Upsert new vectors

## Folder Structure

```text
health-coach-ai/
├── app/                 # FastAPI application
├── rag/                 # Reusable RAG engine
├── knowledge/           # Document corpus and registry
├── scripts/             # CLI entry points
├── tests/               # Automated tests
├── .env.example
├── requirements.txt
└── README.md
```

## Environment Variables

Copy the example file and fill in real values locally:

```bash
cp .env.example .env
```

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | OpenAI API access |
| `PINECONE_API_KEY` | Pinecone API access |
| `PINECONE_INDEX_NAME` | Capstone index (`healthcoach-rag`) |
| `PINECONE_NAMESPACE` | Production namespace (`healthcoach-knowledge-base`) |
| `RAG_TOP_K` | Default retrieval count (optional) |
| `RAG_MIN_RELEVANCE_SCORE` | Retrieval refusal threshold (optional) |

Never commit real keys. See `.env.example` for placeholders.

## Local Setup

*(Placeholder — detailed setup instructions will be added in later phases.)*

```bash
python -m venv .venv
# activate virtual environment
pip install -r requirements.txt
cp .env.example .env
# add real API keys to .env
```

## Ingest One Document

*(Not implemented yet.)*

```bash
python -m scripts.ingest_document --document-id <document_id>
```

## Ingest All Approved Documents

*(Not implemented yet.)*

```bash
python -m scripts.ingest_all_approved
```

## Test Retrieval

*(Not implemented yet.)*

```bash
python -m scripts.test_retrieval --question "Your question here"
```

Retrieval testing will validate Pinecone matches without calling an LLM.

## Pinecone Configuration

| Setting | Planned value |
|---------|---------------|
| Index | `healthcoach-rag` |
| Namespace | `healthcoach-knowledge-base` |
| Embedding model | `text-embedding-3-small` (1536 dimensions) |
| Similarity metric | cosine |

The Pinecone index `healthcoach-rag` holds **407 vectors** across four approved
documents (289 HHS + 15 L2-TD + 89 L2-CR + 14 L3-SF). L2-CR vectors carry
`version=L2-CR-002` and `verification_status=verified_with_constraints`.

## Current Limitations

- No RAG modules implemented
- No FastAPI endpoints implemented
- No curated documents migrated
- No Pinecone index created
- No package installation performed in Phase A

## Future Roadmap

The following are planned but **not implemented**:

- **HealthKit / health data** — ingest and normalize Apple Health metrics
- **Trends** — resting HR, HRV, sleep, workouts, VO2 max, recovery patterns
- **Alerts** — threshold and anomaly notifications
- **Recommendations** — grounded coaching responses from retrieved evidence
- **TRACE evaluations** — structured retrieval and response quality testing
- **Persistent memory** — longitudinal user context
- **Deployment** — production hosting for API and services
- **Final frontend** — user-facing Health Coach experience
