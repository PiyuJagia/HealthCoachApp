"""Offline tests for Assignment 4 human review bundle artifacts."""

from __future__ import annotations

import csv
import unittest
from pathlib import Path

from evals.baseline_dataset import TRACE_INDEX_PATH, load_baseline_scenarios, validate_baseline_manifest
from evals.human_review_bundle import (
    REVIEW_BUNDLE_PATH,
    REVIEW_PROGRESS_PATH,
    TRACES_DIR,
    build_review_bundle,
    build_review_progress_csv,
    bundle_contains_secrets,
)


class HumanReviewBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle_path = REVIEW_BUNDLE_PATH
        cls.progress_path = build_review_progress_csv()

    def test_all_fifteen_scenarios_present_in_bundle(self) -> None:
        text = self.bundle_path.read_text(encoding="utf-8")
        scenarios = load_baseline_scenarios()
        self.assertEqual(len(scenarios), 15)
        for scenario in scenarios:
            self.assertIn(f"## {scenario.scenario_id}", text)

    def test_each_scenario_maps_to_correct_baseline_trace(self) -> None:
        scenarios = load_baseline_scenarios()
        with TRACE_INDEX_PATH.open(encoding="utf-8", newline="") as handle:
            index_rows = {row["scenario_id"]: row for row in csv.DictReader(handle)}
        for scenario in scenarios:
            row = index_rows[scenario.scenario_id]
            trace_path = TRACES_DIR / row["trace_file"]
            self.assertTrue(trace_path.exists(), msg=f"Missing trace for {scenario.scenario_id}")
            self.assertEqual(row["run_status"], "COMPLETED_PRODUCT_TRACE")

    def test_bundle_contains_no_secrets(self) -> None:
        text = self.bundle_path.read_text(encoding="utf-8")
        self.assertFalse(bundle_contains_secrets(text))

    def test_manual_review_sections_present(self) -> None:
        text = self.bundle_path.read_text(encoding="utf-8")
        self.assertIn("Human open-coding notes:", text)
        self.assertIn("Human PASS / FAIL:", text)
        self.assertIn("Possible failure label:", text)

    def test_completed_human_reviews_present_in_bundle(self) -> None:
        text = self.bundle_path.read_text(encoding="utf-8")
        self.assertIn("PASS on signal detection", text)
        self.assertIn("lifestyle events", text)

    def test_build_review_bundle_refuses_to_overwrite_completed_reviews(self) -> None:
        with self.assertRaises(RuntimeError):
            build_review_bundle()

    def test_review_progress_csv_schema(self) -> None:
        with self.progress_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 15)
        for index, row in enumerate(rows, start=1):
            self.assertEqual(row["review_order"], str(index))

    def test_manifest_manual_fields_still_blank(self) -> None:
        validate_baseline_manifest()


if __name__ == "__main__":
    unittest.main()
