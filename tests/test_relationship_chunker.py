"""Deterministic tests for L2-CR relationship-aware chunking."""

from __future__ import annotations

import unittest
from pathlib import Path

from rag.chunker import chunk_markdown_document, chunk_markdown_text
from rag.registry import get_source_record, list_registered_sources, resolve_curated_path
from rag.relationship_chunker import (
    SAFETY_ENVELOPE_MARKER,
    chunk_has_safety_envelope,
    relationship_chunks,
)
from rag.relationship_policy import can_generate_recommendation

PROJECT_ROOT = Path(__file__).resolve().parent.parent

OTHER_DOCUMENT_BASELINE = {
    "hhs_physical_activity_guidelines_2e": 289,
    "healthcoach_trend_detection": 15,
    "healthcoach_safety_scope_escalation": 14,
}


class RelationshipChunkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        record = get_source_record("healthcoach_correlation_modeling")
        cls.l2cr_path = resolve_curated_path(record, project_root=PROJECT_ROOT)
        cls.l2cr_documents = chunk_markdown_document(
            cls.l2cr_path,
            source_record=record,
            project_root=PROJECT_ROOT,
        )
        cls.relationship_documents = relationship_chunks(cls.l2cr_documents)

    def test_every_active_relationship_produces_chunks(self) -> None:
        relationship_ids = {document.metadata["relationship_id"] for document in self.relationship_documents}
        self.assertEqual(
            relationship_ids,
            {f"R-{index:02d}" for index in range(1, 10)},
        )

    def test_every_relationship_chunk_has_relationship_id_metadata(self) -> None:
        for document in self.relationship_documents:
            self.assertTrue(str(document.metadata.get("relationship_id", "")).startswith("R-"))

    def test_every_relationship_child_has_safety_envelope(self) -> None:
        for document in self.relationship_documents:
            self.assertTrue(
                chunk_has_safety_envelope(document.page_content),
                msg=f"Missing safety envelope in chunk for {document.metadata.get('relationship_id')}",
            )

    def test_every_relationship_child_has_max_product_level(self) -> None:
        for document in self.relationship_documents:
            metadata_level = str(document.metadata.get("max_product_level", ""))
            self.assertTrue(metadata_level)
            self.assertIn("Max level:", document.page_content)
            self.assertIn(metadata_level, document.page_content)

    def test_every_relationship_child_has_contradiction_policy(self) -> None:
        for document in self.relationship_documents:
            self.assertIn("Contradiction/suppression:", document.page_content)

    def test_r02_retains_high_transfer_risk_and_level_two_cap(self) -> None:
        r02_chunks = [d for d in self.relationship_documents if d.metadata["relationship_id"] == "R-02"]
        self.assertGreaterEqual(len(r02_chunks), 1)
        for document in r02_chunks:
            self.assertEqual(document.metadata["measurement_transfer_risk"], "high")
            self.assertEqual(document.metadata["max_product_level"], "2")
            self.assertIn("Transfer risk: high", document.page_content)
            self.assertIn("Max level: 2", document.page_content)
            self.assertIn("High measurement-transfer risk", document.page_content)

    def test_r03_retains_mandatory_contradiction_suppression(self) -> None:
        r03_chunks = [d for d in self.relationship_documents if d.metadata["relationship_id"] == "R-03"]
        for document in r03_chunks:
            self.assertEqual(document.metadata["mandatory_contradiction_suppression"], "yes")
            self.assertIn("Mandatory contradiction suppression", document.page_content)

    def test_r06_retains_high_transfer_risk_and_no_recommendation(self) -> None:
        r06_chunks = [d for d in self.relationship_documents if d.metadata["relationship_id"] == "R-06"]
        for document in r06_chunks:
            self.assertEqual(document.metadata["measurement_transfer_risk"], "high")
            self.assertEqual(document.metadata["recommendation_eligible"], "no")
            self.assertIn("Must not generate recommendations", document.page_content)

    def test_r08_retains_level_two_cap_and_no_alcohol_advice(self) -> None:
        r08_chunks = [d for d in self.relationship_documents if d.metadata["relationship_id"] == "R-08"]
        for document in r08_chunks:
            self.assertEqual(document.metadata["max_product_level"], "2")
            self.assertEqual(document.metadata["recommendation_eligible"], "no")
            self.assertIn("No alcohol advice permitted", document.page_content)

    def test_r09_retains_modifier_suppressor_only_status(self) -> None:
        r09_chunks = [d for d in self.relationship_documents if d.metadata["relationship_id"] == "R-09"]
        for document in r09_chunks:
            self.assertEqual(document.metadata["modifier_suppressor_only"], "yes")
            self.assertIn("Modifier/suppressor only", document.page_content)

    def test_only_r05_and_r07_are_level_four_recommendation_eligible(self) -> None:
        eligible = {
            document.metadata["relationship_id"]
            for document in self.relationship_documents
            if document.metadata.get("recommendation_eligible") == "yes"
        }
        self.assertEqual(eligible, {"R-05", "R-07"})
        self.assertTrue(can_generate_recommendation("R-05"))
        self.assertTrue(can_generate_recommendation("R-07"))

    def test_non_l2cr_documents_retain_existing_chunk_counts(self) -> None:
        for record in list_registered_sources():
            if record.document_id == "healthcoach_correlation_modeling":
                continue
            expected = OTHER_DOCUMENT_BASELINE[record.document_id]
            path = resolve_curated_path(record, project_root=PROJECT_ROOT)
            documents = chunk_markdown_document(path, source_record=record, project_root=PROJECT_ROOT)
            self.assertEqual(
                len(documents),
                expected,
                msg=f"{record.document_id} chunk count changed",
            )
            for document in documents:
                self.assertNotIn("relationship_id", document.metadata)

    def test_non_l2cr_fixture_chunking_unchanged(self) -> None:
        fixture = (
            Path(__file__).resolve().parent / "fixtures" / "sample_health_document.md"
        )
        text = fixture.read_text(encoding="utf-8")
        first = chunk_markdown_text(text, document_id="sample_health_document")
        second = chunk_markdown_text(text, document_id="sample_health_document")
        self.assertEqual(
            [document.page_content for document in first],
            [document.page_content for document in second],
        )


if __name__ == "__main__":
    unittest.main()
