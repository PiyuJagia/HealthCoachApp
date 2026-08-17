# Knowledge Corpus

This folder holds the Health Coach multi-document knowledge corpus. The registry in
`registry/source_registry.csv` drives which curated documents are eligible for RAG ingestion.

## Full Lifecycle

```text
source acquisition
  → raw
  → extraction
  → extracted
  → human review / cleanup
  → curated
  → registry approval
  → RAG ingestion
```

Only curated Markdown with `approved_for_ingestion=TRUE` in the registry may be ingested.

---

## RAW

**Original source material**

- PDFs
- downloaded source documents
- reference files

**Location:** `knowledge/raw/`

**Policy**

- local only
- Git ignored
- never ingested directly

---

## EXTRACTED

**Machine-extracted Markdown or text**

**Location:** `knowledge/extracted/`

**Policy**

- staging only
- may contain extraction artifacts
- Git ignored except `.gitkeep`
- never ingested directly

---

## CURATED

**Human-reviewed Markdown**

**Location:** `knowledge/curated/`

**Policy**

- tracked in Git
- trusted source for RAG
- only curated documents may be approved for ingestion

---

## REGISTRY

**Metadata and approval control**

**Location:** `knowledge/registry/source_registry.csv`

**Policy**

- tracked in Git
- drives single-document and batch ingestion
- approval gate is `approved_for_ingestion`

---

## Source Registry Schema

Header order:

```text
document_id,title,organization,topic,topic_category,source_url,publication_date,retrieval_date,document_type,evidence_level,local_filename,version,approved_for_ingestion,notes,curated_path
```

### Field Rules

#### `document_id`

- stable
- lowercase snake_case
- unique
- never reused for a different source

#### `title`

- human-readable official title

#### `organization`

- source publisher or institution

#### `topic`

- specific subject area

#### `topic_category`

- broader grouping such as:
  - exercise
  - sleep
  - recovery
  - cardiovascular
  - lifestyle
  - integrated_health

#### `source_url`

- canonical public source URL when available

#### `publication_date`

- original publication date if known

#### `retrieval_date`

- date the source was obtained

#### `document_type`

Examples:

- guideline
- systematic_review
- review
- primary_research
- consensus_statement
- fact_sheet
- curated_evidence_synthesis

#### `evidence_level`

Examples:

- authoritative_guideline
- systematic_review
- meta_analysis
- professional_guidance
- peer_reviewed_research
- curated_evidence_synthesis

#### `local_filename`

- curated Markdown filename
- filename only, unless `curated_path` overrides it

#### `version`

- source or curation version

#### `approved_for_ingestion`

- `TRUE` or `FALSE`
- only `TRUE` rows are eligible for batch ingestion

#### `notes`

- review notes
- known limitations
- curation caveats

#### `curated_path`

- optional path relative to project root
- if blank, default to:
  `knowledge/curated/{local_filename}`

---

## Registry Validation

Registry parsing and validation live in `rag/registry.py`.

- Parsing the header-only registry is allowed.
- Curated files are validated only when explicitly checked before ingestion.
- Duplicate `document_id` values and invalid approval flags are rejected.

---

## Evidence Provenance Registries

Curated synthesis documents such as L2-CR may cite external evidence. Claim-level
provenance is tracked separately from RAG document approval.

### A. `source_registry.csv`

**Purpose:** Tracks curated RAG documents and whether each document is approved
for ingestion into Pinecone.

**Approval gate:** `approved_for_ingestion=TRUE`

### B. `evidence_registry.csv`

**Purpose:** Tracks authoritative external sources used to support claims inside
curated synthesis documents.

**Key field:** `source_key` (for example `Shaffer-2017`, `ACSM-GETP11`)

**Validation:** `rag/evidence_registry.py`

### C. `claim_evidence_registry.csv`

**Purpose:** Maps individual claims to external sources and records:

- support strength (`support_type`)
- claim grade
- causal interpretation (`causal_class`)
- within-person applicability (`within_person_valid`)
- product-use level (`product_level`)
- measurement transfer (`evidence_measurement` → `product_measurement`)

**Validation:** `rag/claim_evidence_registry.py`

### Evidence Lifecycle

```text
external evidence
  → evidence_registry.csv
  → claim_evidence_registry.csv
  → curated synthesis document
  → document verification
  → source_registry approval
  → RAG ingestion
```

Only curated documents with `approved_for_ingestion=TRUE` may be ingested. A document
may remain in the curated corpus while undergoing scientific or provenance remediation.
