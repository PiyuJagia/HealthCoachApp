"""Ingest all approved registry documents into Pinecone."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

from rag.ingest import ingest_all_approved
from rag.vector_store import describe_index_config, ensure_index

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    _configure_stdout()
    load_dotenv(PROJECT_ROOT / ".env")

    index_name = ensure_index()
    config = describe_index_config(index_name=index_name)
    results = ingest_all_approved()

    print("Batch ingest complete")
    print("=" * 72)
    print(f"index_name: {config['name']}")
    print(f"dimension: {config['dimension']}")
    print(f"metric: {config['metric']}")
    print(f"documents_ingested: {len(results)}")
    print(f"total_vectors_upserted: {sum(result.vectors_upserted for result in results)}")
    print("-" * 72)
    for result in results:
        print(
            f"{result.document_id} | chunks={result.chunks_created} | "
            f"vectors={result.vectors_upserted} | namespace={result.namespace}"
        )


if __name__ == "__main__":
    main()
