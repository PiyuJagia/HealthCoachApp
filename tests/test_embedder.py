"""Tests for embedding helpers without network calls."""

from __future__ import annotations

import unittest

from langchain_core.documents import Document

from rag.embedder import DEFAULT_EMBEDDING_DIMENSION, EmbeddedDocument, embed_documents
from rag.vector_store import build_vector_id, build_vector_metadata


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


if __name__ == "__main__":
    unittest.main()
