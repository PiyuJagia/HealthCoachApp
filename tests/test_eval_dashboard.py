"""Lightweight tests for the Assignment 4 TRACE eval dashboard loaders."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from evals.codify.catalog import DETERMINISTIC_SPECS
from evals.dashboard import (
    DashboardDataError,
    official_trace_paths,
    load_dashboard_bundle,
    load_scorecard,
    load_taxonomy_rows,
    run_deterministic_codify,
)

RESULTS_DIR = Path(__file__).resolve().parents[1] / "evals" / "results"


class DashboardLoaderTests(unittest.TestCase):
    def test_scorecard_matches_frozen_counts(self) -> None:
        score = load_scorecard()
        self.assertEqual(score.baseline_pass, 5)
        self.assertEqual(score.baseline_fail, 10)
        self.assertEqual(score.baseline_total, 15)
        self.assertAlmostEqual(score.baseline_pass_rate, 33.3, places=1)
        self.assertEqual(score.v2_pass, 15)
        self.assertEqual(score.v2_fail, 0)
        self.assertEqual(score.v2_needs_review, 0)
        self.assertEqual(score.v2_total, 15)
        self.assertAlmostEqual(score.v2_pass_rate, 100.0, places=1)
        self.assertAlmostEqual(score.improvement_pp, 66.7, places=1)
        self.assertEqual(score.codify_pass, 168)
        self.assertEqual(score.codify_fail, 0)
        self.assertEqual(score.codify_na, 102)
        self.assertEqual(score.codify_evaluations, 270)
        self.assertEqual(score.deterministic_grader_count, 18)
        self.assertEqual(score.deterministic_grader_count, len(DETERMINISTIC_SPECS))

    def test_taxonomy_status_from_f71_mapping(self) -> None:
        rows = {row["id"]: row for row in load_taxonomy_rows()}
        self.assertEqual(len(rows), 12)
        for closed in ("T1", "T2", "T3", "T4", "T5", "T6", "T12"):
            self.assertEqual(rows[closed]["status"], "CLOSED")
        self.assertEqual(rows["T7"]["status"], "IMPROVED")
        self.assertEqual(rows["T8"]["status"], "IMPROVED")
        self.assertEqual(rows["T9"]["status"], "NOT MEANINGFULLY TESTED")
        self.assertEqual(rows["T10"]["status"], "EVAL DESIGN ISSUE")
        self.assertEqual(rows["T11"]["status"], "STILL PRESENT")
        self.assertEqual(rows["T1"]["name"], "Lifestyle context")

    def test_bundle_comparison_has_fifteen_rows(self) -> None:
        bundle = load_dashboard_bundle()
        self.assertEqual(len(bundle.comparison_rows), 15)
        self.assertEqual(bundle.comparison_rows[0]["scenario"], "A1")
        self.assertEqual(bundle.comparison_rows[0]["baseline"], "PASS")
        self.assertEqual(bundle.comparison_rows[4]["scenario"], "B1")
        self.assertEqual(bundle.comparison_rows[4]["baseline"], "FAIL")
        self.assertEqual(bundle.comparison_rows[4]["v2"], "PASS")
        self.assertEqual(len(bundle.grader_rows), 18)
        self.assertEqual(len(bundle.remediation_examples), 5)

    def test_official_traces_exclude_abandoned_503(self) -> None:
        paths = official_trace_paths()
        self.assertEqual(len(paths), 15)
        names = {path.name for path in paths}
        self.assertNotIn("58f212ef-bca3-4628-be17-83a2a9e09489.json", names)
        self.assertIn("acd5ca80-b54f-465e-a92c-e30fcf92853b.json", names)
        self.assertIn("fa304baa-da6e-47a5-b3c1-0cf0af9a3f00.json", names)

    def test_missing_artifact_raises(self) -> None:
        missing = RESULTS_DIR / "__does_not_exist__"
        with self.assertRaises(DashboardDataError):
            load_scorecard(missing)

    def test_run_codify_without_gemini(self) -> None:
        live = run_deterministic_codify()
        self.assertTrue(live["ok"], live.get("error"))
        self.assertIsNone(live["error"])
        self.assertEqual(live["trace_count"], 15)
        self.assertEqual(live["summary"]["deterministic_fail"], 0)
        self.assertEqual(live["summary"]["deterministic_pass"], 168)
        self.assertEqual(live["failed_grader_ids"], [])

    def test_run_codify_missing_dir_is_clean_error(self) -> None:
        live = run_deterministic_codify(RESULTS_DIR / "__does_not_exist__")
        self.assertFalse(live["ok"])
        self.assertTrue(live["error"])
        self.assertEqual(live["failed_grader_ids"], [])


class DashboardCodifyIsolationTests(unittest.TestCase):
    def test_runner_uses_existing_grader_entry_only(self) -> None:
        with patch("evals.dashboard.grade_trace_paths") as grade:
            with patch("evals.dashboard.summarize_grades") as summarize:
                summarize.return_value = {
                    "deterministic_pass": 1,
                    "deterministic_fail": 0,
                    "deterministic_not_applicable": 0,
                    "failed_grader_ids": [],
                }
                grade.return_value = []
                live = run_deterministic_codify()
        self.assertTrue(live["ok"])
        grade.assert_called_once()
        paths = grade.call_args[0][0]
        self.assertEqual(len(paths), 15)
        self.assertTrue(all(path.suffix == ".json" for path in paths))


if __name__ == "__main__":
    unittest.main()
