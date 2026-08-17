"""Verify Pinecone vector counts and L2-CR version metadata."""

from dotenv import load_dotenv

load_dotenv(".env")

from rag.vector_store import get_index_name, get_namespace, get_pinecone_client

idx = get_pinecone_client().index(get_index_name())
ns = get_namespace()
z = [0.0] * 1536
eq = "$eq"

documents = [
    "hhs_physical_activity_guidelines_2e",
    "healthcoach_trend_detection",
    "healthcoach_correlation_modeling",
    "healthcoach_safety_scope_escalation",
]

print(f"index={get_index_name()} namespace={ns}")
print("-" * 60)
for document_id in documents:
    matches = idx.query(
        vector=z,
        top_k=10000,
        namespace=ns,
        filter={"document_id": {eq: document_id}},
        include_metadata=True,
    ).matches or []
    print(f"{document_id}: {len(matches)}")
    if document_id == "healthcoach_correlation_modeling":
        versions = sorted({m.metadata.get("version", "") for m in matches})
        corpus_ids = sorted({m.metadata.get("corpus_doc_id", "") for m in matches})
        verification = sorted({m.metadata.get("verification_status", "") for m in matches})
        print(f"  versions: {versions}")
        print(f"  corpus_doc_id: {corpus_ids}")
        print(f"  verification_status: {verification}")
        rel_chunks = sum(1 for m in matches if m.metadata.get("relationship_id"))
        print(f"  relationship_id metadata present: {rel_chunks} of {len(matches)}")

stats = idx.describe_index_stats()
namespace_stats = stats.namespaces.get(ns) if stats.namespaces else None
total = namespace_stats.vector_count if namespace_stats else 0
print("-" * 60)
print(f"namespace_total: {total}")
