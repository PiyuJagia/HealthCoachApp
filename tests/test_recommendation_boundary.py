"""Offline tests for F4.7 recommendation worthiness × authorization boundary."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from agent.instructions import HEALTH_COACH_INSTRUCTIONS
from agent.model_observe import extract_recommendation_boundary, observe_llm_request
from agent.runner import _apply_output_guard, _apply_recommendation_boundary
from agent.schemas import HealthCoachResult, HealthCoachStatus
from agent.tools import RunContext, build_tools
from app.health_tools import get_health_trends_for_agent
from app.lifestyle_tools import get_lifestyle_context_for_agent
from app.output_guard import check_final_output
from app.recommendation_boundary import (
    apply_recommendation_boundary,
    compute_final_recommendation_allowed,
)
from data.demo_seed import seed_demo_health_data
from evals.trace_schema import (
    ORIGIN_EVIDENCE_POLICY,
    ORIGIN_RECOMMENDATION_BOUNDARY,
    ORIGIN_SALIENCE_ANALYTICS,
    empty_trace,
)
from google.genai import types
from rag.evidence_policy import AuthorizationVerdict, EvidencePolicyDecision, evaluate_retrieved_evidence
from rag.schemas import RetrievalResult
from tests.test_evidence_policy import _make_result
from tests.test_helpers import open_test_session
from tests.test_lifestyle_context import _r07_result
from tests.test_model_observe import _sample_request

B1 = date(2026, 6, 18)
A1 = date(2026, 8, 2)
B3 = date(2026, 8, 17)


def _authorized_decision(authorized: bool = True) -> EvidencePolicyDecision:
    return EvidencePolicyDecision(
        overall_verdict=AuthorizationVerdict.SURFACE,
        evidence_authorized=True,
        recommendation_authorized=authorized,
        reasons=("authorized_evidence_present",),
        relationship_decisions=(),
        general_evidence=(),
        authorized_results=(),
        suppressed_relationship_ids=(),
    )


class CombinedGateTests(unittest.TestCase):
    def test_worthy_false_authorized_true_blocks(self) -> None:
        self.assertFalse(
            compute_final_recommendation_allowed(
                recommendation_worthy=False,
                recommendation_authorized=True,
            )
        )

    def test_worthy_true_authorized_false_blocks(self) -> None:
        self.assertFalse(
            compute_final_recommendation_allowed(
                recommendation_worthy=True,
                recommendation_authorized=False,
            )
        )

    def test_both_true_allows(self) -> None:
        self.assertTrue(
            compute_final_recommendation_allowed(
                recommendation_worthy=True,
                recommendation_authorized=True,
            )
        )

    def test_both_false_blocks(self) -> None:
        self.assertFalse(
            compute_final_recommendation_allowed(
                recommendation_worthy=False,
                recommendation_authorized=False,
            )
        )


class StructuredBoundaryTests(unittest.TestCase):
    def test_recommendation_field_cleared_when_gate_false(self) -> None:
        updated, decision = apply_recommendation_boundary(
            {
                "status": "INSIGHT",
                "insight": "Your cardiovascular gains appear to be holding.",
                "recommendation": "Maintain your regular aerobic exercise habit.",
            },
            insight_worthy=True,
            recommendation_worthy=False,
            recommendation_authorized=True,
        )
        self.assertEqual(updated["status"], "INSIGHT")
        self.assertIsNone(updated["recommendation"])
        self.assertFalse(updated["final_recommendation_allowed"])
        self.assertTrue(updated["recommendation_authorized"])
        self.assertFalse(updated["recommendation_worthy"])
        self.assertFalse(decision.final_recommendation_allowed)
        self.assertIn("recommendation_field_without_final_allowance", decision.violations)
        self.assertTrue(decision.final_output_respects_boundary)

    def test_recommendation_status_cannot_pass_when_gate_false(self) -> None:
        updated, decision = apply_recommendation_boundary(
            {
                "status": "RECOMMENDATION",
                "insight": "Sleep declined 18%.",
                "recommendation": "Shift caffeine earlier.",
            },
            insight_worthy=True,
            recommendation_worthy=True,
            recommendation_authorized=False,
        )
        self.assertEqual(updated["status"], "INSIGHT")
        self.assertIsNone(updated["recommendation"])
        self.assertFalse(updated["final_recommendation_allowed"])
        self.assertIn("recommendation_status_without_final_allowance", decision.violations)

    def test_both_true_preserves_recommendation(self) -> None:
        updated, decision = apply_recommendation_boundary(
            {
                "status": "RECOMMENDATION",
                "insight": "Sleep declined 18%.",
                "recommendation": "Shift caffeine earlier.",
            },
            insight_worthy=True,
            recommendation_worthy=True,
            recommendation_authorized=True,
        )
        self.assertEqual(updated["status"], "RECOMMENDATION")
        self.assertEqual(updated["recommendation"], "Shift caffeine earlier.")
        self.assertTrue(updated["final_recommendation_allowed"])
        self.assertTrue(decision.model_respected_boundary)

    def test_both_false_blocks_and_does_not_invent_insight(self) -> None:
        updated, _decision = apply_recommendation_boundary(
            {
                "status": "RECOMMENDATION",
                "insight": None,
                "recommendation": "Celebrate your steps.",
            },
            insight_worthy=False,
            recommendation_worthy=False,
            recommendation_authorized=False,
        )
        self.assertEqual(updated["status"], "NO_SIGNIFICANT_NEW_PATTERN")
        self.assertIsNone(updated["recommendation"])


class GuardBoundaryTests(unittest.TestCase):
    def test_guard_rejects_recommendation_status_when_gate_false(self) -> None:
        result = check_final_output(
            "Sleep declined.",
            decision=_authorized_decision(True),
            recommendation_worthy=False,
            structured={"status": "RECOMMENDATION", "recommendation": None},
        )
        self.assertFalse(result.passed)
        self.assertIn("recommendation_status_without_final_allowance", result.violations)

    def test_guard_rejects_recommendation_field_when_gate_false(self) -> None:
        result = check_final_output(
            "Gains are holding.",
            decision=_authorized_decision(True),
            recommendation_worthy=False,
            structured={
                "status": "INSIGHT",
                "recommendation": "Maintain your regular aerobic exercise habit.",
            },
        )
        self.assertFalse(result.passed)
        self.assertIn("recommendation_field_without_final_allowance", result.violations)

    def test_guard_allows_recommendation_when_both_true(self) -> None:
        result = check_final_output(
            "I recommend shifting caffeine earlier.",
            decision=_authorized_decision(True),
            recommendation_worthy=True,
            structured={
                "status": "RECOMMENDATION",
                "primary_message": "Sleep duration declined.",
                "recommendation": "I recommend shifting caffeine earlier.",
            },
        )
        self.assertTrue(result.passed)


class ScenarioContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session, reset=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()

    def _salience(self, as_of: date) -> dict:
        return get_health_trends_for_agent(self.user.id, as_of_date=as_of)["insight_salience"]

    def test_b3_insight_capable_while_rec_blocked(self) -> None:
        salience = self._salience(B3)
        r05 = evaluate_retrieved_evidence(
            [
                _make_result(
                    relationship_id="R-05",
                    max_product_level="4",
                    recommendation_eligible="true",
                    measurement_transfer_risk="low",
                )
            ]
        )
        self.assertTrue(salience["insight_worthy"])
        self.assertFalse(salience["recommendation_worthy"])
        self.assertTrue(r05.recommendation_authorized)
        allowed = compute_final_recommendation_allowed(
            recommendation_worthy=salience["recommendation_worthy"],
            recommendation_authorized=r05.recommendation_authorized,
        )
        self.assertFalse(allowed)
        updated, _decision = apply_recommendation_boundary(
            {
                "status": "INSIGHT",
                "insight": "Your cardiovascular gains appear to be holding.",
                "recommendation": "Maintain your regular aerobic exercise habit.",
            },
            insight_worthy=salience["insight_worthy"],
            recommendation_worthy=salience["recommendation_worthy"],
            recommendation_authorized=r05.recommendation_authorized,
        )
        self.assertEqual(updated["status"], "INSIGHT")
        self.assertIsNone(updated["recommendation"])
        self.assertIn("holding", updated["insight"])

    def test_a1_allowed_if_both_gates_true(self) -> None:
        salience = self._salience(A1)
        lifestyle = get_lifestyle_context_for_agent(self.user.id, as_of_date=A1)
        r07 = evaluate_retrieved_evidence(
            [_r07_result()],
            available_inputs=set(lifestyle["policy_available_inputs"]),
        )
        self.assertTrue(salience["insight_worthy"])
        self.assertTrue(salience["recommendation_worthy"])
        self.assertTrue(r07.recommendation_authorized)
        self.assertTrue(
            compute_final_recommendation_allowed(
                recommendation_worthy=salience["recommendation_worthy"],
                recommendation_authorized=r07.recommendation_authorized,
            )
        )

    def test_b1_stays_non_salient(self) -> None:
        payload = get_health_trends_for_agent(self.user.id, as_of_date=B1)
        salience = payload["insight_salience"]
        self.assertFalse(salience["insight_worthy"])
        self.assertFalse(salience["recommendation_worthy"])
        by_metric = {item["metric"]: item for item in payload["trends"]}
        self.assertEqual(by_metric["steps"]["direction"], "improving")
        updated, _decision = apply_recommendation_boundary(
            {
                "status": "RECOMMENDATION",
                "insight": "Great job — your activity is improving!",
                "recommendation": "Keep walking more.",
            },
            insight_worthy=False,
            recommendation_worthy=False,
            recommendation_authorized=True,
        )
        self.assertEqual(updated["status"], "NO_SIGNIFICANT_NEW_PATTERN")
        self.assertIsNone(updated["recommendation"])

    def test_f46_salience_behavior_unchanged(self) -> None:
        self.assertFalse(self._salience(B1)["insight_worthy"])
        self.assertTrue(self._salience(A1)["insight_worthy"])
        self.assertTrue(self._salience(B3)["insight_worthy"])
        self.assertFalse(self._salience(B3)["recommendation_worthy"])

    def test_f41_maturity_behavior_unchanged(self) -> None:
        payload = get_health_trends_for_agent(self.user.id, as_of_date=B3)
        rhr = next(item for item in payload["trends"] if item["metric"] == "resting_hr_bpm")
        self.assertEqual(rhr["data_maturity_state"], "ESTABLISHED_TREND")
        self.assertTrue(rhr["claim_eligibility"]["trend_allowed"])
        self.assertEqual(rhr["direction"], "stable")

    def test_evidence_policy_semantics_unchanged(self) -> None:
        r05 = evaluate_retrieved_evidence(
            [
                _make_result(
                    relationship_id="R-05",
                    max_product_level="4",
                    recommendation_eligible="true",
                    measurement_transfer_risk="low",
                )
            ]
        )
        self.assertTrue(r05.recommendation_authorized)
        r07_no_inputs = evaluate_retrieved_evidence([_r07_result()], available_inputs=None)
        self.assertFalse(r07_no_inputs.recommendation_authorized)


class RunnerAndTraceTests(unittest.TestCase):
    def test_runner_stamps_boundary_and_clears_rec_field(self) -> None:
        context = RunContext(scenario_id="HC-EVAL-B3", user_id=1, as_of_date=B3)
        context.candidate_signals = {
            "insight_salience": {
                "insight_worthy": True,
                "recommendation_worthy": False,
            }
        }
        context.last_policy_decision = _authorized_decision(True)
        structured = HealthCoachResult(
            scenario_id="HC-EVAL-B3",
            user_id=1,
            as_of_date="2026-08-17",
            status="INSIGHT",
            primary_message="Resting heart rate, HRV, and VO2 remain improved versus the earlier baseline.",
            insight="Your cardiovascular gains appear to be holding.",
            recommendation="Maintain your regular aerobic exercise habit.",
            recommendation_authorized=True,
        ).to_dict()
        updated = _apply_recommendation_boundary(context=context, structured=structured)
        self.assertIsNone(updated["recommendation"])
        self.assertEqual(updated["status"], "INSIGHT")
        self.assertFalse(updated["final_recommendation_allowed"])
        self.assertIsNotNone(context.recommendation_boundary)
        assert context.recommendation_boundary is not None
        self.assertFalse(context.recommendation_boundary.final_recommendation_allowed)
        self.assertEqual(context.recommendation_boundary.recommendation_worthy_origin, ORIGIN_SALIENCE_ANALYTICS)
        self.assertEqual(context.recommendation_boundary.recommendation_authorized_origin, ORIGIN_EVIDENCE_POLICY)
        self.assertEqual(
            context.recommendation_boundary.final_recommendation_allowed_origin,
            ORIGIN_RECOMMENDATION_BOUNDARY,
        )
        guarded = _apply_output_guard(
            context=context,
            structured=updated,
            scenario_id="HC-EVAL-B3",
            user_id=1,
            as_of_date="2026-08-17",
        )
        self.assertEqual(guarded["status"], "INSIGHT")
        self.assertTrue(context.final_guard.passed)

    def test_guard_blocks_recommendation_status_after_boundary_if_still_present(self) -> None:
        context = RunContext(scenario_id="HC-EVAL-B3", user_id=1, as_of_date=B3)
        context.candidate_signals = {"insight_salience": {"insight_worthy": True, "recommendation_worthy": False}}
        context.last_policy_decision = _authorized_decision(True)
        blocked = _apply_output_guard(
            context=context,
            structured={
                "status": "RECOMMENDATION",
                "insight": "Gains are holding.",
                "recommendation": "Keep exercising.",
            },
            scenario_id="HC-EVAL-B3",
            user_id=1,
            as_of_date="2026-08-17",
        )
        self.assertEqual(blocked["status"], HealthCoachStatus.GUARD_BLOCKED.value)

    def test_evidence_tool_exposes_all_three_fields(self) -> None:
        context = RunContext(scenario_id="HC-EVAL-B3", user_id=1, as_of_date=B3)
        context.candidate_signals = {
            "insight_salience": {"insight_worthy": True, "recommendation_worthy": False}
        }
        _, _, retrieve = build_tools(context)
        with patch("agent.tools.agent_tools.retrieve_evidence") as mock_retrieve:
            with patch("agent.tools.agent_tools.evaluate_evidence_policy") as mock_policy:
                mock_retrieve.return_value = []
                mock_policy.return_value = _authorized_decision(True)
                result = retrieve("cardiovascular fitness maintenance")
        self.assertFalse(result["recommendation_worthy"])
        self.assertTrue(result["recommendation_authorized"])
        self.assertFalse(result["final_recommendation_allowed"])

    def test_trace_exposes_three_fields_and_provenance(self) -> None:
        request = _sample_request()
        request.contents[-1] = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name="retrieve_authorized_evidence",
                        response={
                            "query": "maintenance",
                            "retrieval_count": 1,
                            "authorized_count": 1,
                            "overall_verdict": "SURFACE",
                            "evidence_authorized": True,
                            "recommendation_authorized": True,
                            "recommendation_worthy": False,
                            "final_recommendation_allowed": False,
                            "policy": {"reasons": ["authorized_evidence_present"]},
                            "retrieval": [{"relationship_id": "R-05"}],
                        },
                    )
                )
            ],
        )
        captured = observe_llm_request(request, call_index=0)
        visible = captured.recommendation_boundary_visible
        assert visible is not None
        self.assertFalse(visible["recommendation_worthy"])
        self.assertTrue(visible["recommendation_authorized"])
        self.assertFalse(visible["final_recommendation_allowed"])
        self.assertEqual(visible["recommendation_worthy_origin"], ORIGIN_SALIENCE_ANALYTICS)
        self.assertEqual(visible["recommendation_authorized_origin"], ORIGIN_EVIDENCE_POLICY)
        self.assertEqual(visible["final_recommendation_allowed_origin"], ORIGIN_RECOMMENDATION_BOUNDARY)
        component = next(item for item in captured.provenance if item.component == "recommendation_boundary")
        self.assertEqual(component.origin, ORIGIN_RECOMMENDATION_BOUNDARY)
        extracted = extract_recommendation_boundary(
            {"recommendation_authorized": True, "recommendation_worthy": False, "final_recommendation_allowed": False}
        )
        assert extracted is not None
        self.assertFalse(extracted["final_recommendation_allowed"])
        trace = empty_trace(scenario_id="HC-EVAL-B3", user_id=1, as_of_date="2026-08-17")
        self.assertIsNone(trace.to_dict()["recommendation_boundary"])

    def test_prompt_requires_combined_gate(self) -> None:
        self.assertIn("final_recommendation_allowed=true", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("Either flag alone is not enough", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("do not hide advice inside", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("motivational_quote", HEALTH_COACH_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
