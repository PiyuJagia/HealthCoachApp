"""Deterministic tests for L2-CR relationship evaluation policy."""

from __future__ import annotations

import unittest

from rag.relationship_policy import (
    EvaluationOutcome,
    can_generate_recommendation,
    evaluate_relationship_request,
    is_registered_relationship,
    load_relationship_policies,
    should_suppress_contradictory_interpretation,
)


class RelationshipPolicyTests(unittest.TestCase):
    def test_all_nine_active_relationships_are_registered(self) -> None:
        policies = load_relationship_policies()
        self.assertEqual(set(policies.keys()), {f"R-{index:02d}" for index in range(1, 10)})

    def test_unregistered_relationship_cannot_be_evaluated(self) -> None:
        self.assertFalse(is_registered_relationship("R-99"))
        outcome = evaluate_relationship_request("R-99")
        self.assertEqual(outcome, EvaluationOutcome.NOT_REGISTERED)

    def test_contradictory_candidates_cause_suppression_for_r03(self) -> None:
        self.assertTrue(
            should_suppress_contradictory_interpretation(
                "R-03",
                contradictory_candidates=True,
            )
        )
        outcome = evaluate_relationship_request(
            "R-03",
            contradictory_candidates=True,
        )
        self.assertEqual(outcome, EvaluationOutcome.SUPPRESSED_CONTRADICTION)

    def test_below_level_four_cannot_generate_recommendation(self) -> None:
        for relationship_id in ("R-01", "R-02", "R-03", "R-04", "R-06", "R-08", "R-09"):
            self.assertFalse(
                can_generate_recommendation(relationship_id),
                msg=f"{relationship_id} should not generate recommendations",
            )

    def test_high_transfer_risk_relationships_cannot_generate_recommendations(self) -> None:
        self.assertFalse(can_generate_recommendation("R-02"))
        self.assertFalse(can_generate_recommendation("R-06"))

    def test_only_r05_and_r07_are_level_four_recommendation_eligible(self) -> None:
        self.assertTrue(can_generate_recommendation("R-05"))
        self.assertTrue(can_generate_recommendation("R-07"))

    def test_r09_cannot_be_surfaced_as_standalone_insight(self) -> None:
        outcome = evaluate_relationship_request(
            "R-09",
            available_inputs={"cycle_phase"},
        )
        self.assertEqual(outcome, EvaluationOutcome.MODIFIER_ONLY)

    def test_missing_caffeine_input_disables_r07(self) -> None:
        outcome = evaluate_relationship_request("R-07", available_inputs=set())
        self.assertEqual(outcome, EvaluationOutcome.INPUT_UNAVAILABLE)

    def test_missing_alcohol_input_disables_r08(self) -> None:
        outcome = evaluate_relationship_request("R-08", available_inputs=set())
        self.assertEqual(outcome, EvaluationOutcome.INPUT_UNAVAILABLE)

    def test_missing_cycle_input_disables_r09(self) -> None:
        outcome = evaluate_relationship_request("R-09", available_inputs=set())
        self.assertEqual(outcome, EvaluationOutcome.INPUT_UNAVAILABLE)

    def test_null_no_relationship_result_is_valid(self) -> None:
        outcome = evaluate_relationship_request(
            "R-01",
            meaningful_signal=False,
        )
        self.assertEqual(outcome, EvaluationOutcome.NO_RELATIONSHIP)

    def test_r08_cannot_generate_alcohol_advice_even_with_input(self) -> None:
        self.assertFalse(can_generate_recommendation("R-08"))

    def test_r06_cannot_generate_recommendations_despite_level_three_cap(self) -> None:
        policies = load_relationship_policies()
        self.assertEqual(policies["R-06"].max_product_level, 3)
        self.assertFalse(can_generate_recommendation("R-06"))


if __name__ == "__main__":
    unittest.main()
