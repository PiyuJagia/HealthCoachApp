"""Agent-facing tool contracts for Assignment 3 (Google ADK) — no ADK dependency yet."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.health_tools import get_health_trends_for_agent
from app.lifestyle_tools import get_lifestyle_context_for_agent
from rag.evidence_policy import EvidencePolicyDecision, evaluate_retrieved_evidence
from rag.retrieval import retrieve
from rag.schemas import RetrievalResult


def get_trend_signals(
    user_id: int,
    *,
    as_of_date: date | None = None,
    include_weekly_summaries: bool = True,
    weekly_weeks: int = 4,
) -> dict[str, Any]:
    """
    Return deterministic candidate health signals from relational user data.

    Observational only. Callers must honor claim_eligibility and coverage
    provenance; data_sufficient is not part of this contract.
    """
    return get_health_trends_for_agent(
        user_id,
        as_of_date=as_of_date,
        include_weekly_summaries=include_weekly_summaries,
        weekly_weeks=weekly_weeks,
    )


def get_lifestyle_context(
    user_id: int,
    *,
    as_of_date: date,
    lookback_days: int | None = None,
) -> dict[str, Any]:
    """Return stored lifestyle events in a bounded as-of lookback window.

    Observational context only. Does not retrieve RAG evidence or apply policy.
    """
    return get_lifestyle_context_for_agent(
        user_id,
        as_of_date=as_of_date,
        lookback_days=lookback_days,
    )


def retrieve_evidence(
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
) -> list[RetrievalResult]:
    """
    Retrieve curated scientific evidence from Pinecone.

    Retrieval relevance is NOT authorization. Callers should compose this with
    policy evaluation before any user-facing generation step.
    """
    return retrieve(query, top_k=top_k, min_score=min_score)


def evaluate_evidence_policy(
    results: list[RetrievalResult],
    *,
    available_inputs: set[str] | None = None,
    meaningful_signal: bool = True,
    contradictory_candidates: bool = False,
) -> EvidencePolicyDecision:
    """
    Deterministically evaluate retrieved evidence against relationship policy.

    Future ADK orchestration should invoke this automatically after retrieval.
    """
    return evaluate_retrieved_evidence(
        results,
        available_inputs=available_inputs,
        meaningful_signal=meaningful_signal,
        contradictory_candidates=contradictory_candidates,
    )


def retrieve_authorized_evidence(
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
    available_inputs: set[str] | None = None,
    meaningful_signal: bool = True,
    contradictory_candidates: bool = False,
) -> dict[str, Any]:
    """
    Enforced evidence path: retrieve, then apply deterministic policy evaluation.

    Returns both raw retrieval and the authorization decision so future traces
    can record the full path without relying on the LLM to call policy manually.
    """
    results = retrieve_evidence(query, top_k=top_k, min_score=min_score)
    decision = evaluate_evidence_policy(
        results,
        available_inputs=available_inputs,
        meaningful_signal=meaningful_signal,
        contradictory_candidates=contradictory_candidates,
    )
    return {
        "query": query,
        "retrieval_count": len(results),
        "authorized_count": len(decision.authorized_results),
        "overall_verdict": decision.overall_verdict.value,
        "evidence_authorized": decision.evidence_authorized,
        "recommendation_authorized": decision.recommendation_authorized,
        "policy": decision.to_dict(),
        "retrieval": [
            {
                "vector_id": result.vector_id,
                "score": result.score,
                "document_id": result.document_id,
                "chunk_index": result.chunk_index,
                "relationship_id": result.relationship_id,
                "section_heading": result.section_heading,
            }
            for result in results
        ],
    }
