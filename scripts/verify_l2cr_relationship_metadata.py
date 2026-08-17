"""Verify L2-CR relationship metadata persisted in Pinecone after D2.1 re-ingestion."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from rag.vector_store import RELATIONSHIP_METADATA_FIELDS, get_index_name, get_namespace, get_pinecone_client

REPRESENTATIVE_RELATIONSHIPS = ("R-02", "R-03", "R-05", "R-06", "R-08", "R-09")

DOCUMENTS = [
    "hhs_physical_activity_guidelines_2e",
    "healthcoach_trend_detection",
    "healthcoach_correlation_modeling",
    "healthcoach_safety_scope_escalation",
]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    idx = get_pinecone_client().index(get_index_name())
    ns = get_namespace()
    eq = "$eq"
    zero = [0.0] * 1536

    print(f"index={get_index_name()} namespace={ns}")
    print("-" * 72)

    for document_id in DOCUMENTS:
        count = len(
            idx.query(
                vector=zero,
                top_k=10000,
                namespace=ns,
                filter={"document_id": {eq: document_id}},
                include_metadata=True,
            ).matches
            or []
        )
        print(f"{document_id}: {count}")

    l2cr_matches = idx.query(
        vector=zero,
        top_k=10000,
        namespace=ns,
        filter={"document_id": {eq: "healthcoach_correlation_modeling"}},
        include_metadata=True,
    ).matches or []

    versions = sorted({m.metadata.get("version", "") for m in l2cr_matches})
    rel_present = sum(1 for m in l2cr_matches if m.metadata.get("relationship_id"))
    print("-" * 72)
    print(f"L2-CR versions: {versions}")
    print(f"L2-CR vectors with relationship_id: {rel_present} of {len(l2cr_matches)}")

    print("-" * 72)
    print("Representative relationship metadata samples:")
    by_relationship: dict[str, list] = {}
    for match in l2cr_matches:
        relationship_id = match.metadata.get("relationship_id")
        if relationship_id:
            by_relationship.setdefault(str(relationship_id), []).append(match)

    for relationship_id in REPRESENTATIVE_RELATIONSHIPS:
        matches = by_relationship.get(relationship_id, [])
        if not matches:
            print(f"  {relationship_id}: MISSING")
            continue
        meta = matches[0].metadata
        sample = {field: meta.get(field) for field in RELATIONSHIP_METADATA_FIELDS if field in meta}
        print(f"  {relationship_id}: {sample}")

    stats = idx.describe_index_stats()
    total = stats.namespaces[ns].vector_count if stats.namespaces and ns in stats.namespaces else 0
    print("-" * 72)
    print(f"namespace_total: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
