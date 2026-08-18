"""Offline tests for deterministic final-output guard."""

from __future__ import annotations

import unittest

from app.output_guard import check_final_output
from rag.evidence_policy import (
    AuthorizationVerdict,
    EvidencePolicyDecision,
    RelationshipAuthorization,
    evaluate_retrieved_evidence,
)
from rag.schemas import RetrievalResult


def _decision_with_suppressed_r03() -> EvidencePolicyDecision:
    return evaluate_retrieved_evidence(
        [
            RetrievalResult(
                vector_id="r03",
                score=0.8,
                text="",
                document_id="healthcoach_correlation_modeling",
                source_title="",
                section_heading="",
                chunk_index=1,
                version="L2-CR-002",
                evidence_level="",
                evidence_grade="",
                verification_status="",
                relationship_id="R-03",
                relationship_status="active",
                evidence_strength="moderate",
                measurement_transfer_risk="moderate",
                max_product_level="3",
                recommendation_eligible="false",
                modifier_suppressor_only="false",
                mandatory_contradiction_suppression="true",
            ),
            RetrievalResult(
                vector_id="r05",
                score=0.7,
                text="",
                document_id="healthcoach_correlation_modeling",
                source_title="",
                section_heading="",
                chunk_index=2,
                version="L2-CR-002",
                evidence_level="",
                evidence_grade="",
                verification_status="",
                relationship_id="R-05",
                relationship_status="active",
                evidence_strength="strong",
                measurement_transfer_risk="low",
                max_product_level="4",
                recommendation_eligible="true",
                modifier_suppressor_only="false",
                mandatory_contradiction_suppression="false",
            ),
        ],
        contradictory_candidates=True,
    )


class OutputGuardTests(unittest.TestCase):
    def test_suppressed_relationship_in_output_fails(self) -> None:
        decision = _decision_with_suppressed_r03()
        result = check_final_output(
            "Observed pattern involving R-03 and sleep duration.",
            decision=decision,
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("suppressed_relationship_referenced" in v for v in result.violations))

    def test_unauthorized_recommendation_fails(self) -> None:
        decision = evaluate_retrieved_evidence(
            [
                RetrievalResult(
                    vector_id="r02",
                    score=0.8,
                    text="",
                    document_id="healthcoach_correlation_modeling",
                    source_title="",
                    section_heading="",
                    chunk_index=1,
                    version="L2-CR-002",
                    evidence_level="",
                    evidence_grade="",
                    verification_status="",
                    relationship_id="R-02",
                    relationship_status="active",
                    evidence_strength="moderate",
                    measurement_transfer_risk="high",
                    max_product_level="2",
                    recommendation_eligible="false",
                    modifier_suppressor_only="false",
                    mandatory_contradiction_suppression="false",
                )
            ]
        )
        result = check_final_output(
            "You should increase training intensity based on this association.",
            decision=decision,
        )
        self.assertFalse(result.passed)
        self.assertIn("unauthorized_recommendation_language", result.violations)

    def test_causal_wording_fails(self) -> None:
        decision = evaluate_retrieved_evidence([])
        result = check_final_output(
            "Exercise caused your resting heart rate to decrease.",
            decision=decision,
        )
        self.assertFalse(result.passed)
        self.assertIn("association_only_causal_wording", result.violations)

    def test_unsupported_analytical_method_claim_fails(self) -> None:
        decision = evaluate_retrieved_evidence([])
        result = check_final_output(
            "Changepoint analysis detected a meaningful shift in sleep duration.",
            decision=decision,
        )
        self.assertFalse(result.passed)
        self.assertTrue(any(v.startswith("unsupported_analytical_method_claim") for v in result.violations))

    def test_safe_qualified_output_passes(self) -> None:
        decision = EvidencePolicyDecision(
            overall_verdict=AuthorizationVerdict.QUALIFY,
            evidence_authorized=True,
            recommendation_authorized=False,
            reasons=("qualified_evidence_only",),
            relationship_decisions=(
                RelationshipAuthorization(
                    relationship_id="R-05",
                    vector_id="r05",
                    document_id="healthcoach_correlation_modeling",
                    chunk_index=1,
                    score=0.8,
                    verdict=AuthorizationVerdict.QUALIFY,
                    evaluation_outcome="relationship_detected",
                    evidence_authorized=True,
                    recommendation_authorized=False,
                    recommendation_eligible=False,
                    max_product_level=3,
                    measurement_transfer_risk="low",
                    evidence_strength="moderate",
                    modifier_suppressor_only=False,
                    mandatory_contradiction_suppression=False,
                    reasons=("interpretation_allowed_with_constraints",),
                ),
            ),
            general_evidence=(),
            authorized_results=(),
            suppressed_relationship_ids=(),
        )
        result = check_final_output(
            "Recent resting heart rate is lower than the prior baseline window.",
            decision=decision,
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.violations, ())


if __name__ == "__main__":
    unittest.main()
