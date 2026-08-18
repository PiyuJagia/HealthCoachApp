"""Per-run context and ADK tool factories."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app import agent_tools
from evals.trace_schema import (
    FinalGuardTrace,
    GenerationTrace,
    PolicyTrace,
    RetrievalTraceItem,
    ToolCallTrace,
    sanitize_for_trace,
)
from rag.evidence_policy import EvidencePolicyDecision


def _summarize_trends(result: dict[str, Any]) -> dict[str, Any]:
    trends = result.get("trends") or []
    return {
        "as_of_date": result.get("as_of_date"),
        "trend_count": len(trends),
        "metrics": [
            {
                "metric": item.get("metric"),
                "direction": item.get("direction"),
                "data_sufficient": item.get("data_sufficient"),
                "percent_change": item.get("percent_change"),
            }
            for item in trends
        ],
    }


def _summarize_evidence(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "query": result.get("query"),
        "retrieval_count": result.get("retrieval_count"),
        "authorized_count": result.get("authorized_count"),
        "overall_verdict": result.get("overall_verdict"),
        "evidence_authorized": result.get("evidence_authorized"),
        "recommendation_authorized": result.get("recommendation_authorized"),
        "relationship_ids": [
            item.get("relationship_id")
            for item in result.get("retrieval") or []
            if item.get("relationship_id")
        ],
    }


@dataclass
class RunContext:
    scenario_id: str
    user_id: int
    as_of_date: date
    candidate_signals: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    retrieval: list[RetrievalTraceItem] = field(default_factory=list)
    policy: PolicyTrace | None = None
    last_policy_decision: EvidencePolicyDecision | None = None
    activity_log: list[dict[str, Any]] = field(default_factory=list)
    generation: GenerationTrace | None = None
    final_guard: FinalGuardTrace | None = None

    def record_decision(self, label: str) -> None:
        self.activity_log.append({"phase": "DECISION", "label": label})

    def record_act(self, tool_name: str, arguments: dict[str, Any]) -> None:
        self.activity_log.append(
            {
                "phase": "ACT",
                "tool": tool_name,
                "arguments": sanitize_for_trace(arguments),
            }
        )

    def record_observe(self, tool_name: str, summary: dict[str, Any]) -> None:
        self.activity_log.append(
            {
                "phase": "OBSERVE",
                "tool": tool_name,
                "summary": sanitize_for_trace(summary),
            }
        )

    def record_final(self, label: str) -> None:
        self.activity_log.append({"phase": "FINAL", "label": label})


def build_tools(context: RunContext) -> tuple:
    """Create ADK-callable tools bound to the current review."""

    def get_trend_signals() -> dict[str, Any]:
        """Inspect deterministic health signals from the user's relational health database.

        Use this first to learn what objectively changed in stored health data.
        Do not calculate trends yourself.
        """
        context.record_act("get_trend_signals", {"user_id": context.user_id, "as_of_date": context.as_of_date.isoformat()})
        result = agent_tools.get_trend_signals(context.user_id, as_of_date=context.as_of_date)
        context.candidate_signals = result
        summary = _summarize_trends(result)
        context.tool_calls.append(
            ToolCallTrace(
                tool_name="get_trend_signals",
                arguments={"user_id": context.user_id, "as_of_date": context.as_of_date.isoformat()},
                result_summary=summary,
            )
        )
        context.record_observe("get_trend_signals", summary)
        meaningful = [
            item.get("metric")
            for item in summary.get("metrics") or []
            if item.get("data_sufficient") and item.get("direction") not in {"stable", "unknown", None}
        ]
        if meaningful:
            context.record_decision(f"Reviewing stored signals for: {', '.join(meaningful[:3])}.")
        else:
            context.record_decision("No significant new directional pattern detected in current comparison.")
        return result

    def retrieve_authorized_evidence(
        query: str,
        meaningful_signal: bool = True,
    ) -> dict[str, Any]:
        """Retrieve curated scientific evidence with deterministic policy enforcement.

        Use when interpretation needs authorized evidence grounding.
        Policy verdict and recommendation authorization are determined by code, not by you.
        """
        args = {"query": query, "meaningful_signal": meaningful_signal}
        context.record_act("retrieve_authorized_evidence", args)
        results = agent_tools.retrieve_evidence(query)
        decision = agent_tools.evaluate_evidence_policy(
            results,
            meaningful_signal=meaningful_signal,
        )
        context.last_policy_decision = decision
        result = {
            "query": query,
            "retrieval_count": len(results),
            "authorized_count": len(decision.authorized_results),
            "overall_verdict": decision.overall_verdict.value,
            "evidence_authorized": decision.evidence_authorized,
            "recommendation_authorized": decision.recommendation_authorized,
            "policy": decision.to_dict(),
            "retrieval": [
                {
                    "vector_id": item.vector_id,
                    "score": item.score,
                    "document_id": item.document_id,
                    "chunk_index": item.chunk_index,
                    "relationship_id": item.relationship_id,
                    "section_heading": item.section_heading,
                }
                for item in results
            ],
        }
        summary = _summarize_evidence(result)
        context.tool_calls.append(
            ToolCallTrace(
                tool_name="retrieve_authorized_evidence",
                arguments=args,
                result_summary=summary,
            )
        )
        policy_payload = result.get("policy") or {}
        context.policy = PolicyTrace(
            overall_verdict=str(result.get("overall_verdict") or ""),
            reasons=list(policy_payload.get("reasons") or []),
            relationship_decisions=list(policy_payload.get("relationship_decisions") or []),
            suppressed_relationship_ids=list(policy_payload.get("suppressed_relationship_ids") or []),
        )
        for item in result.get("retrieval") or []:
            rel_decisions = {
                decision.get("relationship_id"): decision
                for decision in policy_payload.get("relationship_decisions") or []
            }
            rel_id = item.get("relationship_id") or ""
            rel_meta = rel_decisions.get(rel_id, {})
            context.retrieval.append(
                RetrievalTraceItem(
                    query=query,
                    score=float(item.get("score") or 0.0),
                    document_id=str(item.get("document_id") or ""),
                    vector_id=str(item.get("vector_id") or ""),
                    chunk_index=int(item.get("chunk_index") or 0),
                    relationship_id=rel_id,
                    policy_metadata={
                        "evidence_strength": rel_meta.get("evidence_strength"),
                        "verdict": rel_meta.get("verdict"),
                        "recommendation_authorized": rel_meta.get("recommendation_authorized"),
                    },
                )
            )
        context.record_observe("retrieve_authorized_evidence", summary)
        rel_ids = summary.get("relationship_ids") or []
        rel_part = f" relationships={', '.join(rel_ids)}" if rel_ids else ""
        context.record_decision(
            f"Evidence lookup complete: verdict={summary.get('overall_verdict')};"
            f" recommendation_authorized={summary.get('recommendation_authorized')}.{rel_part}"
        )
        return result

    return get_trend_signals, retrieve_authorized_evidence
