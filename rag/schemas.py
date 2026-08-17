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


@dataclass(frozen=True)
class EvidenceSourceRecord:
    """One external evidence source from evidence_registry.csv."""

    source_key: str
    title: str
    authors_or_organization: str
    publication_year: str
    source_type: str
    doi: str
    pmid: str
    source_url: str
    verification_status: str
    notes: str


@dataclass(frozen=True)
class ClaimEvidenceRecord:
    """One claim-to-source mapping from claim_evidence_registry.csv."""

    claim_id: str
    document_id: str
    section: str
    claim_summary: str
    source_key: str
    support_type: str
    claim_grade: str
    causal_class: str
    within_person_valid: str
    product_level: str
    evidence_measurement: str
    product_measurement: str
    verification_status: str
    verified_date: str
    notes: str


@dataclass(frozen=True)
class RetrievalResult:
    """One retrieved chunk from Pinecone with normalized metadata."""

    vector_id: str
    score: float
    text: str
    document_id: str
    source_title: str
    section_heading: str
    chunk_index: int
    version: str
    evidence_level: str
    evidence_grade: str
    verification_status: str
    relationship_id: str
    relationship_status: str
    evidence_strength: str
    measurement_transfer_risk: str
    max_product_level: str
    recommendation_eligible: str
    modifier_suppressor_only: str
    mandatory_contradiction_suppression: str
