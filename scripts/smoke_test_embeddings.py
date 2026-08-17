"""Smoke-test OpenAI embeddings on a small sample of curated chunks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from rag.chunker import chunk_markdown_document
from rag.embedder import DEFAULT_EMBEDDING_DIMENSION, DEFAULT_EMBEDDING_MODEL, embed_documents
from rag.registry import get_source_record, validate_curated_file_exists

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def smoke_test_embeddings(
    *,
    document_id: str = "healthcoach_trend_detection",
    sample_size: int = 3,
    project_root: Path = PROJECT_ROOT,
) -> None:
    record = get_source_record(document_id)
    source_path = validate_curated_file_exists(record, project_root=project_root)
    documents = chunk_markdown_document(
        source_path,
        source_record=record,
        project_root=project_root,
    )

    sample = documents[:sample_size]
    embedded = embed_documents(sample)

    print("Embedding smoke test")
    print("=" * 72)
    print(f"document_id: {document_id}")
    print(f"model: {DEFAULT_EMBEDDING_MODEL}")
    print(f"expected_dimension: {DEFAULT_EMBEDDING_DIMENSION}")
    print(f"sample_size: {len(embedded)}")
    print(f"pinecone_called: False")

    for item in embedded:
        chunk_index = item.metadata["chunk_index"]
        print("-" * 72)
        print(f"chunk_index: {chunk_index}")
        print(f"section_heading: {item.metadata.get('section_heading', '')}")
        print(f"embedding_length: {len(item.embedding)}")
        print(f"embedding_preview: {item.embedding[:5]}")
        print(f"text_preview: {item.page_content[:160]}...")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test embeddings without Pinecone.")
    parser.add_argument(
        "--document-id",
        default="healthcoach_trend_detection",
        help="Registry document_id to sample chunks from.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=3,
        help="Number of leading chunks to embed.",
    )
    return parser


def main() -> None:
    _configure_stdout()
    load_dotenv(PROJECT_ROOT / ".env")
    args = build_parser().parse_args()
    smoke_test_embeddings(
        document_id=args.document_id,
        sample_size=args.sample_size,
    )


if __name__ == "__main__":
    main()
