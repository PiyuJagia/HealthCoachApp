"""Tests for Markdown chunking."""

from __future__ import annotations

import unittest
from pathlib import Path

from rag.chunker import REQUIRED_METADATA_KEYS, chunk_markdown_document, chunk_markdown_text
from rag.schemas import SourceRecord

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sample_health_document.md"

SOURCE_RECORD = SourceRecord(
    document_id="sample_health_document",
    title="Synthetic Capstone Fixture Document",
    organization="Capstone Test Lab",
    topic="chunking_validation",
    topic_category="testing",
    source_url="",
    publication_date="2026-08-16",
    retrieval_date="2026-08-16",
    document_type="curated_evidence_synthesis",
    evidence_level="curated_evidence_synthesis",
    local_filename="sample_health_document.md",
    version="fixture-v1",
    approved_for_ingestion=False,
    notes="Synthetic chunking fixture only.",
    curated_path="tests/fixtures/sample_health_document.md",
)


class ChunkerTests(unittest.TestCase):
    def test_blank_text_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            chunk_markdown_text("   ", document_id="sample_doc")

    def test_blank_document_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            chunk_markdown_text("# Title\n\nBody", document_id="  ")

    def test_text_produces_at_least_one_chunk(self) -> None:
        documents = chunk_markdown_text(
            "# Title\n\nA short paragraph.",
            document_id="sample_doc",
        )
        self.assertGreaterEqual(len(documents), 1)

    def test_chunk_index_begins_at_one(self) -> None:
        documents = chunk_markdown_text(
            FIXTURE_PATH.read_text(encoding="utf-8"),
            document_id="sample_health_document",
        )
        self.assertEqual(documents[0].metadata["chunk_index"], 1)

    def test_final_chunk_index_equals_total_chunks(self) -> None:
        documents = chunk_markdown_text(
            FIXTURE_PATH.read_text(encoding="utf-8"),
            document_id="sample_health_document",
        )
        self.assertEqual(
            documents[-1].metadata["chunk_index"],
            documents[-1].metadata["total_chunks"],
        )

    def test_every_chunk_has_required_metadata(self) -> None:
        documents = chunk_markdown_text(
            FIXTURE_PATH.read_text(encoding="utf-8"),
            document_id="sample_health_document",
            source_title="Synthetic Capstone Fixture Document",
            organization="Capstone Test Lab",
            topic="chunking_validation",
            topic_category="testing",
            document_type="curated_evidence_synthesis",
            evidence_level="curated_evidence_synthesis",
            version="fixture-v1",
        )

        for document in documents:
            for key in REQUIRED_METADATA_KEYS:
                self.assertIn(key, document.metadata)

    def test_section_heading_populated_when_heading_exists(self) -> None:
        documents = chunk_markdown_text(
            FIXTURE_PATH.read_text(encoding="utf-8"),
            document_id="sample_health_document",
        )

        headings = {
            document.metadata["section_heading"]
            for document in documents
            if document.metadata["section_heading"]
        }
        self.assertIn("Long Synthetic Section For Splitting", headings)

    def test_source_metadata_is_preserved(self) -> None:
        documents = chunk_markdown_text(
            "# Title\n\nBody text.",
            document_id="sample_doc",
            source_title="Sample Title",
            organization="Sample Org",
            topic="sample_topic",
            topic_category="testing",
            source_file="tests/fixtures/sample.md",
            document_type="fact_sheet",
            evidence_level="professional_guidance",
            version="v1",
        )

        metadata = documents[0].metadata
        self.assertEqual(metadata["source_title"], "Sample Title")
        self.assertEqual(metadata["organization"], "Sample Org")
        self.assertEqual(metadata["topic"], "sample_topic")
        self.assertEqual(metadata["topic_category"], "testing")
        self.assertEqual(metadata["source_file"], "tests/fixtures/sample.md")
        self.assertEqual(metadata["document_type"], "fact_sheet")
        self.assertEqual(metadata["evidence_level"], "professional_guidance")
        self.assertEqual(metadata["version"], "v1")

    def test_max_chunk_length_respects_chunk_size(self) -> None:
        chunk_size = 1200
        documents = chunk_markdown_text(
            FIXTURE_PATH.read_text(encoding="utf-8"),
            document_id="sample_health_document",
            chunk_size=chunk_size,
            chunk_overlap=200,
        )

        for document in documents:
            self.assertLessEqual(
                len(document.page_content),
                chunk_size + 50,
                msg="Chunk length materially exceeded configured chunk_size.",
            )

    def test_overlap_repeats_boundary_text_on_controlled_fixture(self) -> None:
        repeated = "Boundary marker sentence. " * 50
        text = repeated
        documents = chunk_markdown_text(
            text,
            document_id="overlap_doc",
            chunk_size=120,
            chunk_overlap=40,
        )

        self.assertGreaterEqual(len(documents), 2)

        first = documents[0].page_content
        second = documents[1].page_content
        tail = first[-40:]
        self.assertIn(tail[:20], second)

    def test_file_wrapper_delegates_correctly(self) -> None:
        fixture_dir = Path(__file__).resolve().parent / "fixtures"
        temp_path = fixture_dir / "_temp_wrapper_test.md"
        temp_path.write_text("# Wrapper Test\n\nWrapper body text.", encoding="utf-8")
        self.addCleanup(lambda: temp_path.unlink(missing_ok=True))

        documents = chunk_markdown_document(
            temp_path,
            source_record=SOURCE_RECORD,
            project_root=Path(__file__).resolve().parents[1],
        )

        self.assertGreaterEqual(len(documents), 1)
        self.assertEqual(documents[0].metadata["document_id"], SOURCE_RECORD.document_id)
        self.assertEqual(documents[0].metadata["source_title"], SOURCE_RECORD.title)
        self.assertEqual(documents[0].metadata["organization"], SOURCE_RECORD.organization)

    def test_missing_file_raises_clear_error(self) -> None:
        missing_path = Path("tests/fixtures/does_not_exist.md")
        with self.assertRaises(FileNotFoundError):
            chunk_markdown_document(
                missing_path,
                source_record=SOURCE_RECORD,
            )


if __name__ == "__main__":
    unittest.main()
