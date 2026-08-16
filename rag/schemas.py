"""Shared internal schemas for the Health Coach RAG engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRecord:
    """One approved knowledge source from source_registry.csv."""

    document_id: str
    title: str
    organization: str
    topic: str
    topic_category: str
    source_url: str
    publication_date: str
    retrieval_date: str
    document_type: str
    evidence_level: str
    local_filename: str
    version: str
    approved_for_ingestion: bool
    notes: str
    curated_path: str
