"""Offline tests for F4.1.1 deterministic contract inspection."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from data.demo_seed import seed_demo_health_data
from evals.contract_inspection import inspect_selected_scenarios, write_inspection_artifacts
from tests.test_helpers import open_test_session


class ContractInspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session, reset=True)
        cls.report = inspect_selected_scenarios(cls.session, cls.user.id)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()

    def _scenario(self, scenario_id: str) -> dict:
        return next(item for item in self.report["scenarios"] if item["scenario_id"] == scenario_id)

    def _metric(self, scenario_id: str, metric: str) -> dict:
        return next(row for row in self._scenario(scenario_id)["metrics"] if row["metric"] == metric)

    def test_inspects_four_scenarios(self) -> None:
        self.assertEqual(len(self.report["scenarios"]), 4)

    def test_no_contract_contradictions(self) -> None:
        self.assertEqual(self.report["contradictions"], [])

    def test_d1_hrv_missing_today_keeps_trend(self) -> None:
        self.assertTrue(self.report["answers"]["d1_hrv_trend_with_missing_today"])
        hrv = self._metric("HC-EVAL-D1", "hrv_sdnn_ms")
        self.assertFalse(hrv["as_of_date_available"])
        self.assertIsNone(hrv["as_of_date_value"])
        self.assertTrue(hrv["claim_eligibility"]["trend_allowed"])

    def test_d2_sync_gap_keeps_history(self) -> None:
        self.assertTrue(self.report["answers"]["d2_history_with_sync_gap"])
        payload = self._scenario("HC-EVAL-D2")["payload"]
        self.assertTrue(payload["gap_caveat_required"])
        self.assertFalse(payload["as_of_any_daily_metric_available"])

    def test_d3_passes_ten_valid_day_rule(self) -> None:
        self.assertTrue(self.report["answers"]["d3_not_blocked_by_old_rule"])

    def test_a1_control_is_established_sleep_decline(self) -> None:
        self.assertTrue(self.report["answers"]["a1_mature_control_normal"])
        sleep = self._metric("HC-EVAL-A1", "sleep_duration_hours")
        self.assertEqual(sleep["data_maturity_state"], "ESTABLISHED_TREND")
        self.assertFalse(sleep["gap_caveat_required"])

    def test_agent_payload_has_no_data_sufficient(self) -> None:
        for scenario in self.report["scenarios"]:
            self.assertFalse(scenario["payload"]["data_sufficient_present"])

    def test_raw_counts_match_contract(self) -> None:
        for scenario in self.report["scenarios"]:
            for row in scenario["metrics"]:
                self.assertEqual(row["observation_count_current"], row["raw_current_count"])
                self.assertEqual(row["baseline_observation_count"], row["raw_baseline_count"])

    def test_write_artifacts(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            paths = write_inspection_artifacts(self.report, Path(tmp))
            payload = json.loads(paths["json"].read_text(encoding="utf-8"))
            self.assertEqual(payload["inspection_id"], "f41_contract_inspection_v1")
            self.assertTrue(paths["csv"].exists())
            self.assertIn("F4.1.1", paths["md"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
