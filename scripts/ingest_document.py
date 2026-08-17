"""Ingest one approved registry document into Pinecone."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from rag.ingest import ingest_document_record

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest one approved document.")
    parser.add_argument("--document-id", required=True, help="Registry document_id.")
    return parser


def main() -> None:
    _configure_stdout()
    load_dotenv(PROJECT_ROOT / ".env")
    args = build_parser().parse_args()
    result = ingest_document_record(args.document_id)

    print("Ingest complete")
    print("=" * 72)
    print(f"document_id: {result.document_id}")
    print(f"chunks_created: {result.chunks_created}")
    print(f"vectors_upserted: {result.vectors_upserted}")
    print(f"index_name: {result.index_name}")
    print(f"namespace: {result.namespace}")


if __name__ == "__main__":
    main()
