# Knowledge Corpus

This folder holds the Health Coach knowledge corpus.

## Directories

| Folder | Purpose | Git policy |
|--------|---------|------------|
| `raw/` | Original PDFs and source binaries | Contents ignored; folder tracked via `.gitkeep` |
| `extracted/` | Automated extraction output | Contents ignored; folder tracked via `.gitkeep` |
| `curated/` | Approved Markdown for RAG ingestion | Tracked in Git |
| `registry/` | `source_registry.csv` metadata and approval flags | Tracked in Git |

## Workflow

```text
raw → extracted → curated → registry approval → RAG ingestion
```

Only curated Markdown with `approved_for_ingestion=TRUE` in the registry is eligible
for ingestion.
