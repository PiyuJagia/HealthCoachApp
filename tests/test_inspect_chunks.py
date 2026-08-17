"""Tests for chunk inspection helpers and CLI discovery."""

from __future__ import annotations

import unittest

from scripts.inspect_chunks import (
    analyze_frontmatter,
    has_yaml_frontmatter,
    inspect_all_registered,
    sample_chunk_indices,
)
from rag.chunker import chunk_markdown_text


class InspectChunksTests(unittest.TestCase):
    def test_sample_chunk_indices_returns_first_middle_and_last(self) -> None:
        indices = sample_chunk_indices(20)
        self.assertEqual(indices[:3], [1, 2, 3])
        self.assertIn(10, indices)
        self.assertIn(11, indices)
        self.assertEqual(indices[-3:], [18, 19, 20])

    def test_has_yaml_frontmatter_detects_leading_yaml(self) -> None:
        text = "---\ndoc_id: sample\n---\n\n# Title\n\nBody"
        self.assertTrue(has_yaml_frontmatter(text))

    def test_analyze_frontmatter_reports_combined_body(self) -> None:
        text = "---\ndoc_id: sample\n---\n\n# Title\n\nBody text."
        documents = chunk_markdown_text(
            text,
            document_id="sample",
            source_title="Sample",
        )
        report = analyze_frontmatter(text, documents)
        self.assertIsNotNone(report)
        assert report is not None
        self.assertTrue(report.combined_with_body)
        self.assertFalse(report.standalone_yaml_chunk)

    def test_inspect_all_registered_returns_four_documents(self) -> None:
        results = inspect_all_registered()
        document_ids = sorted(result.record.document_id for result in results)
        self.assertEqual(
            document_ids,
            [
                "healthcoach_correlation_modeling",
                "healthcoach_safety_scope_escalation",
                "healthcoach_trend_detection",
                "hhs_physical_activity_guidelines_2e",
            ],
        )
        approved_ids = {result.record.document_id for result in results if result.record.approved_for_ingestion}
        self.assertEqual(
            approved_ids,
            {
                "hhs_physical_activity_guidelines_2e",
                "healthcoach_trend_detection",
                "healthcoach_safety_scope_escalation",
            },
        )


if __name__ == "__main__":
    unittest.main()
