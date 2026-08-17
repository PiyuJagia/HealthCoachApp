"""Pinecone vector store helpers for embedded document chunks."""

from __future__ import annotations

import os
from typing import Any

from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import NotFoundException

from rag.embedder import DEFAULT_EMBEDDING_MODEL, EmbeddedDocument

DEFAULT_INDEX_NAME = "healthcoach-rag"
DEFAULT_NAMESPACE = "healthcoach-knowledge-base"
DEFAULT_DIMENSION = 1536
DEFAULT_METRIC = "cosine"
DEFAULT_CLOUD = "aws"
DEFAULT_REGION = "us-east-1"

CORE_METADATA_FIELDS = (
    "document_id",
    "source_title",
    "organization",
    "topic",
    "topic_category",
    "source_file",
    "document_type",
    "evidence_level",
    "version",
    "chunk_index",
    "total_chunks",
    "section_heading",
)

SUPPLEMENTAL_METADATA_FIELDS = (
    "corpus_doc_id",
    "layer",
    "domain",
    "evidence_grade",
    "verification_status",
    "last_reviewed",
    "source_keys",
    "metrics",
    "entities",
)

RELATIONSHIP_METADATA_FIELDS = (
    "relationship_id",
    "relationship_status",
    "relationship_section_title",
    "evidence_strength",
    "measurement_transfer_risk",
    "max_product_level",
    "recommendation_eligible",
    "modifier_suppressor_only",
    "mandatory_contradiction_suppression",
)

RELATIONSHIP_BOOL_FIELDS = frozenset(
    {
        "recommendation_eligible",
        "modifier_suppressor_only",
        "mandatory_contradiction_suppression",
    }
)

RELATIONSHIP_INT_FIELDS = frozenset({"max_product_level"})


def _require_pinecone_api_key() -> None:
    if not os.getenv("PINECONE_API_KEY", "").strip():
        raise ValueError(
            "PINECONE_API_KEY is not set. Add it to .env before using Pinecone."
        )


def get_index_name() -> str:
    return os.getenv("PINECONE_INDEX_NAME", DEFAULT_INDEX_NAME).strip() or DEFAULT_INDEX_NAME


def get_namespace() -> str:
    return os.getenv("PINECONE_NAMESPACE", DEFAULT_NAMESPACE).strip() or DEFAULT_NAMESPACE


def get_pinecone_client() -> Pinecone:
    _require_pinecone_api_key()
    return Pinecone()


def build_vector_id(document_id: str, chunk_index: int) -> str:
    return f"{document_id}__chunk_{chunk_index:04d}"


def _coerce_relationship_metadata_value(field: str, value: Any) -> str | int | bool:
    """Normalize L2-CR relationship fields to Pinecone-safe scalar types."""
    if field in RELATIONSHIP_BOOL_FIELDS:
        normalized = str(value).strip().lower()
        if normalized in {"yes", "true", "1"}:
            return True
        if normalized in {"no", "false", "0"}:
            return False
        return normalized

    if field in RELATIONSHIP_INT_FIELDS:
        try:
            return int(value)
        except (TypeError, ValueError):
            return str(value).strip()

    return str(value).strip()


def build_vector_metadata(embedded_doc: EmbeddedDocument) -> dict[str, str | int | bool]:
    """Build flat Pinecone metadata for one embedded chunk."""
    source_metadata = embedded_doc.metadata

    metadata: dict[str, str | int | bool] = {
        "text": embedded_doc.page_content,
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "document_id": str(source_metadata["document_id"]),
        "source_title": str(source_metadata.get("source_title", "")),
        "organization": str(source_metadata.get("organization", "")),
        "topic": str(source_metadata.get("topic", "")),
        "topic_category": str(source_metadata.get("topic_category", "")),
        "source_file": str(source_metadata.get("source_file", "")),
        "document_type": str(source_metadata.get("document_type", "")),
        "evidence_level": str(source_metadata.get("evidence_level", "")),
        "version": str(source_metadata.get("version", "")),
        "chunk_index": int(source_metadata["chunk_index"]),
        "total_chunks": int(source_metadata["total_chunks"]),
    }

    for field in ("section_heading", *SUPPLEMENTAL_METADATA_FIELDS):
        value = source_metadata.get(field)
        if value not in (None, ""):
            metadata[field] = str(value)

    for field in RELATIONSHIP_METADATA_FIELDS:
        value = source_metadata.get(field)
        if value in (None, ""):
            continue
        metadata[field] = _coerce_relationship_metadata_value(field, value)

    return metadata


