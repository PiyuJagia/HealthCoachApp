"""Tests for Markdown chunking."""

from __future__ import annotations

import unittest
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.chunker import (
    MARKDOWN_SEPARATORS,
    MERGE_SIZE_TOLERANCE,
    REQUIRED_METADATA_KEYS,
    chunk_markdown_document,
    chunk_markdown_text,
    is_heading_only_chunk,
    is_meaningful_short_standalone,
    post_process_chunks,
    reindex_chunks,
)
from rag.frontmatter import FrontmatterError, extract_frontmatter
from langchain_core.documents import Document
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
                chunk_size + MERGE_SIZE_TOLERANCE,
                msg="Chunk length materially exceeded configured chunk_size plus merge tolerance.",
            )

    def test_overlap_repeats_boundary_text_on_controlled_fixture(self) -> None:
        repeated = "Boundary marker sentence. " * 50
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=120,
            chunk_overlap=40,
            separators=MARKDOWN_SEPARATORS,
            length_function=len,
        )
        chunk_texts = splitter.split_text(repeated)

        self.assertGreaterEqual(len(chunk_texts), 2)

        first = chunk_texts[0]
        second = chunk_texts[1]
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

    def test_valid_yaml_frontmatter_is_parsed(self) -> None:
        supplemental, body = extract_frontmatter(
            "---\ndoc_id: L2-TD-001\nlayer: L2\nevidence_grade: A\n---\n\n# Title\n"
        )
        self.assertEqual(supplemental["corpus_doc_id"], "L2-TD-001")
        self.assertEqual(supplemental["layer"], "L2")
        self.assertEqual(supplemental["evidence_grade"], "A")
        self.assertTrue(body.startswith("# Title"))

    def test_yaml_is_excluded_from_chunk_page_content(self) -> None:
        text = (
            "---\n"
            "doc_id: L2-TD-001\n"
            "layer: L2\n"
            "sources: [ISO-statistical-methods, Shaffer-2017]\n"
            "---\n\n"
            "# Trend Detection\n\n"
            "Body paragraph about trend detection.\n"
        )
        documents = chunk_markdown_text(text, document_id="healthcoach_trend_detection")
        self.assertFalse(documents[0].page_content.strip().startswith("---"))
        self.assertIn("# Trend Detection", documents[0].page_content)

    def test_whitelisted_yaml_metadata_appears_on_chunks(self) -> None:
        text = (
            "---\n"
            "doc_id: L2-CR-001\n"
            "verification_status: needs_verification\n"
            "metrics: [rhr, sleep_total]\n"
            "---\n\n"
            "# Correlation\n\n"
            "Relationship modeling body.\n"
        )
        documents = chunk_markdown_text(text, document_id="healthcoach_correlation_modeling")
        metadata = documents[0].metadata
        self.assertEqual(metadata["corpus_doc_id"], "L2-CR-001")
        self.assertEqual(metadata["verification_status"], "needs_verification")
        self.assertEqual(metadata["metrics"], "rhr|sleep_total")

    def test_registry_metadata_cannot_be_overwritten_by_yaml(self) -> None:
        text = (
            "---\n"
            "document_id: yaml_override\n"
            "title: YAML Title\n"
            "doc_id: L2-TD-001\n"
            "---\n\n"
            "# Title\n\nBody.\n"
        )
        documents = chunk_markdown_text(
            text,
            document_id="registry_doc_id",
            source_title="Registry Title",
            version="registry-version",
        )
        metadata = documents[0].metadata
        self.assertEqual(metadata["document_id"], "registry_doc_id")
        self.assertEqual(metadata["source_title"], "Registry Title")
        self.assertEqual(metadata["version"], "registry-version")
        self.assertEqual(metadata["corpus_doc_id"], "L2-TD-001")

    def test_malformed_yaml_raises_clear_error(self) -> None:
        with self.assertRaises(FrontmatterError):
            extract_frontmatter("---\ndoc_id: [unclosed\n---\n\n# Title\n")

    def test_document_without_yaml_behaves_unchanged(self) -> None:
        text = FIXTURE_PATH.read_text(encoding="utf-8")
        baseline = chunk_markdown_text(
            text,
            document_id="sample_health_document",
            chunk_size=1200,
            chunk_overlap=200,
        )
        # Re-run through extract path without YAML: body equals original text.
        supplemental, body = extract_frontmatter(text)
        self.assertEqual(supplemental, {})
        self.assertEqual(body, text)
        self.assertEqual(
            [document.page_content for document in baseline],
            [document.page_content for document in chunk_markdown_text(text, document_id="sample_health_document")],
        )

    def test_heading_only_chunk_is_detected(self) -> None:
        self.assertTrue(is_heading_only_chunk("# Chapter 4. Active Adults"))
        self.assertTrue(is_heading_only_chunk("### Recovery and autonomic\n"))
        self.assertFalse(is_heading_only_chunk("# Title\n\nSubstantive body text."))

    def test_heading_only_chunk_merges_with_following_content(self) -> None:
        documents = post_process_chunks(
            [
                Document(
                    page_content="# Chapter 4. Active Adults",
                    metadata={"section_heading": "Chapter 4. Active Adults", "document_id": "doc"},
                ),
                Document(
                    page_content="Adults who are physically active are healthier.",
                    metadata={"section_heading": "Chapter 4. Active Adults", "document_id": "doc"},
                ),
            ],
            chunk_size=1200,
        )
        self.assertEqual(len(documents), 1)
        self.assertIn("# Chapter 4. Active Adults", documents[0].page_content)
        self.assertIn("Adults who are physically active", documents[0].page_content)

    def test_chunk_index_is_recomputed_after_merges(self) -> None:
        documents = reindex_chunks(
            post_process_chunks(
                [
                    Document(page_content="### Heading", metadata={"section_heading": "Heading"}),
                    Document(page_content="Body text.", metadata={"section_heading": "Heading"}),
                    Document(page_content="Another section body.", metadata={"section_heading": "Next"}),
                ],
                chunk_size=1200,
            )
        )
        self.assertEqual([document.metadata["chunk_index"] for document in documents], [1, 2])
        self.assertEqual(documents[0].metadata["total_chunks"], 2)
        self.assertEqual(documents[-1].metadata["chunk_index"], documents[-1].metadata["total_chunks"])

    def test_total_chunks_is_correct_after_merges(self) -> None:
        merged = post_process_chunks(
            [
                Document(page_content="# One", metadata={"section_heading": "One"}),
                Document(page_content="Body one.", metadata={"section_heading": "One"}),
                Document(page_content="# Two", metadata={"section_heading": "Two"}),
                Document(page_content="Body two.", metadata={"section_heading": "Two"}),
            ],
            chunk_size=1200,
        )
        self.assertEqual(len(merged), 2)
        self.assertTrue(all(document.metadata["total_chunks"] == 2 for document in merged))

    def test_safe_tiny_fragment_merge_works(self) -> None:
        documents = post_process_chunks(
            [
                Document(
                    page_content="The primary audience for the Physical Activity Guidelines for",
                    metadata={"section_heading": "Developing the Physical Activity Guidelines"},
                ),
                Document(
                    page_content="Americans is broad and includes policy makers.",
                    metadata={"section_heading": "Developing the Physical Activity Guidelines"},
                ),
            ],
            chunk_size=1200,
        )
        self.assertEqual(len(documents), 1)
        self.assertIn("primary audience", documents[0].page_content)
        self.assertIn("policy makers", documents[0].page_content)

    def test_meaningful_short_section_is_not_blindly_merged(self) -> None:
        text = "## 6. Test cases for CI\n\nEvery build runs these. A failure blocks release."
        self.assertTrue(is_meaningful_short_standalone(text))
        documents = post_process_chunks(
            [
                Document(page_content=text, metadata={"section_heading": "6. Test cases for CI"}),
                Document(page_content="Next section body content.", metadata={"section_heading": "Next"}),
            ],
            chunk_size=1200,
        )
        self.assertEqual(len(documents), 2)

    def test_merged_content_remains_within_documented_size_tolerance(self) -> None:
        heading = "# Chapter 4. Active Adults"
        body = "A" * 1180
        documents = post_process_chunks(
            [
                Document(page_content=heading, metadata={"section_heading": "Chapter 4. Active Adults"}),
                Document(page_content=body, metadata={"section_heading": "Chapter 4. Active Adults"}),
            ],
            chunk_size=1200,
        )
        self.assertEqual(len(documents), 1)
        self.assertLessEqual(len(documents[0].page_content), 1200 + MERGE_SIZE_TOLERANCE)

    def test_all_final_chunks_preserve_required_metadata(self) -> None:
        text = (
            "---\n"
            "doc_id: L2-TD-001\n"
            "layer: L2\n"
            "---\n\n"
            "# Title\n\n"
            "Paragraph one.\n\n"
            "## Section\n\n"
            "Paragraph two.\n"
        )
        documents = chunk_markdown_text(
            text,
            document_id="healthcoach_trend_detection",
            source_title="Trend Detection",
            topic="trend_detection",
            topic_category="integrated_health",
            document_type="curated_evidence_synthesis",
            evidence_level="curated_evidence_synthesis",
            version="L2-TD-001",
        )
        for document in documents:
            for key in REQUIRED_METADATA_KEYS:
                self.assertIn(key, document.metadata)
            self.assertEqual(document.metadata["document_id"], "healthcoach_trend_detection")
            self.assertEqual(document.metadata["corpus_doc_id"], "L2-TD-001")


if __name__ == "__main__":
    unittest.main()
