"""Offline tests for retrieval→policy authorization adapter."""

from __future__ import annotations

import unittest

from rag.evidence_policy import AuthorizationVerdict, evaluate_retrieved_evidence
from rag.schemas import RetrievalResult


def _make_result(
    *,
    vector_id: str = "doc__chunk_0001",
    score: float = 0.8,
    document_id: str = "healthcoach_correlation_modeling",
    relationship_id: str = "",
    measurement_transfer_risk: str = "",
    max_product_level: str = "",
    recommendation_eligible: str = "",
    modifier_suppressor_only: str = "",
    mandatory_contradiction_suppression: str = "",
    evidence_strength: str = "moderate",
) -> RetrievalResult:
    return RetrievalResult(
        vector_id=vector_id,
        score=score,
        text="Sample retrieved evidence text.",
        document_id=document_id,
        source_title="Sample Source",
        section_heading="Sample section",
        chunk_index=1,
        version="L2-CR-002",
        evidence_level="curated_evidence_synthesis",
        evidence_grade="verified_with_constraints",
        verification_status="verified_with_constraints",
        relationship_id=relationship_id,
        relationship_status="active",
        evidence_strength=evidence_strength,
        measurement_transfer_risk=measurement_transfer_risk,
        max_product_level=max_product_level,
        recommendation_eligible=recommendation_eligible,
        modifier_suppressor_only=modifier_suppressor_only,
        mandatory_contradiction_suppression=mandatory_contradiction_suppression,
    )


