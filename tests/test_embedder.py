"""Tests for embedding helpers without network calls."""

from __future__ import annotations

import unittest

from langchain_core.documents import Document

from rag.embedder import DEFAULT_EMBEDDING_DIMENSION, EmbeddedDocument, embed_documents
from rag.vector_store import (
    RELATIONSHIP_METADATA_FIELDS,
    build_vector_id,
    build_vector_metadata,
)


class EmbedderTests(unittest.TestCase):
    def test_embed_documents_rejects_empty_list(self) -> None:
        with self.assertRaises(ValueError):
            embed_documents([])

    def test_embed_documents_rejects_blank_page_content(self) -> None:
        with self.assertRaises(ValueError):
            embed_documents([Document(page_content="   ", metadata={"document_id": "doc"})])


class VectorStoreTests(unittest.TestCase):
    def test_build_vector_id_is_stable(self) -> None:
        self.assertEqual(
            build_vector_id("healthcoach_trend_detection", 7),
            "healthcoach_trend_detection__chunk_0007",
        )

    def test_build_vector_metadata_includes_core_and_supplemental_fields(self) -> None:
        embedded = EmbeddedDocument(
            page_content="Sample chunk text.",
            metadata={
                "document_id": "healthcoach_trend_detection",
                "source_title": "Trend Detection",
                "organization": "",
                "topic": "trend_detection",
                "topic_category": "integrated_health",
                "source_file": "knowledge/curated/healthcoach_trend_detection.md",
                "document_type": "curated_evidence_synthesis",
                "evidence_level": "curated_evidence_synthesis",
                "version": "L2-TD-001",
                "chunk_index": 1,
                "total_chunks": 15,
                "section_heading": "Trend Detection & Signal Processing",
                "corpus_doc_id": "L2-TD-001",
                "layer": "L2",
                "source_keys": "ISO-statistical-methods|Shaffer-2017",
            },
            embedding=[0.1] * DEFAULT_EMBEDDING_DIMENSION,
        )

        metadata = build_vector_metadata(embedded)
        self.assertEqual(metadata["document_id"], "healthcoach_trend_detection")
        self.assertEqual(metadata["corpus_doc_id"], "L2-TD-001")
        self.assertEqual(metadata["source_keys"], "ISO-statistical-methods|Shaffer-2017")
        self.assertEqual(metadata["text"], "Sample chunk text.")
        for field in RELATIONSHIP_METADATA_FIELDS:
            self.assertNotIn(field, metadata)

    def test_build_vector_metadata_includes_relationship_fields_when_present(self) -> None:
        embedded = EmbeddedDocument(
            page_content="[L2-CR Safety Envelope | R-02]\n\nRelationship body.",
            metadata={
                "document_id": "healthcoach_correlation_modeling",
                "source_title": "Correlation Modeling",
                "organization": "",
                "topic": "correlation_modeling",
                "topic_category": "integrated_health",
                "source_file": "knowledge/curated/healthcoach_correlation_modeling.md",
                "document_type": "curated_evidence_synthesis",
                "evidence_level": "curated_evidence_synthesis",
                "version": "L2-CR-002",
                "chunk_index": 17,
                "total_chunks": 89,
                "section_heading": "R-02 · Sleep duration and HRV",
                "relationship_id": "R-02",
                "relationship_status": "ACTIVE",
                "relationship_section_title": "R-02 · Sleep duration and HRV",
                "evidence_strength": "C−",
                "measurement_transfer_risk": "high",
                "max_product_level": "2",
                "recommendation_eligible": "no",
                "modifier_suppressor_only": "no",
                "mandatory_contradiction_suppression": "no",
            },
            embedding=[0.1] * DEFAULT_EMBEDDING_DIMENSION,
        )

        metadata = build_vector_metadata(embedded)
        self.assertEqual(metadata["relationship_id"], "R-02")
        self.assertEqual(metadata["relationship_status"], "ACTIVE")
        self.assertEqual(metadata["evidence_strength"], "C−")
        self.assertEqual(metadata["measurement_transfer_risk"], "high")
        self.assertIsInstance(metadata["max_product_level"], int)
        self.assertEqual(metadata["max_product_level"], 2)
        self.assertIs(metadata["recommendation_eligible"], False)
        self.assertIs(metadata["modifier_suppressor_only"], False)
        self.assertIs(metadata["mandatory_contradiction_suppression"], False)

    def test_build_vector_metadata_omits_missing_optional_relationship_fields(self) -> None:
        embedded = EmbeddedDocument(
            page_content="Generic section without relationship metadata.",
            metadata={
                "document_id": "healthcoach_correlation_modeling",
                "source_title": "Correlation Modeling",
                "organization": "",
                "topic": "correlation_modeling",
                "topic_category": "integrated_health",
                "source_file": "knowledge/curated/healthcoach_correlation_modeling.md",
                "document_type": "curated_evidence_synthesis",
                "evidence_level": "curated_evidence_synthesis",
                "version": "L2-CR-002",
                "chunk_index": 1,
                "total_chunks": 89,
                "section_heading": "How to read this document",
            },
            embedding=[0.1] * DEFAULT_EMBEDDING_DIMENSION,
        )

        metadata = build_vector_metadata(embedded)
        for field in RELATIONSHIP_METADATA_FIELDS:
            self.assertNotIn(field, metadata)

    def test_build_vector_metadata_coerces_yes_no_bools_for_r03_suppression(self) -> None:
        embedded = EmbeddedDocument(
            page_content="R-03 chunk",
            metadata={
                "document_id": "healthcoach_correlation_modeling",
                "source_title": "Correlation Modeling",
                "organization": "",
                "topic": "correlation_modeling",
                "topic_category": "integrated_health",
                "source_file": "knowledge/curated/healthcoach_correlation_modeling.md",
                "document_type": "curated_evidence_synthesis",
                "evidence_level": "curated_evidence_synthesis",
                "version": "L2-CR-002",
                "chunk_index": 20,
                "total_chunks": 89,
                "section_heading": "R-03 · Acute training load and HRV",
                "relationship_id": "R-03",
                "relationship_status": "ACTIVE",
                "relationship_section_title": "R-03 · Acute training load and HRV",
                "evidence_strength": "B",
                "measurement_transfer_risk": "moderate",
                "max_product_level": "2",
                "recommendation_eligible": "no",
                "modifier_suppressor_only": "no",
                "mandatory_contradiction_suppression": "yes",
            },
            embedding=[0.1] * DEFAULT_EMBEDDING_DIMENSION,
        )

        metadata = build_vector_metadata(embedded)
        self.assertIs(metadata["mandatory_contradiction_suppression"], True)
        self.assertEqual(metadata["max_product_level"], 2)


if __name__ == "__main__":
    unittest.main()
