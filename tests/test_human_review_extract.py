"""Offline tests for verified human review extract from markdown bundle."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from evals.failure_taxonomy_analysis import parse_human_review_bundle, parse_human_review_extract
from evals.human_review_extract import EXTRACT_PATH, VERIFY_REPORT_PATH, verify_extract_against_markdown

RESULTS_DIR = Path(__file__).resolve().parent.parent / "evals" / "results"
BUNDLE_PATH = RESULTS_DIR / "baseline_human_review_bundle_v1.md"


class HumanReviewExtractTests(unittest.TestCase):
    def test_markdown_contains_completed_reviews(self) -> None:
        text = BUNDLE_PATH.read_text(encoding="utf-8")
        self.assertIn("PASS on signal detection", text)
        self.assertIn("lifestyle events", text)

    def test_parse_all_fifteen_from_markdown(self) -> None:
        records = parse_human_review_bundle()
        self.assertEqual(len(records), 15)

    def test_baseline_pass_fail_totals_from_markdown(self) -> None:
        records = parse_human_review_bundle()
        passes = sum(1 for record in records if record.normalized_pass_fail == "PASS")
        fails = sum(1 for record in records if record.normalized_pass_fail == "FAIL")
        self.assertEqual(passes, 5)
        self.assertEqual(fails, 10)

    def test_c3_completed_notes_preserved(self) -> None:
        md_records = {record.scenario_id: record for record in parse_human_review_bundle()}
        json_records = {record.scenario_id: record for record in parse_human_review_extract()}
        md_c3 = md_records["HC-EVAL-C3"]
        json_c3 = json_records["HC-EVAL-C3"]

        self.assertTrue(md_c3.human_open_coding_notes.strip())
        self.assertEqual(json_c3.human_open_coding_notes, md_c3.human_open_coding_notes)
        self.assertEqual(md_c3.normalized_pass_fail, "FAIL")
        self.assertEqual(json_c3.normalized_pass_fail, "FAIL")
        self.assertEqual(md_c3.likely_originating_layer, "product limitation")
        self.assertEqual(json_c3.likely_originating_layer, "product limitation")

        payload = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
        extract_c3 = next(item for item in payload["reviews"] if item["scenario_id"] == "HC-EVAL-C3")
        self.assertEqual(extract_c3["human_open_coding_notes"], md_c3.human_open_coding_notes)
        self.assertEqual(extract_c3["human_pass_fail"], "FAIL")
        self.assertEqual(extract_c3["likely_originating_layer"], "product limitation")

        report = json.loads(VERIFY_REPORT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(report["verification_status"], "verified")
        self.assertEqual(report["mismatch_count"], 0)
        self.assertFalse(
            any(mismatch.get("scenario_id") == "HC-EVAL-C3" for mismatch in report.get("mismatches", []))
        )

    def test_verified_extract_matches_markdown(self) -> None:
        self.assertTrue(EXTRACT_PATH.exists(), "Run scripts/extract_human_review_extract.py first")
        payload = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["manifest"]["verification_status"], "verified")
        report = json.loads(VERIFY_REPORT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(report["verification_status"], "verified")
        self.assertEqual(report["mismatch_count"], 0)

        md_records = {record.scenario_id: record for record in parse_human_review_bundle()}
        json_records = {record.scenario_id: record for record in parse_human_review_extract()}
        for scenario_id, md_record in md_records.items():
            json_record = json_records[scenario_id]
            self.assertEqual(json_record.human_open_coding_notes, md_record.human_open_coding_notes)
            self.assertEqual(json_record.normalized_pass_fail, md_record.normalized_pass_fail)


if __name__ == "__main__":
    unittest.main()