class EvidencePolicyAdapterTests(unittest.TestCase):
    def test_empty_retrieval_suppresses(self) -> None:
        decision = evaluate_retrieved_evidence([])
        self.assertEqual(decision.overall_verdict, AuthorizationVerdict.SUPPRESS)
        self.assertFalse(decision.evidence_authorized)
        self.assertFalse(decision.recommendation_authorized)
        self.assertIn("no_retrieval_results", decision.reasons)
        self.assertEqual(decision.authorized_results, ())

    def test_ordinary_hhs_evidence_usable_without_recommendation_authority(self) -> None:
        decision = evaluate_retrieved_evidence(
            [_make_result(document_id="hhs_physical_activity_guidelines_2e")]
        )
        self.assertTrue(decision.evidence_authorized)
        self.assertFalse(decision.recommendation_authorized)
        self.assertEqual(decision.overall_verdict, AuthorizationVerdict.SURFACE)
        general = decision.general_evidence[0]
        self.assertTrue(general.evidence_authorized)
        self.assertFalse(general.recommendation_authorized)

    def test_r05_recommendation_eligible_surface(self) -> None:
        decision = evaluate_retrieved_evidence(
            [
                _make_result(
                    relationship_id="R-05",
                    max_product_level="4",
                    recommendation_eligible="true",
                    measurement_transfer_risk="low",
                )
            ]
        )
        rel = decision.relationship_decisions[0]
        self.assertEqual(rel.verdict, AuthorizationVerdict.SURFACE)
        self.assertTrue(rel.evidence_authorized)
        self.assertTrue(rel.recommendation_authorized)
        self.assertTrue(decision.recommendation_authorized)

    def test_r02_high_transfer_not_recommendation_eligible(self) -> None:
        decision = evaluate_retrieved_evidence(
            [
                _make_result(
                    relationship_id="R-02",
                    max_product_level="2",
                    recommendation_eligible="false",
                    measurement_transfer_risk="high",
                )
            ]
        )
        rel = decision.relationship_decisions[0]
        self.assertFalse(rel.recommendation_authorized)
        self.assertTrue(rel.evidence_authorized)
        self.assertEqual(rel.measurement_transfer_risk, "high")

    def test_r03_suppressed_only_when_contradiction_explicitly_indicated(self) -> None:
        without_flag = evaluate_retrieved_evidence(
            [
                _make_result(
                    vector_id="r03",
                    relationship_id="R-03",
                    max_product_level="3",
                    mandatory_contradiction_suppression="true",
                ),
                _make_result(
                    vector_id="r05",
                    relationship_id="R-05",
                    max_product_level="4",
                    recommendation_eligible="true",
                ),
            ]
        )
        r03 = next(item for item in without_flag.relationship_decisions if item.relationship_id == "R-03")
        self.assertNotEqual(r03.evaluation_outcome, "suppressed_contradiction")
        self.assertIn(without_flag.overall_verdict, {AuthorizationVerdict.QUALIFY, AuthorizationVerdict.SURFACE})

        with_flag = evaluate_retrieved_evidence(
            [
                _make_result(
                    vector_id="r03",
                    relationship_id="R-03",
                    max_product_level="3",
                    mandatory_contradiction_suppression="true",
                ),
                _make_result(
                    vector_id="r05",
                    relationship_id="R-05",
                    max_product_level="4",
                    recommendation_eligible="true",
                ),
            ],
            contradictory_candidates=True,
        )
        r03_flagged = next(item for item in with_flag.relationship_decisions if item.relationship_id == "R-03")
        self.assertEqual(r03_flagged.verdict, AuthorizationVerdict.SUPPRESS)
        self.assertEqual(r03_flagged.evaluation_outcome, "suppressed_contradiction")

    def test_r06_recommendation_prohibited(self) -> None:
        decision = evaluate_retrieved_evidence(
            [
                _make_result(
                    relationship_id="R-06",
                    max_product_level="3",
                    measurement_transfer_risk="high",
                )
            ]
        )
        rel = decision.relationship_decisions[0]
        self.assertFalse(rel.recommendation_authorized)
        self.assertTrue(rel.evidence_authorized)

    def test_r08_alcohol_advice_prohibited(self) -> None:
        decision = evaluate_retrieved_evidence(
            [
                _make_result(
                    relationship_id="R-08",
                    max_product_level="2",
                    measurement_transfer_risk="moderate",
                )
            ],
            available_inputs={"alcohol_units"},
        )
        rel = decision.relationship_decisions[0]
        self.assertFalse(rel.recommendation_authorized)

    def test_r09_modifier_only_suppressed(self) -> None:
        decision = evaluate_retrieved_evidence(
            [
                _make_result(
                    relationship_id="R-09",
                    modifier_suppressor_only="true",
                    max_product_level="2",
                )
            ],
            available_inputs={"cycle_phase"},
        )
        rel = decision.relationship_decisions[0]
        self.assertEqual(rel.verdict, AuthorizationVerdict.SUPPRESS)
        self.assertFalse(rel.evidence_authorized)

    def test_compatible_r05_and_r06_not_auto_suppressed(self) -> None:
        decision = evaluate_retrieved_evidence(
            [
                _make_result(
                    vector_id="r05",
                    relationship_id="R-05",
                    max_product_level="4",
                    recommendation_eligible="true",
                    measurement_transfer_risk="low",
                ),
                _make_result(
                    vector_id="r06",
                    relationship_id="R-06",
                    max_product_level="3",
                    measurement_transfer_risk="high",
                ),
            ]
        )
        self.assertNotEqual(decision.overall_verdict, AuthorizationVerdict.SUPPRESS)
        self.assertIn("multiple_relationship_candidates_ambiguous", decision.reasons)
        r05 = next(item for item in decision.relationship_decisions if item.relationship_id == "R-05")
        r06 = next(item for item in decision.relationship_decisions if item.relationship_id == "R-06")
        self.assertTrue(r05.evidence_authorized)
        self.assertTrue(r06.evidence_authorized)

    def test_compatible_r01_and_r02_not_auto_suppressed(self) -> None:
        decision = evaluate_retrieved_evidence(
            [
                _make_result(vector_id="r01", relationship_id="R-01", max_product_level="2"),
                _make_result(
                    vector_id="r02",
                    relationship_id="R-02",
                    max_product_level="2",
                    measurement_transfer_risk="high",
                ),
            ]
        )
        self.assertNotEqual(decision.overall_verdict, AuthorizationVerdict.SUPPRESS)
        self.assertEqual(len(decision.relationship_decisions), 2)
        self.assertTrue(all(item.evidence_authorized for item in decision.relationship_decisions))

    def test_mixed_general_and_relationship_preserves_action_limits(self) -> None:
        decision = evaluate_retrieved_evidence(
            [
                _make_result(document_id="hhs_physical_activity_guidelines_2e"),
                _make_result(
                    relationship_id="R-02",
                    max_product_level="2",
                    measurement_transfer_risk="high",
                ),
            ]
        )
        self.assertTrue(decision.evidence_authorized)
        self.assertFalse(decision.recommendation_authorized)
        self.assertTrue(decision.general_evidence[0].evidence_authorized)
        self.assertFalse(decision.general_evidence[0].recommendation_authorized)

    def test_missing_metadata_unregistered_relationship_suppressed(self) -> None:
        decision = evaluate_retrieved_evidence(
            [_make_result(relationship_id="R-99", max_product_level="4")]
        )
        rel = decision.relationship_decisions[0]
        self.assertEqual(rel.verdict, AuthorizationVerdict.SUPPRESS)
        self.assertFalse(rel.evidence_authorized)


if __name__ == "__main__":
    unittest.main()
