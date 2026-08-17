"""Inspect L2-CR relationship-aware chunk boundaries and safety envelopes."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.chunker import chunk_markdown_document, is_heading_only_chunk
from rag.registry import get_source_record, resolve_curated_path
from rag.relationship_chunker import chunk_has_safety_envelope, relationship_chunks

REPRESENTATIVE_IDS = ("R-02", "R-03", "R-05", "R-06", "R-08", "R-09")


def _is_safe_for_independent_retrieval(document) -> bool:
    content = document.page_content
    metadata = document.metadata
    required_content = (
        chunk_has_safety_envelope(content),
        "Association only" in content,
        "Max level:" in content,
        "Contradiction/suppression:" in content,
        bool(metadata.get("relationship_id")),
        bool(metadata.get("max_product_level")),
    )
    return all(required_content)


def main() -> int:
    record = get_source_record("healthcoach_correlation_modeling")
    path = resolve_curated_path(record, project_root=PROJECT_ROOT)
    text = path.read_text(encoding="utf-8")
    documents = chunk_markdown_document(path, source_record=record, project_root=PROJECT_ROOT)
    rel_docs = relationship_chunks(documents)

    print("L2-CR RELATIONSHIP-AWARE CHUNK INSPECTION")
    print("=" * 72)
    print(f"Total document chunks: {len(documents)}")
    print(f"Relationship chunks: {len(rel_docs)}")
    print(f"YAML in first chunk: {'---' in documents[0].page_content[:20]}")
    heading_only = [i for i, d in enumerate(documents, 1) if is_heading_only_chunk(d.page_content)]
    print(f"Heading-only chunks: {heading_only or 'none'}")
    print()

    grouped: dict[str, list] = defaultdict(list)
    for document in rel_docs:
        grouped[str(document.metadata["relationship_id"])].append(document)

    print(
        "relationship_id | parent_chars | child_chunks | min_child | max_child | "
        "envelope_all | safe_independent"
    )
    print("-" * 72)

    for relationship_id in sorted(grouped):
        chunks = grouped[relationship_id]
        lengths = [len(document.page_content) for document in chunks]
        parent_chars = sum(
            len(document.page_content.split("\n\n", 1)[-1]) for document in chunks
        )
        envelope_all = all(chunk_has_safety_envelope(document.page_content) for document in chunks)
        safe_all = all(_is_safe_for_independent_retrieval(document) for document in chunks)
        print(
            f"{relationship_id:15} | {parent_chars:12} | {len(chunks):12} | "
            f"{min(lengths):9} | {max(lengths):9} | "
            f"{'yes' if envelope_all else 'NO':12} | {'yes' if safe_all else 'NO'}"
        )

    print()
    print("REPRESENTATIVE SAFETY-ENVELOPED CHILD CHUNKS")
    print("=" * 72)
    for relationship_id in REPRESENTATIVE_IDS:
        chunks = grouped.get(relationship_id, [])
        if not chunks:
            print(f"\n### {relationship_id} — MISSING")
            continue
        sample = chunks[0]
        print(f"\n### {relationship_id} — chunk 1 of {len(chunks)} ({len(sample.page_content)} chars)")
        print("-" * 72)
        print(sample.page_content)
        print("-" * 72)
        print("metadata:", {k: sample.metadata[k] for k in sorted(sample.metadata) if k in {
            "relationship_id", "relationship_status", "evidence_strength",
            "measurement_transfer_risk", "max_product_level", "recommendation_eligible",
            "modifier_suppressor_only", "mandatory_contradiction_suppression", "section_heading",
        }})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