def ensure_index(
    *,
    index_name: str | None = None,
    dimension: int = DEFAULT_DIMENSION,
) -> str:
    """Ensure the Pinecone index exists and matches the expected dimension."""
    resolved_index_name = index_name or get_index_name()
    client = get_pinecone_client()

    if resolved_index_name not in client.indexes.list().names():
        client.indexes.create(
            name=resolved_index_name,
            dimension=dimension,
            metric=DEFAULT_METRIC,
            spec=ServerlessSpec(cloud=DEFAULT_CLOUD, region=DEFAULT_REGION),
        )
        return resolved_index_name

    description = client.indexes.describe(resolved_index_name)
    if description.dimension != dimension:
        raise RuntimeError(
            "Pinecone index dimension mismatch: "
            f"index '{resolved_index_name}' has dimension {description.dimension}, "
            f"expected {dimension}."
        )

    if description.metric != DEFAULT_METRIC:
        raise RuntimeError(
            "Pinecone index metric mismatch: "
            f"index '{resolved_index_name}' uses metric '{description.metric}', "
            f"expected '{DEFAULT_METRIC}'."
        )

    return resolved_index_name


def describe_index_config(*, index_name: str | None = None) -> dict[str, str | int]:
    resolved_index_name = index_name or get_index_name()
    description = get_pinecone_client().indexes.describe(resolved_index_name)

    cloud = DEFAULT_CLOUD
    region = DEFAULT_REGION
    if description.spec and description.spec.serverless:
        cloud = description.spec.serverless.cloud or cloud
        region = description.spec.serverless.region or region

    return {
        "name": resolved_index_name,
        "dimension": description.dimension,
        "metric": description.metric,
        "cloud": cloud,
        "region": region,
    }


def upsert_embedded_documents(
    embedded_documents: list[EmbeddedDocument],
    *,
    namespace: str | None = None,
    index_name: str | None = None,
) -> int:
    if not embedded_documents:
        raise ValueError("Cannot upsert an empty embedded document list.")

    resolved_index_name = ensure_index(index_name=index_name)
    resolved_namespace = namespace if namespace is not None else get_namespace()
    index = get_pinecone_client().index(resolved_index_name)

    vectors = []
    for embedded_doc in embedded_documents:
        chunk_index = int(embedded_doc.metadata["chunk_index"])
        document_id = str(embedded_doc.metadata["document_id"])
        vector_id = build_vector_id(document_id, chunk_index)
        vectors.append(
            (
                vector_id,
                embedded_doc.embedding,
                build_vector_metadata(embedded_doc),
            )
        )

    try:
        response = index.upsert(vectors=vectors, namespace=resolved_namespace)
    except Exception as error:
        raise RuntimeError(f"Pinecone upsert failed: {error}") from error

    return int(response.upserted_count)


def query_similar(
    query_vector: list[float],
    *,
    top_k: int,
    namespace: str | None = None,
    index_name: str | None = None,
):
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    resolved_index_name = index_name or get_index_name()
    resolved_namespace = namespace if namespace is not None else get_namespace()
    index = get_pinecone_client().index(resolved_index_name)

    try:
        response = index.query(
            vector=query_vector,
            top_k=top_k,
            namespace=resolved_namespace,
            include_metadata=True,
        )
    except Exception as error:
        raise RuntimeError(f"Pinecone query failed: {error}") from error

    return list(response.matches)


def delete_document_vectors(
    document_id: str,
    *,
    namespace: str | None = None,
    index_name: str | None = None,
) -> None:
    if not document_id.strip():
        raise ValueError("document_id must not be blank.")

    resolved_index_name = ensure_index(index_name=index_name)
    resolved_namespace = namespace if namespace is not None else get_namespace()
    index = get_pinecone_client().index(resolved_index_name)

    try:
        index.delete(
            filter={"document_id": {"$eq": document_id}},
            namespace=resolved_namespace,
        )
    except NotFoundException:
        return
    except Exception as error:
        raise RuntimeError(
            f"Pinecone document delete failed for document_id '{document_id}': {error}"
        ) from error
