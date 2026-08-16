"""Inspect Markdown chunking for the synthetic test fixture."""

from __future__ import annotations

from pathlib import Path

from rag.chunker import chunk_markdown_document
from rag.schemas import SourceRecord

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "sample_health_document.md"

SOURCE_RECORD = SourceRecord(
    document_id="sample_health_document",
    title="Synthetic Capstone Fixture Document",
    organization="Capstone Test Lab",
    topic="chunking_validation",
    topic_category="testing",
    source_url="",
    publication_date="2026-08-16",
    retrieval_date="2026-08-16",
    document_type="curated_evidence_synthesis",
    evidence_level="curated_evidence_synthesis",
    local_filename="sample_health_document.md",
    version="fixture-v1",
    approved_for_ingestion=False,
    notes="Synthetic chunking fixture only.",
    curated_path="tests/fixtures/sample_health_document.md",
)


def main() -> None:
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    documents = chunk_markdown_document(
        FIXTURE_PATH,
        source_record=SOURCE_RECORD,
        project_root=PROJECT_ROOT,
    )

    lengths = [len(document.page_content) for document in documents]
    total_chunks = len(documents)
    min_length = min(lengths)
    max_length = max(lengths)
    average_length = round(sum(lengths) / total_chunks, 1)

    print("Chunk Inspection")
    print("=" * 72)
    print(f"Source file: {FIXTURE_PATH.as_posix()}")
    print(f"Character count: {len(text)}")
    print(f"Total chunks: {total_chunks}")
    print(f"Min chunk length: {min_length}")
    print(f"Max chunk length: {max_length}")
    print(f"Average chunk length: {average_length}")
    print()

    for document in documents:
        metadata = document.metadata
        print("-" * 72)
        print(f"chunk_index: {metadata['chunk_index']}")
        print(f"total_chunks: {metadata['total_chunks']}")
        print(f"section_heading: {metadata['section_heading']}")
        print(f"document_id: {metadata['document_id']}")
        print(f"character length: {len(document.page_content)}")
        print("metadata:")
        for key, value in metadata.items():
            print(f"  {key}: {value}")
        print("chunk text:")
        print(document.page_content)
        print()


if __name__ == "__main__":
    main()
