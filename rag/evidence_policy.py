"""Deterministic authorization decisions for retrieved evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from rag.relationship_policy import (
    EvaluationOutcome,
    can_generate_recommendation,
    evaluate_relationship_request,
    is_registered_relationship,
    load_relationship_policies,
)
from rag.schemas import RetrievalResult


class AuthorizationVerdict(str, Enum):
    SURFACE = "SURFACE"
    QUALIFY = "QUALIFY"
    SUPPRESS = "SUPPRESS"


def _metadata_bool(value: str) -> bool:
    normalized = (value or "").strip().lower()
    return normalized in {"true", "1", "yes"}


def _metadata_int(value: str, default: int = 0) -> int:
    try:
        return int((value or "").strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class RelationshipAuthorization:
    relationship_id: str
    vector_id: str
    document_id: str
    chunk_index: int
    score: float
    verdict: AuthorizationVerdict
    evaluation_outcome: str
    evidence_authorized: bool
    recommendation_authorized: bool
    recommendation_eligible: bool
    max_product_level: int
    measurement_transfer_risk: str
    evidence_strength: str
    modifier_suppressor_only: bool
    mandatory_contradiction_suppression: bool
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["verdict"] = self.verdict.value
        return payload


@dataclass(frozen=True)
class GeneralEvidenceAuthorization:
    vector_id: str
    document_id: str
    chunk_index: int
    score: float
    source_title: str
    section_heading: str
    verdict: AuthorizationVerdict
    evidence_authorized: bool
    recommendation_authorized: bool
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["verdict"] = self.verdict.value
        return payload


@dataclass(frozen=True)
class EvidencePolicyDecision:
    overall_verdict: AuthorizationVerdict
    evidence_authorized: bool
    recommendation_authorized: bool
    reasons: tuple[str, ...]
    relationship_decisions: tuple[RelationshipAuthorization, ...]
    general_evidence: tuple[GeneralEvidenceAuthorization, ...]
    authorized_results: tuple[RetrievalResult, ...]
    suppressed_relationship_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_verdict": self.overall_verdict.value,
            "evidence_authorized": self.evidence_authorized,
            "recommendation_authorized": self.recommendation_authorized,
            "reasons": list(self.reasons),
            "relationship_decisions": [item.to_dict() for item in self.relationship_decisions],
            "general_evidence": [item.to_dict() for item in self.general_evidence],
            "authorized_results": [_retrieval_result_summary(result) for result in self.authorized_results],
            "suppressed_relationship_ids": list(self.suppressed_relationship_ids),
        }


def _retrieval_result_summary(result: RetrievalResult) -> dict[str, Any]:
    return {
        "vector_id": result.vector_id,
        "score": result.score,
        "document_id": result.document_id,
        "chunk_index": result.chunk_index,
        "relationship_id": result.relationship_id,
        "section_heading": result.section_heading,
    }


def _relationship_verdict_from_outcome(
    outcome: EvaluationOutcome,
    *,
    recommendation_eligible: bool,
    max_product_level: int,
    measurement_transfer_risk: str,
) -> tuple[AuthorizationVerdict, tuple[str, ...]]:
    if outcome == EvaluationOutcome.RELATIONSHIP_DETECTED:
        if recommendation_eligible:
            return AuthorizationVerdict.SURFACE, ("relationship_detected_recommendation_eligible",)
        if measurement_transfer_risk == "high":
            return AuthorizationVerdict.QUALIFY, ("high_measurement_transfer_risk",)
        if max_product_level >= 3:
            return AuthorizationVerdict.QUALIFY, ("interpretation_allowed_with_constraints",)
        return AuthorizationVerdict.QUALIFY, ("relationship_detected_non_recommendation",)

    if outcome == EvaluationOutcome.MODIFIER_ONLY:
        return AuthorizationVerdict.SUPPRESS, ("modifier_suppressor_only",)

    if outcome == EvaluationOutcome.SUPPRESSED_CONTRADICTION:
        return AuthorizationVerdict.SUPPRESS, ("mandatory_contradiction_suppression",)

    if outcome == EvaluationOutcome.INPUT_UNAVAILABLE:
        return AuthorizationVerdict.SUPPRESS, ("required_input_unavailable",)

    if outcome == EvaluationOutcome.NOT_REGISTERED:
        return AuthorizationVerdict.SUPPRESS, ("relationship_not_registered",)

    if outcome == EvaluationOutcome.NO_RELATIONSHIP:
        return AuthorizationVerdict.SUPPRESS, ("no_meaningful_signal",)

    return AuthorizationVerdict.SUPPRESS, ("relationship_not_authorized",)


def _evaluate_relationship_result(
    result: RetrievalResult,
    *,
    available_inputs: set[str] | None,
    contradictory_candidates: bool,
    meaningful_signal: bool,
) -> RelationshipAuthorization:
    relationship_id = result.relationship_id.strip()
    modifier_only = _metadata_bool(result.modifier_suppressor_only)
    mandatory_suppression = _metadata_bool(result.mandatory_contradiction_suppression)
    max_level = _metadata_int(result.max_product_level)
    transfer_risk = (result.measurement_transfer_risk or "").strip() or "unknown"
    evidence_strength = (result.evidence_strength or "").strip()

    if not relationship_id:
        return RelationshipAuthorization(
            relationship_id="",
            vector_id=result.vector_id,
            document_id=result.document_id,
            chunk_index=result.chunk_index,
            score=result.score,
            verdict=AuthorizationVerdict.SUPPRESS,
            evaluation_outcome=EvaluationOutcome.NOT_REGISTERED.value,
            evidence_authorized=False,
            recommendation_authorized=False,
            recommendation_eligible=False,
            max_product_level=max_level,
            measurement_transfer_risk=transfer_risk,
            evidence_strength=evidence_strength,
            modifier_suppressor_only=modifier_only,
            mandatory_contradiction_suppression=mandatory_suppression,
            reasons=("missing_relationship_id",),
        )

    if not is_registered_relationship(relationship_id):
        return RelationshipAuthorization(
            relationship_id=relationship_id,
            vector_id=result.vector_id,
            document_id=result.document_id,
            chunk_index=result.chunk_index,
            score=result.score,
            verdict=AuthorizationVerdict.SUPPRESS,
            evaluation_outcome=EvaluationOutcome.NOT_REGISTERED.value,
            evidence_authorized=False,
            recommendation_authorized=False,
            recommendation_eligible=False,
            max_product_level=max_level,
            measurement_transfer_risk=transfer_risk,
            evidence_strength=evidence_strength,
            modifier_suppressor_only=modifier_only,
            mandatory_contradiction_suppression=mandatory_suppression,
            reasons=("relationship_not_registered",),
        )

    policies = load_relationship_policies()
    policy = policies[relationship_id]
    if max_level == 0:
        max_level = policy.max_product_level
    if transfer_risk == "unknown":
        transfer_risk = policy.measurement_transfer_risk

    relationship_contradiction = contradictory_candidates and (
        mandatory_suppression or relationship_id == "R-03"
    )

    outcome = evaluate_relationship_request(
        relationship_id,
        available_inputs=available_inputs,
        contradictory_candidates=relationship_contradiction,
        meaningful_signal=meaningful_signal,
    )
    recommendation_eligible = can_generate_recommendation(relationship_id)
    verdict, reasons = _relationship_verdict_from_outcome(
        outcome,
        recommendation_eligible=recommendation_eligible,
        max_product_level=max_level,
        measurement_transfer_risk=transfer_risk,
    )

    if modifier_only and verdict != AuthorizationVerdict.SUPPRESS:
        verdict = AuthorizationVerdict.SUPPRESS
        reasons = ("modifier_suppressor_only",)

    if relationship_id in {"R-06", "R-08"} and recommendation_eligible:
        recommendation_eligible = False
        if verdict == AuthorizationVerdict.SURFACE:
            verdict = AuthorizationVerdict.QUALIFY
            reasons = ("recommendation_prohibited_for_relationship",)

    evidence_authorized = verdict != AuthorizationVerdict.SUPPRESS
    recommendation_authorized = evidence_authorized and recommendation_eligible

    return RelationshipAuthorization(
        relationship_id=relationship_id,
        vector_id=result.vector_id,
        document_id=result.document_id,
        chunk_index=result.chunk_index,
        score=result.score,
        verdict=verdict,
        evaluation_outcome=outcome.value,
        evidence_authorized=evidence_authorized,
        recommendation_authorized=recommendation_authorized,
        recommendation_eligible=recommendation_eligible,
        max_product_level=max_level,
        measurement_transfer_risk=transfer_risk,
        evidence_strength=evidence_strength,
        modifier_suppressor_only=modifier_only,
        mandatory_contradiction_suppression=mandatory_suppression,
        reasons=reasons,
    )


def _evaluate_general_result(result: RetrievalResult) -> GeneralEvidenceAuthorization:
    return GeneralEvidenceAuthorization(
        vector_id=result.vector_id,
        document_id=result.document_id,
        chunk_index=result.chunk_index,
        score=result.score,
        source_title=result.source_title,
        section_heading=result.section_heading,
        verdict=AuthorizationVerdict.SURFACE,
        evidence_authorized=True,
        recommendation_authorized=False,
        reasons=("general_corpus_evidence",),
    )


def _overall_verdict(
    relationship_decisions: list[RelationshipAuthorization],
    general_evidence: list[GeneralEvidenceAuthorization],
    *,
    multiple_relationship_candidates: bool,
) -> tuple[AuthorizationVerdict, tuple[str, ...]]:
    if not relationship_decisions and not general_evidence:
        return AuthorizationVerdict.SUPPRESS, ("no_retrieval_results",)

    if not relationship_decisions and general_evidence:
        return AuthorizationVerdict.SURFACE, ("general_corpus_evidence_only",)

    relationship_verdicts = {decision.verdict for decision in relationship_decisions}

    if relationship_verdicts == {AuthorizationVerdict.SUPPRESS} and not general_evidence:
        return AuthorizationVerdict.SUPPRESS, ("all_relationship_evidence_suppressed",)

    if multiple_relationship_candidates and AuthorizationVerdict.SUPPRESS not in relationship_verdicts:
        if AuthorizationVerdict.SURFACE in relationship_verdicts:
            return AuthorizationVerdict.QUALIFY, ("multiple_relationship_candidates_ambiguous",)
        return AuthorizationVerdict.QUALIFY, ("multiple_relationship_candidates_ambiguous",)

    if AuthorizationVerdict.SURFACE in relationship_verdicts:
        if AuthorizationVerdict.SUPPRESS in relationship_verdicts:
            return AuthorizationVerdict.QUALIFY, ("mixed_surface_and_suppressed_relationships",)
        return AuthorizationVerdict.SURFACE, ("authorized_evidence_present",)

    if AuthorizationVerdict.QUALIFY in relationship_verdicts or general_evidence:
        return AuthorizationVerdict.QUALIFY, ("qualified_evidence_only",)

    return AuthorizationVerdict.SUPPRESS, ("no_authorized_evidence",)


def evaluate_retrieved_evidence(
    results: list[RetrievalResult],
    *,
    available_inputs: set[str] | None = None,
    meaningful_signal: bool = True,
    contradictory_candidates: bool = False,
) -> EvidencePolicyDecision:
    """
    Deterministically authorize retrieved chunks for downstream agent use.

    Retrieval relevance is not authorization. Evidence validity, interpretation
    authority, and recommendation authority are separate decisions.

    Relationships are evaluated independently. Multiple relationship_ids in one
    retrieval set do NOT automatically imply contradiction. Pass
    contradictory_candidates=True only when an upstream signal explicitly indicates
    an ambiguous/contradictory interpretation context; R-03 and chunks with
    mandatory_contradiction_suppression metadata may then suppress per existing policy.
    """
    relationship_ids = {
        result.relationship_id.strip()
        for result in results
        if result.relationship_id.strip()
    }
    multiple_relationship_candidates = len(relationship_ids) >= 2

    relationship_decisions: list[RelationshipAuthorization] = []
    general_evidence: list[GeneralEvidenceAuthorization] = []
    authorized_results: list[RetrievalResult] = []

    for result in results:
        if result.relationship_id.strip():
            decision = _evaluate_relationship_result(
                result,
                available_inputs=available_inputs,
                contradictory_candidates=contradictory_candidates,
                meaningful_signal=meaningful_signal,
            )
            relationship_decisions.append(decision)
            if decision.evidence_authorized:
                authorized_results.append(result)
        else:
            general = _evaluate_general_result(result)
            general_evidence.append(general)
            authorized_results.append(result)

    overall, reasons = _overall_verdict(
        relationship_decisions,
        general_evidence,
        multiple_relationship_candidates=multiple_relationship_candidates,
    )

    if overall == AuthorizationVerdict.SUPPRESS:
        authorized_results = []

    evidence_authorized = bool(general_evidence) or any(
        decision.evidence_authorized for decision in relationship_decisions
    )
    recommendation_authorized = any(
        decision.recommendation_authorized for decision in relationship_decisions
    )

    suppressed_ids = tuple(
        sorted(
            {
                decision.relationship_id
                for decision in relationship_decisions
                if not decision.evidence_authorized and decision.relationship_id
            }
        )
    )

    return EvidencePolicyDecision(
        overall_verdict=overall,
        evidence_authorized=evidence_authorized,
        recommendation_authorized=recommendation_authorized,
        reasons=reasons,
        relationship_decisions=tuple(relationship_decisions),
        general_evidence=tuple(general_evidence),
        authorized_results=tuple(authorized_results),
        suppressed_relationship_ids=suppressed_ids,
    )
