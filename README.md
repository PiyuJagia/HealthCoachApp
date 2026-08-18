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

**Current status:** Four approved corpus documents are embedded in Pinecone
(`healthcoach-rag` / `healthcoach-knowledge-base`, 407 vectors). Retrieval,
deterministic relationship-policy enforcement, health-data analytics, and trace
schemas are implemented. Google ADK Health Coach agent is implemented (Phase E3.1).

## Implementation Status

| Component | Status |
|-----------|--------|
| Chunking | implemented |
| Document ingestion | implemented (registry-driven) |
| Embeddings | implemented |
| Pinecone | implemented (`healthcoach-rag`) |
| Retrieval | implemented |
| Retrieval→policy enforcement | implemented (Phase E2) |
| Agent tool contracts | implemented (Phase E2; no ADK yet) |
| TRACE schemas | partial (E2 schemas + E3.1 run capture; Assignment 4 eval runner not built) |
| Health data (relational) | implemented (Phase E1) |
| Trend analytics | implemented (Phase E1) |
| Google ADK agent | implemented (Phase E3.1 — Assignment 3 Path A) |

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

**Workflow for adding a new knowledge source:**

1. Add curated Markdown to `knowledge/curated/`
2. Add a registry row with metadata
3. Set `approved_for_ingestion=TRUE`
4. Run `python scripts/ingest_document.py --document-id <document_id>` or batch ingest

No application-code changes should be required when a new approved document is added.

See `knowledge/README.md` for the full knowledge-engineering lifecycle and registry rules.

## Architecture

```text
Knowledge engineering          RAG pipeline                 Application (future)
raw → extracted → curated  →  chunk → embed → Pinecone  →  retrieve → reason → respond
         ↑                           ↑
    source_registry.csv         registry-driven ingest

User health data               Analytics                    Agent readiness (E2)
relational DB (SQLite/PG)  →  trend engine (deterministic) →  tool contracts + policy
                                                                    ↓
                                                              ADK agent (E3.1)
         ↑
   user's longitudinal truth — NOT stored in Pinecone
```

**Storage split:** Postgres (or SQLite locally) stores the **user's longitudinal truth**.
Pinecone stores the **application's curated scientific knowledge**. User health
observations must not be mixed into Pinecone.

| Layer | Responsibility |
|-------|----------------|
| `knowledge/` | Source documents, curation workflow, registry metadata |
| `rag/` | Chunking, embeddings, vector store, ingestion, retrieval |
| `data/` | SQLAlchemy models, database init, repository access |
| `analytics/` | Deterministic trend calculations from stored health data |
| `app/` | Agent-ready tools, output guard |
| `agent/` | Google ADK Health Coach agent, runner, trace capture |
| `evals/` | TRACE schemas and archived agent run traces |
| `scripts/` | CLI tools for ingest, retrieval testing, demo data seeding |

Curated Markdown in `knowledge/curated/` is the trusted source of truth for ingestion.
The RAG pipeline does not perform PDF cleaning, OCR, or substantive content rewriting.

## Knowledge Engineering Lifecycle

