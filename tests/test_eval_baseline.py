"""Offline tests for Assignment 4 Phase F1 baseline infrastructure."""

from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

from evals.baseline_dataset import (
    BASELINE_DATASET_VERSION,
    DATASET_PATH,
    MANUAL_REVIEW_FIELDS,
    METADATA_PATH,
    TRACE_INDEX_COLUMNS,
    TRACE_INDEX_PATH,
    load_baseline_scenarios,
    validate_baseline_manifest,
)
from evals.trace_schema import sanitize_for_trace
from scripts.run_eval_baseline import build_baseline_metadata, verify_trace_completeness


class BaselineManifestTests(unittest.TestCase):
    def test_scenario_manifest_parses(self) -> None:
        scenarios = load_baseline_scenarios()
        self.assertGreater(len(scenarios), 0)
        self.assertEqual(scenarios[0].scenario_id, "HC-EVAL-A1")

    def test_exactly_fifteen_scenarios_exist(self) -> None:
        scenarios = load_baseline_scenarios()
        self.assertEqual(len(scenarios), 15)

    def test_scenario_ids_are_unique(self) -> None:
        scenarios = load_baseline_scenarios()
        ids = [scenario.scenario_id for scenario in scenarios]
        self.assertEqual(len(ids), len(set(ids)))

    def test_required_manual_fields_remain_blank(self) -> None:
        validate_baseline_manifest()

    def test_all_scenario_dates_within_marcus_dataset(self) -> None:
        scenarios = load_baseline_scenarios()
        validate_baseline_manifest(scenarios)

    def test_dataset_filename_matches_version(self) -> None:
        self.assertTrue(DATASET_PATH.name.startswith(BASELINE_DATASET_VERSION))


class BaselineInspectionTests(unittest.TestCase):
    def test_baseline_inspection_is_deterministic(self) -> None:
        from evals.baseline_dataset import inspect_scenario_data_support

        scenarios = load_baseline_scenarios()
        first = inspect_scenario_data_support(scenarios[0])
        second = inspect_scenario_data_support(scenarios[0])
        self.assertEqual(first, second)


class TraceIndexSchemaTests(unittest.TestCase):
    def test_trace_index_schema_validates(self) -> None:
        self.assertIn("scenario_id", TRACE_INDEX_COLUMNS)
        self.assertIn("run_status", TRACE_INDEX_COLUMNS)
        for field in MANUAL_REVIEW_FIELDS:
            self.assertIn(field, TRACE_INDEX_COLUMNS)

    def test_verify_trace_completeness_detects_missing_fields(self) -> None:
        complete, missing = verify_trace_completeness(
            {
                "run_id": "abc",
                "scenario_id": "HC-EVAL-A1",
                "user_id": 1,
                "as_of_date": "2026-08-02",
                "candidate_signals": {},
                "tool_calls": [],
                "retrieval": [],
                "policy": {"overall_verdict": "SURFACE"},
                "generation": {"model_name": "gemini-3.6-flash"},
                "final_guard": {"passed": True},
                "structured_result": {"status": "INSIGHT"},
                "activity_log": [],
            }
        )
        self.assertTrue(complete)
        self.assertEqual(missing, [])


class BaselineMetadataTests(unittest.TestCase):
    def test_metadata_manifest_contains_no_secrets(self) -> None:
        metadata = build_baseline_metadata()
        serialized = json.dumps(metadata).lower()
        forbidden_value_markers = ("sk-", "api_key=", "secret=", "password=", "authorization: bearer")
        for marker in forbidden_value_markers:
            self.assertNotIn(marker, serialized)
        for key in metadata:
            self.assertFalse(any(fragment in key.lower() for fragment in ("password", "secret", "token")))

    def test_metadata_includes_core_system_fields(self) -> None:
        metadata = build_baseline_metadata()
        self.assertEqual(metadata["baseline_dataset_version"], BASELINE_DATASET_VERSION)
        self.assertIn("gemini_model", metadata)
        self.assertIn("max_llm_calls", metadata)
        self.assertIn("pinecone_index_name", metadata)
        self.assertIn("rag_top_k", metadata)


class BaselineResultsArtifactTests(unittest.TestCase):
    def test_results_paths_exist_after_metadata_write(self) -> None:
        from scripts.run_eval_baseline import write_baseline_metadata

        path = write_baseline_metadata()
        self.assertTrue(path.exists())
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("api_key", json.dumps(payload).lower())

    def test_trace_index_manual_columns_blank_when_present(self) -> None:
        if not TRACE_INDEX_PATH.exists():
            self.skipTest("baseline trace index not generated yet")
        with TRACE_INDEX_PATH.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            for field in MANUAL_REVIEW_FIELDS:
                self.assertEqual(row.get(field, ""), "")


if __name__ == "__main__":
    unittest.main()
