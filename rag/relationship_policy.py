"""Relationship evaluation policy derived from L2-CR claim evidence mappings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag.claim_evidence_registry import load_claim_evidence_registry

INPUT_GATED_RELATIONSHIPS = {
    "R-07": "caffeine_mg",
    "R-08": "alcohol_units",
    "R-09": "cycle_phase",
}

MODIFIER_ONLY_RELATIONSHIPS = frozenset({"R-09"})

HIGH_TRANSFER_RISK_RELATIONSHIPS = frozenset({"R-02", "R-06"})

LEVEL_FOUR_RECOMMENDATION_ELIGIBLE = frozenset({"R-05", "R-07"})

NO_RECOMMENDATION_RELATIONSHIPS = frozenset({"R-06", "R-08"})


class EvaluationOutcome(str, Enum):
    RELATIONSHIP_DETECTED = "relationship_detected"
    SUPPRESSED_CONTRADICTION = "suppressed_contradiction"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_REGISTERED = "not_registered"
    INPUT_UNAVAILABLE = "input_unavailable"
    NO_RELATIONSHIP = "no_relationship"
    MODIFIER_ONLY = "modifier_only"


@dataclass(frozen=True)
class RelationshipPolicy:
    relationship_id: str
    max_product_level: int
    measurement_transfer_risk: str
    standalone_insight_allowed: bool
    input_metric: str | None = None
    requires_contradiction_suppression: bool = False


def load_relationship_policies() -> dict[str, RelationshipPolicy]:
    """Build one policy per relationship from the primary claim-evidence row."""
    policies: dict[str, RelationshipPolicy] = {}

    for record in load_claim_evidence_registry():
        if record.claim_id in policies:
            continue

        policies[record.claim_id] = RelationshipPolicy(
            relationship_id=record.claim_id,
            max_product_level=int(record.product_level),
            measurement_transfer_risk=record.evidence_measurement,
            standalone_insight_allowed=record.claim_id not in MODIFIER_ONLY_RELATIONSHIPS,
            input_metric=INPUT_GATED_RELATIONSHIPS.get(record.claim_id),
            requires_contradiction_suppression=record.claim_id == "R-03",
        )

    return policies


def is_registered_relationship(relationship_id: str) -> bool:
    return relationship_id in load_relationship_policies()


def can_evaluate_relationship(
    relationship_id: str,
    *,
    available_inputs: set[str] | None = None,
) -> EvaluationOutcome:
    policies = load_relationship_policies()
    policy = policies.get(relationship_id)
    if policy is None:
        return EvaluationOutcome.NOT_REGISTERED

    if policy.input_metric and (available_inputs is None or policy.input_metric not in available_inputs):
        return EvaluationOutcome.INPUT_UNAVAILABLE

    if not policy.standalone_insight_allowed:
        return EvaluationOutcome.MODIFIER_ONLY

    return EvaluationOutcome.RELATIONSHIP_DETECTED


def can_generate_recommendation(relationship_id: str) -> bool:
    if relationship_id in NO_RECOMMENDATION_RELATIONSHIPS:
        return False
    if relationship_id not in LEVEL_FOUR_RECOMMENDATION_ELIGIBLE:
        return False
    if relationship_id in HIGH_TRANSFER_RISK_RELATIONSHIPS:
        return False

    policies = load_relationship_policies()
    policy = policies.get(relationship_id)
    if policy is None:
        return False
    return policy.max_product_level >= 4


def should_suppress_contradictory_interpretation(
    relationship_id: str,
    *,
    contradictory_candidates: bool,
) -> bool:
    if not contradictory_candidates:
        return False
    if relationship_id == "R-03":
        return True
    return contradictory_candidates


def evaluate_relationship_request(
    relationship_id: str,
    *,
    available_inputs: set[str] | None = None,
    contradictory_candidates: bool = False,
    meaningful_signal: bool = True,
) -> EvaluationOutcome:
    if not is_registered_relationship(relationship_id):
        return EvaluationOutcome.NOT_REGISTERED

    if should_suppress_contradictory_interpretation(
        relationship_id,
        contradictory_candidates=contradictory_candidates,
    ):
        return EvaluationOutcome.SUPPRESSED_CONTRADICTION

    gated = can_evaluate_relationship(relationship_id, available_inputs=available_inputs)
    if gated != EvaluationOutcome.RELATIONSHIP_DETECTED:
        return gated

    if not meaningful_signal:
        return EvaluationOutcome.NO_RELATIONSHIP

    return EvaluationOutcome.RELATIONSHIP_DETECTED