1. **raw/** — original downloaded PDFs or source files (local reference; gitignored)
2. **extracted/** — automated Markdown/text extraction; may contain layout artifacts (gitignored)
3. **curated/** — manually reviewed, approved Markdown (tracked in Git)
4. **registry/** — `source_registry.csv` defines metadata and ingestion approval

Only documents with `approved_for_ingestion=TRUE` are eligible for batch ingestion.

## RAG Ingestion Lifecycle

1. Look up document in `source_registry.csv`
2. Confirm approval status
3. Read curated Markdown
4. Chunk with overlap and metadata
5. Embed with `text-embedding-3-small`
6. Safely replace existing Pinecone vectors for the same `document_id`
7. Upsert new vectors

```bash
python scripts/ingest_document.py --document-id <document_id>
python scripts/ingest_all_approved.py
```

## Folder Structure

```text
health-coach-ai/
├── agent/               # Google ADK Health Coach agent (E3.1)
├── app/                 # Agent-ready tools and output guard
├── analytics/           # Deterministic trend analytics
├── data/                # SQLAlchemy models, DB init, repositories
├── rag/                 # Reusable RAG engine
├── knowledge/           # Document corpus and registry
├── scripts/             # CLI entry points
├── tests/               # Automated tests
├── evals/               # Trace schemas and run artifacts
├── streamlit_agent_demo.py
├── .env.example
├── requirements.txt
└── README.md
```

## Health Data (Phase E1 / E1.1)

Local development uses **SQLite** as a fast adapter (`sqlite:///./data/healthcoach.db`).
Production is planned to use **PostgreSQL** with the same SQLAlchemy models — no
SQLite-specific business logic in application code.

```bash
python scripts/seed_demo_health_data.py --reset
python scripts/inspect_demo_health_story.py --reset
```

Tables:

- `users` — minimal profile (display name, age, sex, height, weight, goal)
- `health_daily` — one row per user per date (HR, HRV, sleep, activity, VO2 max, etc.)
- `lifestyle_events` — timestamped caffeine, alcohol, mood/context events

**Synthetic 3-phase demo narrative (E1.1):** fictional user **Marcus Chen**, 90 days.

1. **Days 1–30** — baseline/calibration (noise, no strong directional signal)
2. **Days 31–60** — structured Mon/Wed/Fri exercise; emerging fitness trends
3. **Days 61–90** — disruption (61–75) then recovery (76–90); mixed signals

Synthetic data encodes **observations and temporal patterns, not causal truth**.
Afternoon caffeine, late-work context, and sleep changes overlap intentionally so a
future agent must handle ambiguity — caffeine is not the sole encoded cause.
`respiratory_rate` is a stable non-signal control metric.

Trend analytics compare a recent **7-day average** to a prior **30-day baseline**.
This is the **recent trend**; it may differ from **longer-term change** visible
across the full 90-day window (e.g., sleep improving in recovery week but still
below an earlier baseline).

Agent-ready entry point (no ADK yet):

```python
from app.health_tools import get_health_trends_for_agent
payload = get_health_trends_for_agent(user_id=1)
```

## Agent Readiness (Phase E2 — no ADK yet)

Deterministic path for Assignment 3:

```text
get_trend_signals() → retrieve_evidence() → evaluate_evidence_policy()
                              ↓
                   retrieve_authorized_evidence()  # enforced composition
                              ↓
                   check_final_output()            # future generation guard
```

Retrieval relevance is **not** authorization. Policy evaluation is deterministic
Python — not LLM-decided. Future traces use JSON under `evals/traces/` via
`evals/trace_schema.py`.

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
| `DATABASE_URL` | Relational health-data store (SQLite local; PostgreSQL planned) |

Never commit real keys. See `.env.example` for placeholders.

## Local Setup

```bash
python -m venv .venv
# activate virtual environment
pip install -r requirements.txt
cp .env.example .env
# add real API keys to .env (OPENAI_API_KEY, PINECONE_API_KEY, GOOGLE_API_KEY)
```

### Google ADK / Gemini (Phase E3.0)

Dependencies: `google-adk`, `google-genai` (see `requirements.txt`).

Set `GOOGLE_API_KEY` in `.env` (from [Google AI Studio](https://aistudio.google.com/apikey)).
Live verification scripts are **not** part of the offline pytest suite:

```bash
python scripts/smoke_gemini_auth.py
python scripts/smoke_adk_setup.py
```

These confirm Gemini auth and a minimal ADK agent → tool → observation → response cycle.

## Health Coach ADK Agent (Phase E3.1 — Assignment 3)

Stack: **Google ADK** + **Gemini** (`gemini-3.6-flash`).

The Health Coach is a **longitudinal health interpreter**, not merely an anomaly detector.
It proactively identifies useful themes — improvements, declines, recovery, ambiguity, and meaningful stability —
while refusing to manufacture correlations or recommendations without authorized evidence.

**Product principle:** Absence of a new trend can itself be useful information; absence of evidence is not permission to invent an explanation.

**Why this is an agent (not a fixed workflow):** It does not follow a fixed analysis sequence — it evaluates deterministic health signals, chooses which patterns warrant investigation, calls real evidence tools based on what it observes, and decides what to surface within deterministic safety and authorization constraints.

Architecture:

```text
User/scenario request
        ↓
health_coach_agent (Google ADK, max_llm_calls=8)
        ↓
get_trend_signals()          → SQLite/Postgres analytics (deterministic)
        ↓
retrieve_authorized_evidence() → Pinecone retrieve → evidence policy (deterministic)
        ↓
structured JSON candidate → check_final_output() (deterministic guard)
        ↓
trace archived to evals/traces/{run_id}.json
```

Run Marcus demo scenarios (live — requires `GOOGLE_API_KEY`, Pinecone, seeded DB):

```bash
python scripts/seed_demo_health_data.py --reset
python scripts/run_health_agent_scenarios.py --all
python scripts/run_health_agent_scenarios.py --scenario day60
```

Streamlit demo (Assignment 3 UI):

```bash
streamlit run streamlit_agent_demo.py
```

TRACE evaluation (Assignment 4) remains **partial** — runs are archived, but eval runner/taxonomy/assertions are not built yet.

## Ingest One Document

```bash
python scripts/ingest_document.py --document-id <document_id>
```

## Ingest All Approved Documents

```bash
python scripts/ingest_all_approved.py
```

## Test Retrieval

```bash
python scripts/test_retrieval.py --representative
python scripts/test_retrieval.py --query "your question here"
```

Uses `RAG_TOP_K` and `RAG_MIN_RELEVANCE_SCORE` from `.env` (defaults: 3 and 0.35).
Retrieval returns ranked chunks only — no LLM answer generation.

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

- No Google ADK agent orchestration yet
- No FastAPI `/ask` endpoint yet
- No persistent agent memory yet
- No Assignment 4 eval runner yet (trace schemas only)
- No Streamlit/deployment yet
- Analytics engine uses simple 7-day vs 30-day comparisons (not changepoint/z-score methods)

## Future Roadmap

The following remain planned:

- **Google ADK agent** — orchestrate trend signals, retrieval, policy, generation
- **Apple Health / HealthKit ingest** — live user data beyond synthetic demo
- **Assignment 4 TRACE eval runner** — score traces under `evals/`
- **Persistent memory** — Assignment 5
- **Deployment + frontend** — production hosting and user-facing UI
