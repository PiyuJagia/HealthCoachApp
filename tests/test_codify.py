"""Offline tests for the CODIFY evaluation framework. No Gemini."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from evals.codify.catalog import DETERMINISTIC_SPECS, SEMANTIC_SPECS, all_specs
from evals.codify.deterministic import (
    DETERMINISTIC_GRADERS,
    f41_established_trend_requires_trend_allowed,
    f43_weekly_cannot_bypass_trend_eligibility,
    f44_lifestyle_inputs_require_lookup,
    f45_maintenance_of_gain_may_surface,
    f46_t5_unworthy_not_elevated,
    f47_rec_phrase_leak_when_blocked,
    f47_recommendation_requires_both_gates,
    f48_t6_control_not_primary,
    f49_t12_spread_distinct_from_level,
    f51_facts_are_system_stamped,
    f51_output_contract_shape,
    f51a_quote_null_on_quiet_path,
    scenario_a_family_mature_data,
    scenario_b1_quiet_path,
    scenario_b3_maintenance_without_rec,
    scenario_c4_spread_distinct,
    scenario_e1_rr_control,
)
from evals.codify.runner import (
    F52_TRACE_DIR,
    coverage_matrix,
    grade_trace,
    grade_trace_directory,
    summarize_grades,
    write_coverage_artifacts,
)
from evals.codify.schema import (
    GRADER_DETERMINISTIC,
    GRADER_LLM_AS_JUDGE,
    OUTCOME_FAIL,
    OUTCOME_NOT_APPLICABLE,
    OUTCOME_PASS,
    GraderResult,
)
from evals.failure_taxonomy_analysis import parse_human_review_extract
from evals.human_review_extract import EXTRACT_PATH

RESULTS_DIR = Path(__file__).resolve().parents[1] / "evals" / "results"


def _trend(
    metric: str,
    *,
    direction: str = "stable",
    maturity: str = "ESTABLISHED_TREND",
    trend_allowed: bool = True,
    rec_support: bool = True,
    as_of: bool = True,
    gap: bool = False,
    control: bool = False,
    insight_candidate: bool = False,
    recommendation_candidate: bool = False,
    maintenance_of_gain: bool = False,
    spread: dict | None = None,
) -> dict:
    return {
        "metric": metric,
        "direction": direction,
        "data_maturity_state": maturity,
        "as_of_date_available": as_of,
        "gap_caveat_required": gap,
        "control_metric": control,
        "insight_candidate": insight_candidate,
        "recommendation_candidate": recommendation_candidate,
        "claim_eligibility": {
            "trend_allowed": trend_allowed,
            "recommendation_support_allowed": rec_support,
        },
        "longitudinal": {"maintenance_of_gain": maintenance_of_gain},
        "within_window_spread": spread,
    }


def _trace(
    scenario_id: str = "HC-EVAL-A1",
    *,
    status: str = "INSIGHT",
    insight_worthy: bool = True,
    recommendation_worthy: bool = False,
    recommendation_authorized: bool = False,
    allowed: bool | None = None,
    primary: str | None = "Sleep duration decreased this week.",
    quote: str | None = "Consistency builds progress.",
    recommendation: str | None = None,
    insight: str | None = "Sleep duration decreased relative to baseline.",
    trends: list[dict] | None = None,
    primary_metrics: list[str] | None = None,
    control_metrics: list[str] | None = None,
    reasons: list[str] | None = None,
    weekly: list[dict] | None = None,
    lifestyle_called: bool = False,
    lifestyle_inputs: list[str] | None = None,
    facts: list[dict] | None = None,
    facts_origin: str = "deterministic_output_contract",
    run_id: str = "test-run",
) -> dict:
    if allowed is None:
        allowed = bool(recommendation_worthy and recommendation_authorized)
    rows = trends if trends is not None else [_trend("sleep_duration_hours", direction="decreasing", insight_candidate=True)]
    payload = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "structured_result": {
            "status": status,
            "primary_message": primary,
            "subtext": None,
            "motivational_quote": quote,
            "insight": insight,
            "recommendation": recommendation,
            "recommendation_worthy": recommendation_worthy,
            "recommendation_authorized": recommendation_authorized,
            "final_recommendation_allowed": allowed,
            "supporting_metric_facts": facts or [],
        },
        "output_contract": {
            "supporting_metric_facts_origin": facts_origin,
            "supporting_metric_facts": facts or [],
        },
        "recommendation_boundary": {
            "recommendation_worthy": recommendation_worthy,
            "recommendation_authorized": recommendation_authorized,
            "final_recommendation_allowed": allowed,
        },
        "candidate_signals": {
            "insight_salience": {
                "insight_worthy": insight_worthy,
                "recommendation_worthy": recommendation_worthy,
                "primary_metrics": primary_metrics or ["sleep_duration_hours"],
                "control_metrics": control_metrics or [],
                "reasons": reasons or [],
            },
            "trends": rows,
            "weekly_summaries": weekly or [],
        },
        "tool_calls": [{"tool_name": "get_trend_signals"}],
        "activity_log": [{"tool": "get_trend_signals"}],
        "model_calls": [],
    }
    if lifestyle_called:
        payload["tool_calls"].append({"tool_name": "get_lifestyle_context"})
        payload["model_calls"].append(
            {
                "lifestyle_context_visible": {"policy_available_inputs": lifestyle_inputs or []},
                "rag_evidence_visible": {"available_inputs": lifestyle_inputs or []},
            }
        )
    elif lifestyle_inputs:
        payload["model_calls"].append(
            {
                "lifestyle_context_visible": {},
                "rag_evidence_visible": {"available_inputs": lifestyle_inputs},
            }
        )
    return payload


class SchemaTests(unittest.TestCase):
    def test_result_rejects_invalid_outcome(self) -> None:
        result = GraderResult(
            scenario_id="HC-EVAL-A1",
            grader_id="demo",
            grader_type=GRADER_DETERMINISTIC,
            contract="F4.1",
            taxonomy=None,
            outcome="maybe",
            observed_value=None,
            expected_behavior="x",
            evidence={},
            reason="x",
        )
        with self.assertRaises(ValueError):
            result.to_dict()

    def test_catalog_has_expected_types(self) -> None:
        self.assertGreaterEqual(len(DETERMINISTIC_SPECS), 14)
        self.assertGreaterEqual(len(SEMANTIC_SPECS), 6)
        self.assertTrue(all(item.executable for item in DETERMINISTIC_SPECS))
        self.assertTrue(all(not item.executable for item in SEMANTIC_SPECS))
        self.assertTrue(any(item.grader_type == GRADER_LLM_AS_JUDGE for item in SEMANTIC_SPECS))
        ids = [item.grader_id for item in all_specs()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("sem_c2_single_cause_deterministic", ids)


class DeterministicGraderTests(unittest.TestCase):
    def test_f41_pass_and_fail(self) -> None:
        ok = f41_established_trend_requires_trend_allowed(_trace())
        self.assertEqual(ok.outcome, OUTCOME_PASS)
        bad = f41_established_trend_requires_trend_allowed(
            _trace(trends=[_trend("vo2_max", maturity="ESTABLISHED_TREND", trend_allowed=False)])
        )
        self.assertEqual(bad.outcome, OUTCOME_FAIL)

    def test_f43_weekly_bypass_fails(self) -> None:
        weekly = [
            {
                "coverage": {
                    "sleep_duration_hours": {
                        "metric": "sleep_duration_hours",
                        "claim_semantics": {
                            "summary_comparison_allowed": True,
                            "summary_recommendation_support_allowed": True,
                        },
                    }
                }
            }
        ]
        bad = f43_weekly_cannot_bypass_trend_eligibility(
            _trace(
                trends=[_trend("sleep_duration_hours", trend_allowed=False, rec_support=False)],
                weekly=weekly,
            )
        )
        self.assertEqual(bad.outcome, OUTCOME_FAIL)
        good = f43_weekly_cannot_bypass_trend_eligibility(
            _trace(
                weekly=[
                    {
                        "coverage": {
                            "sleep_duration_hours": {
                                "metric": "sleep_duration_hours",
                                "claim_semantics": {
                                    "summary_comparison_allowed": False,
                                    "summary_recommendation_support_allowed": False,
                                },
                            }
                        }
                    }
                ]
            )
        )
        self.assertEqual(good.outcome, OUTCOME_PASS)

    def test_f44_lifestyle_inputs_require_lookup(self) -> None:
        missing = f44_lifestyle_inputs_require_lookup(_trace(lifestyle_inputs=["caffeine_mg"]))
        self.assertEqual(missing.outcome, OUTCOME_FAIL)
        present = f44_lifestyle_inputs_require_lookup(
            _trace(lifestyle_called=True, lifestyle_inputs=["caffeine_mg"])
        )
        self.assertEqual(present.outcome, OUTCOME_PASS)
        none = f44_lifestyle_inputs_require_lookup(_trace())
        self.assertEqual(none.outcome, OUTCOME_NOT_APPLICABLE)

    def test_f45_maintenance_cannot_be_quieted(self) -> None:
        quiet = f45_maintenance_of_gain_may_surface(
            _trace(
                status="NO_SIGNIFICANT_NEW_PATTERN",
                primary=None,
                quote=None,
                insight_worthy=True,
                reasons=["maintenance_of_gain"],
                trends=[_trend("hrv_sdnn_ms", maintenance_of_gain=True, insight_candidate=True)],
            )
        )
        self.assertEqual(quiet.outcome, OUTCOME_FAIL)
        surfaced = f45_maintenance_of_gain_may_surface(
            _trace(
                status="INSIGHT",
                insight_worthy=True,
                reasons=["maintenance_of_gain"],
                trends=[_trend("hrv_sdnn_ms", maintenance_of_gain=True, insight_candidate=True)],
            )
        )
        self.assertEqual(surfaced.outcome, OUTCOME_PASS)

    def test_f46_unworthy_cannot_elevate(self) -> None:
        bad = f46_t5_unworthy_not_elevated(_trace(insight_worthy=False, status="INSIGHT"))
        self.assertEqual(bad.outcome, OUTCOME_FAIL)
        good = f46_t5_unworthy_not_elevated(
            _trace(
                insight_worthy=False,
                status="NO_SIGNIFICANT_NEW_PATTERN",
                primary=None,
                quote=None,
            )
        )
        self.assertEqual(good.outcome, OUTCOME_PASS)

    def test_f47_combined_gate(self) -> None:
        leak = f47_recommendation_requires_both_gates(
            _trace(
                recommendation_worthy=False,
                recommendation_authorized=True,
                allowed=False,
                recommendation="Walk more.",
            )
        )
        self.assertEqual(leak.outcome, OUTCOME_FAIL)
        stamp_mismatch = f47_recommendation_requires_both_gates(
            _trace(
                recommendation_worthy=True,
                recommendation_authorized=False,
                allowed=True,
            )
        )
        self.assertEqual(stamp_mismatch.outcome, OUTCOME_FAIL)
        blocked_clean = f47_recommendation_requires_both_gates(
            _trace(recommendation_worthy=False, recommendation_authorized=True, allowed=False)
        )
        self.assertEqual(blocked_clean.outcome, OUTCOME_PASS)

    def test_f47_existing_phrase_leak_only_when_blocked(self) -> None:
        leaked = f47_rec_phrase_leak_when_blocked(
            _trace(
                recommendation_worthy=False,
                recommendation_authorized=True,
                allowed=False,
                insight="You should sleep more.",
            )
        )
        self.assertEqual(leaked.outcome, OUTCOME_FAIL)
        allowed = f47_rec_phrase_leak_when_blocked(
            _trace(
                status="RECOMMENDATION",
                recommendation_worthy=True,
                recommendation_authorized=True,
                allowed=True,
                recommendation="You should move caffeine earlier.",
            )
        )
        self.assertEqual(allowed.outcome, OUTCOME_NOT_APPLICABLE)

    def test_f48_control_cannot_be_primary(self) -> None:
        bad = f48_t6_control_not_primary(
            _trace(
                primary_metrics=["respiratory_rate"],
                control_metrics=["respiratory_rate"],
                trends=[
                    _trend(
                        "respiratory_rate",
                        control=True,
                        insight_candidate=True,
                        recommendation_candidate=True,
                    )
                ],
                recommendation_worthy=True,
            )
        )
        self.assertEqual(bad.outcome, OUTCOME_FAIL)
        good = f48_t6_control_not_primary(
            _trace(
                primary_metrics=["sleep_duration_hours"],
                control_metrics=["respiratory_rate"],
                recommendation_worthy=True,
                trends=[
                    _trend("sleep_duration_hours", insight_candidate=True, recommendation_candidate=True),
                    _trend("respiratory_rate", control=True, insight_candidate=False),
                ],
            )
        )
        self.assertEqual(good.outcome, OUTCOME_PASS)

    def test_f49_spread_not_promoted(self) -> None:
        spread = {
            "spread_ratio": 2.61,
            "spread_observation_allowed": True,
            "spread_comparison_allowed": True,
        }
        bad = f49_t12_spread_distinct_from_level(
            _trace(
                primary_metrics=["hrv_sdnn_ms"],
                trends=[
                    _trend(
                        "hrv_sdnn_ms",
                        direction="improving",
                        insight_candidate=False,
                        spread=spread,
                    )
                ],
            )
        )
        self.assertEqual(bad.outcome, OUTCOME_FAIL)
        good = f49_t12_spread_distinct_from_level(
            _trace(
                primary_metrics=["sleep_duration_hours"],
                trends=[
                    _trend("sleep_duration_hours", direction="decreasing", insight_candidate=True),
                    _trend("hrv_sdnn_ms", direction="improving", insight_candidate=False, spread=spread),
                ],
                facts=[
                    {
                        "metric": "hrv_sdnn_ms",
                        "role": "spread_context",
                        "direction": "improving",
                        "origin": "deterministic_spread_analytics",
                        "source": "get_trend_signals",
                    }
                ],
            )
        )
        self.assertEqual(good.outcome, OUTCOME_PASS)

    def test_f51_shape_and_facts(self) -> None:
        missing_primary = f51_output_contract_shape(_trace(status="INSIGHT", primary=None))
        self.assertEqual(missing_primary.outcome, OUTCOME_FAIL)
        quiet_quote = f51a_quote_null_on_quiet_path(
            _trace(status="NO_SIGNIFICANT_NEW_PATTERN", primary=None, quote="Keep going.")
        )
        self.assertEqual(quiet_quote.outcome, OUTCOME_FAIL)
        quiet_ok = f51_output_contract_shape(
            _trace(status="NO_SIGNIFICANT_NEW_PATTERN", primary=None, quote=None)
        )
        self.assertEqual(quiet_ok.outcome, OUTCOME_PASS)
        bad_origin = f51_facts_are_system_stamped(_trace(facts_origin="model_invented"))
        self.assertEqual(bad_origin.outcome, OUTCOME_FAIL)
        good_facts = f51_facts_are_system_stamped(
            _trace(
                facts=[
                    {
                        "metric": "sleep_duration_hours",
                        "role": "primary",
                        "origin": "deterministic_analytics",
                        "source": "get_trend_signals",
                    }
                ]
            )
        )
        self.assertEqual(good_facts.outcome, OUTCOME_PASS)


class RegressionControlTests(unittest.TestCase):
    def test_b1_protected(self) -> None:
        good = scenario_b1_quiet_path(
            _trace(
                "HC-EVAL-B1",
                status="NO_SIGNIFICANT_NEW_PATTERN",
                insight_worthy=False,
                primary=None,
                quote=None,
                recommendation=None,
            )
        )
        self.assertEqual(good.outcome, OUTCOME_PASS)
        bad = scenario_b1_quiet_path(_trace("HC-EVAL-B1", status="INSIGHT", insight_worthy=False))
        self.assertEqual(bad.outcome, OUTCOME_FAIL)
        skipped = scenario_b1_quiet_path(_trace("HC-EVAL-A1"))
        self.assertEqual(skipped.outcome, OUTCOME_NOT_APPLICABLE)

    def test_b3_protected(self) -> None:
        good = scenario_b3_maintenance_without_rec(
            _trace(
                "HC-EVAL-B3",
                status="INSIGHT",
                insight_worthy=True,
                recommendation_worthy=False,
                recommendation_authorized=True,
                allowed=False,
                recommendation=None,
                trends=[_trend("resting_hr_bpm", maintenance_of_gain=True, insight_candidate=True)],
            )
        )
        self.assertEqual(good.outcome, OUTCOME_PASS)
        rec = scenario_b3_maintenance_without_rec(
            _trace(
                "HC-EVAL-B3",
                status="RECOMMENDATION",
                insight_worthy=True,
                recommendation_worthy=False,
                recommendation_authorized=True,
                allowed=False,
                recommendation="Maintain your aerobic habit.",
                trends=[_trend("resting_hr_bpm", maintenance_of_gain=True, insight_candidate=True)],
            )
        )
        self.assertEqual(rec.outcome, OUTCOME_FAIL)

    def test_e1_and_c4_and_a_family(self) -> None:
        e1 = scenario_e1_rr_control(
            _trace(
                "HC-EVAL-E1",
                primary_metrics=["sleep_duration_hours"],
                control_metrics=["respiratory_rate"],
                trends=[
                    _trend("sleep_duration_hours", insight_candidate=True),
                    _trend("respiratory_rate", control=True),
                ],
            )
        )
        self.assertEqual(e1.outcome, OUTCOME_PASS)
        c4 = scenario_c4_spread_distinct(
            _trace(
                "HC-EVAL-C4",
                primary_metrics=["sleep_duration_hours"],
                trends=[
                    _trend(
                        "hrv_sdnn_ms",
                        direction="improving",
                        insight_candidate=False,
                        spread={"spread_ratio": 2.61, "spread_comparison_allowed": True},
                    )
                ],
                facts=[
                    {
                        "metric": "hrv_sdnn_ms",
                        "role": "spread_context",
                        "direction": "improving",
                        "origin": "deterministic_spread_analytics",
                        "source": "get_trend_signals",
                    }
                ],
            )
        )
        self.assertEqual(c4.outcome, OUTCOME_PASS)
        a1 = scenario_a_family_mature_data(_trace("HC-EVAL-A1"))
        self.assertEqual(a1.outcome, OUTCOME_PASS)

    def test_c2_has_no_single_cause_deterministic_rule(self) -> None:
        ids = [fn.__name__ for fn in DETERMINISTIC_GRADERS]
        self.assertNotIn("scenario_c2_single_cause", ids)
        self.assertTrue(any(spec.grader_id == "sem_c2_confounders_not_collapsed" for spec in SEMANTIC_SPECS))


class RunnerAndFrozenLabelTests(unittest.TestCase):
    def test_grade_trace_attaches_frozen_label_without_using_it_as_outcome(self) -> None:
        grade = grade_trace(
            _trace(
                "HC-EVAL-B1",
                status="NO_SIGNIFICANT_NEW_PATTERN",
                insight_worthy=False,
                primary=None,
                quote=None,
            )
        )
        b1 = next(item for item in grade.results if item.grader_id == "scenario_b1_quiet_path")
        self.assertEqual(b1.outcome, OUTCOME_PASS)
        if b1.frozen_human_pass_fail:
            self.assertEqual(b1.frozen_human_pass_fail, "FAIL")

    def test_frozen_extract_still_five_pass_ten_fail(self) -> None:
        self.assertTrue(EXTRACT_PATH.exists())
        records = parse_human_review_extract()
        labels = [record.normalized_pass_fail for record in records]
        self.assertEqual(labels.count("PASS"), 5)
        self.assertEqual(labels.count("FAIL"), 10)

    def test_coverage_matrix_separates_judgment(self) -> None:
        rows = coverage_matrix()
        types = {row["grader_type"] for row in rows}
        self.assertIn("DETERMINISTIC", types)
        self.assertIn("LLM_AS_JUDGE", types)
        self.assertIn("HUMAN_REVIEW", types)
        t8 = next(row for row in rows if row["grader_id"] == "sem_t8_no_level_c")
        self.assertEqual(t8["current_coverage"], "spec_only")
        quote = next(row for row in rows if row["grader_id"] == "sem_quote_not_hidden_advice")
        self.assertIn("C4", quote["notes"])

    def test_write_coverage_artifacts(self) -> None:
        json_path = RESULTS_DIR / "f60_codify_coverage_v1.json"
        csv_path = RESULTS_DIR / "f60_codify_coverage_v1.csv"
        write_coverage_artifacts(json_path=json_path, csv_path=csv_path)
        self.assertTrue(json_path.exists())
        self.assertTrue(csv_path.exists())
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(payload["graders"]), 20)


class F52SmokeTests(unittest.TestCase):
    def test_f52_traces_have_no_deterministic_fails(self) -> None:
        if not F52_TRACE_DIR.exists():
            self.skipTest("F5.2 traces not present")
        grades = grade_trace_directory(F52_TRACE_DIR)
        if not grades:
            self.skipTest("F5.2 traces not present")
        summary = summarize_grades(grades)
        self.assertEqual(summary["scenario_count"], 6)
        self.assertEqual(summary["deterministic_fail"], 0, summary["failed_grader_ids"])
        scenario_ids = {grade.scenario_id for grade in grades}
        self.assertEqual(
            scenario_ids,
            {"HC-EVAL-A1", "HC-EVAL-B1", "HC-EVAL-B3", "HC-EVAL-C2", "HC-EVAL-E1", "HC-EVAL-C4"},
        )


if __name__ == "__main__":
    unittest.main()
