"""Query Pinecone for relevant knowledge chunks — no LLM completion."""

from __future__ import annotations

import os
from typing import Any

from rag.embedder import embed_query
from rag.schemas import RetrievalResult
from rag.vector_store import get_index_name, get_namespace, query_similar

DEFAULT_TOP_K = 3
DEFAULT_MIN_RELEVANCE_SCORE = 0.35


def get_top_k() -> int:
    """Return configured retrieval count (env RAG_TOP_K or default)."""
    raw = os.getenv("RAG_TOP_K", str(DEFAULT_TOP_K)).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"RAG_TOP_K must be an integer; got '{raw}'.") from error
    if value < 1:
        raise ValueError("RAG_TOP_K must be at least 1.")
    return value


def get_min_relevance_score() -> float:
    """Return configured minimum cosine score (env RAG_MIN_RELEVANCE_SCORE or default)."""
    raw = os.getenv("RAG_MIN_RELEVANCE_SCORE", str(DEFAULT_MIN_RELEVANCE_SCORE)).strip()
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"RAG_MIN_RELEVANCE_SCORE must be a number; got '{raw}'.") from error
    if not 0.0 <= value <= 1.0:
        raise ValueError("RAG_MIN_RELEVANCE_SCORE must be between 0.0 and 1.0.")
    return value


def _metadata_str(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _metadata_int(metadata: dict[str, Any], key: str) -> int:
    value = metadata.get(key)
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def map_match_to_result(match: Any) -> RetrievalResult:
    """Map a Pinecone match object into a RetrievalResult."""
    metadata = match.metadata or {}
    return RetrievalResult(
        vector_id=str(match.id),
        score=float(match.score or 0.0),
        text=_metadata_str(metadata, "text"),
        document_id=_metadata_str(metadata, "document_id"),
        source_title=_metadata_str(metadata, "source_title"),
        section_heading=_metadata_str(metadata, "section_heading"),
        chunk_index=_metadata_int(metadata, "chunk_index"),
        version=_metadata_str(metadata, "version"),
        evidence_level=_metadata_str(metadata, "evidence_level"),
        evidence_grade=_metadata_str(metadata, "evidence_grade"),
        verification_status=_metadata_str(metadata, "verification_status"),
        relationship_id=_metadata_str(metadata, "relationship_id"),
        relationship_status=_metadata_str(metadata, "relationship_status"),
        evidence_strength=_metadata_str(metadata, "evidence_strength"),
        measurement_transfer_risk=_metadata_str(metadata, "measurement_transfer_risk"),
        max_product_level=_metadata_str(metadata, "max_product_level"),
        recommendation_eligible=_metadata_str(metadata, "recommendation_eligible"),
        modifier_suppressor_only=_metadata_str(metadata, "modifier_suppressor_only"),
        mandatory_contradiction_suppression=_metadata_str(
            metadata, "mandatory_contradiction_suppression"
        ),
    )


def filter_by_min_score(
    results: list[RetrievalResult],
    *,
    min_score: float,
) -> list[RetrievalResult]:
    """Keep only results at or above the relevance threshold."""
    return [result for result in results if result.score >= min_score]


def retrieve(
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
    index_name: str | None = None,
    namespace: str | None = None,
) -> list[RetrievalResult]:
    """
    Embed a query, search Pinecone, and return scored chunks above min_score.

    Does not call any chat/LLM completion or synthesize an answer.
    """
    if not query.strip():
        raise ValueError("Query must not be blank.")

    resolved_top_k = top_k if top_k is not None else get_top_k()
    resolved_min_score = min_score if min_score is not None else get_min_relevance_score()

    if resolved_top_k < 1:
        raise ValueError("top_k must be at least 1.")

    query_vector = embed_query(query)
    matches = query_similar(
        query_vector,
        top_k=resolved_top_k,
        index_name=index_name,
        namespace=namespace,
    )

    results = [map_match_to_result(match) for match in matches]
    return filter_by_min_score(results, min_score=resolved_min_score)


def retrieve_with_config(query: str) -> list[RetrievalResult]:
    """Convenience wrapper using environment defaults for top_k and min_score."""
    return retrieve(query)


def describe_retrieval_config() -> dict[str, str | int | float]:
    """Return active retrieval configuration for logging and smoke tests."""
    return {
        "index_name": get_index_name(),
        "namespace": get_namespace(),
        "top_k": get_top_k(),
        "min_relevance_score": get_min_relevance_score(),
    }
