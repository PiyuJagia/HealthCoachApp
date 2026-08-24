"""Per-run context and ADK tool factories."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app import agent_tools
from app.recommendation_boundary import compute_final_recommendation_allowed, salience_flags_from_signals
from evals.trace_schema import (
    FinalGuardTrace,
    GenerationTrace,
    ModelCallContextTrace,
    PolicyTrace,
    RecommendationBoundaryTrace,
    RetrievalTraceItem,
    ToolCallTrace,
    sanitize_for_trace,
)
from rag.evidence_policy import EvidencePolicyDecision


def _summarize_trends(result: dict[str, Any]) -> dict[str, Any]:
    trends = result.get("trends") or []
    return {
        "as_of_date": result.get("as_of_date"),
        "gap_caveat_required": result.get("gap_caveat_required"),
        "as_of_any_daily_metric_available": result.get("as_of_any_daily_metric_available"),
        "longitudinal_summary": result.get("longitudinal_summary"),
        "insight_salience": result.get("insight_salience"),
        "trend_count": len(trends),
        "metrics": [
            {
                "metric": item.get("metric"),
                "cadence": item.get("cadence"),
                "direction": item.get("direction"),
                "percent_change": item.get("percent_change"),
                "as_of_date_available": item.get("as_of_date_available"),
                "coverage_ratio": item.get("coverage_ratio"),
                "data_maturity_state": item.get("data_maturity_state"),
                "gap_caveat_required": item.get("gap_caveat_required"),
                "claim_eligibility": item.get("claim_eligibility"),
                "maintenance_of_gain": (item.get("longitudinal") or {}).get("maintenance_of_gain"),
                "current_vs_long_term_percent": (item.get("longitudinal") or {}).get(
                    "current_vs_long_term_percent"
                ),
                "salience_level": (item.get("salience") or {}).get("salience_level"),
                "insight_candidate": (item.get("salience") or {}).get("insight_candidate"),
                "recommendation_candidate": (item.get("salience") or {}).get(
                    "recommendation_candidate"
                ),
                "control_metric": item.get("control_metric")
                or (item.get("salience") or {}).get("control_metric"),
                "within_window_spread": item.get("within_window_spread"),
            }
            for item in trends
        ],
    }


def _summarize_lifestyle(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of_date": result.get("as_of_date"),
        "lookback_days": result.get("lookback_days"),
        "window_start": result.get("window_start"),
        "window_end": result.get("window_end"),
        "event_count": result.get("event_count"),
        "event_types": [item.get("event_type") for item in result.get("by_type") or []],
        "late_work_context_event_count": result.get("late_work_context_event_count"),
        "policy_available_inputs": list(result.get("policy_available_inputs") or []),
    }


def _summarize_evidence(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "query": result.get("query"),
        "retrieval_count": result.get("retrieval_count"),
        "authorized_count": result.get("authorized_count"),
        "overall_verdict": result.get("overall_verdict"),
        "evidence_authorized": result.get("evidence_authorized"),
        "recommendation_authorized": result.get("recommendation_authorized"),
        "recommendation_worthy": result.get("recommendation_worthy"),
        "final_recommendation_allowed": result.get("final_recommendation_allowed"),
        "available_inputs": list(result.get("available_inputs") or []),
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
    model_calls: list[ModelCallContextTrace] = field(default_factory=list)
    last_lifestyle_context: dict[str, Any] = field(default_factory=dict)
    lifestyle_available_inputs: set[str] = field(default_factory=set)
    recommendation_boundary: RecommendationBoundaryTrace | None = None
    output_contract: dict[str, Any] | None = None
    raw_model_output: dict[str, Any] | None = None

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
        Honor claim_eligibility: snapshot_allowed, early_pattern_allowed, and
        trend_allowed are distinct. Do not state a directional trend unless
        trend_allowed is true. If gap_caveat_required is true, explicitly note
        that as-of-date wearable data are missing; still use recent history.
        Weekly summaries describe recorded week values with coverage.claim_semantics;
        they are not trends. Do not treat a weekly average as a complete-week
        measurement when partial_coverage is true. Do not make directional
        comparisons from weekly summaries unless summary_comparison_allowed is
        true, and do not use them for recommendations unless
        summary_recommendation_support_allowed is true.
        longitudinal_context is observational. If maintenance_of_gain is true,
        the recent window is stable while remaining materially better than an
        older personal reference the 7-vs-60 comparison does not include.
        That is not a celebration directive and does not authorize recommendations.
        Weekly summaries cannot independently create a maintenance claim.
        insight_salience is observational product-surfacing metadata.
        Direction can be detectable without being insight_worthy.
        When insight_worthy is false, do not return INSIGHT status from these
        trends even if some directions are improving or declining; they may
        remain visible as supporting analytics.
        Do not treat insight_worthy or recommendation_worthy as recommendation
        authorization. A recommendation may be output only when
        final_recommendation_allowed is true after evidence policy is applied.
        Do not treat an early_pattern observation as an
        established personalized trend.
        control_metric=true metrics (also listed in
        insight_salience.control_metrics) are bounding context.
        Do not treat a stable control metric as an independent
        health-reassurance insight or as evidence of broader
        cardiorespiratory wellness.
        within_window_spread describes day-to-day spread of readings.
        It is not a level/direction claim. A stable or improving mean with
        higher spread is not a decline. Do not infer stress, poor recovery,
        or cardiovascular instability from spread alone. Compare to baseline
        spread only when spread_comparison_allowed is true.
        Put the concise priority in primary_message and the explanation in insight.
        Stay at named metric facts or named multi-metric summaries. Do not
        invent supporting_metric_facts; the system stamps those.
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
            if (item.get("claim_eligibility") or {}).get("trend_allowed")
            and item.get("direction") not in {"stable", "unknown", None}
        ]
        emerging = [
            item.get("metric")
            for item in summary.get("metrics") or []
            if (item.get("claim_eligibility") or {}).get("early_pattern_allowed")
            and not (item.get("claim_eligibility") or {}).get("trend_allowed")
        ]
        maintaining = [
            item.get("metric")
            for item in summary.get("metrics") or []
            if item.get("maintenance_of_gain")
        ]
        salience = summary.get("insight_salience") or result.get("insight_salience") or {}
        insight_worthy = bool(salience.get("insight_worthy"))
        recommendation_worthy = bool(salience.get("recommendation_worthy"))
        primary = [metric for metric in (salience.get("primary_metrics") or []) if metric]
        early_primaries = [
            item.get("metric")
            for item in summary.get("metrics") or []
            if item.get("metric") in set(primary)
            and (item.get("claim_eligibility") or {}).get("early_pattern_allowed")
            and not (item.get("claim_eligibility") or {}).get("trend_allowed")
        ]
        if insight_worthy:
            context.record_decision(
                "Insight-worthy signal(s): "
                f"{', '.join(primary[:3]) or 'see insight_salience'}."
            )
            if early_primaries:
                context.record_decision(
                    "Early-pattern observation(s), not an established trend: "
                    f"{', '.join(early_primaries[:3])}."
                )
            if recommendation_worthy:
                context.record_decision(
                    "Physiology is recommendation-candidate; evidence policy remains "
                    "the authorization gate."
                )
            else:
                context.record_decision(
                    "Insight-worthy but not recommendation-worthy; this does not "
                    "authorize a recommendation."
                )
        elif meaningful:
            context.record_decision(
                "Detectable directional movement is not insight-worthy: "
                f"{', '.join(meaningful[:3])}."
            )
        elif emerging:
            context.record_decision(
                f"Emerging-pattern signals only (no established trend): {', '.join(emerging[:3])}."
            )
        elif maintaining:
            context.record_decision(
                "Recent window is stable; longitudinal context shows maintained "
                f"prior gains for: {', '.join(maintaining[:3])}."
            )
        else:
            context.record_decision("No significant new directional pattern detected in current comparison.")
        return result

    def get_lifestyle_context(lookback_days: int = 14) -> dict[str, Any]:
        """Inspect stored user-specific lifestyle events in a bounded lookback window.

        Use after identifying a meaningful health observation if user context
        may matter. This is observational context, not scientific evidence.
        Co-occurrence is not causation. Do not treat lifestyle events as proof
        of a cause, and do not make recommendations from this tool.
        """
        args = {
            "user_id": context.user_id,
            "as_of_date": context.as_of_date.isoformat(),
            "lookback_days": lookback_days,
        }
        context.record_act("get_lifestyle_context", args)
        result = agent_tools.get_lifestyle_context(
            context.user_id,
            as_of_date=context.as_of_date,
            lookback_days=lookback_days,
        )
        context.last_lifestyle_context = result
        context.lifestyle_available_inputs = set(result.get("policy_available_inputs") or [])
        summary = _summarize_lifestyle(result)
        context.tool_calls.append(
            ToolCallTrace(
                tool_name="get_lifestyle_context",
                arguments=args,
                result_summary=summary,
            )
        )
        context.record_observe("get_lifestyle_context", summary)
        types_seen = ", ".join(summary.get("event_types") or []) or "none"
        context.record_decision(
            f"Lifestyle context inspected: {summary.get('event_count') or 0} events "
            f"({types_seen}); observational only."
        )
        return result

    def retrieve_authorized_evidence(
        query: str,
        meaningful_signal: bool = True,
    ) -> dict[str, Any]:
        """Retrieve curated scientific evidence with deterministic policy enforcement.

        Use when interpretation needs authorized evidence grounding.
        Policy verdict and recommendation_authorized are determined by code, not by you.
        recommendation_authorized is scientific/policy permission only.
        recommendation_worthy comes from insight_salience and is the product gate.
        final_recommendation_allowed is true only when both are true.
        Do not emit a recommendation unless final_recommendation_allowed is true.
        Lifestyle-derived available_inputs are applied only if get_lifestyle_context
        was already called in this run.
        """
        args = {"query": query, "meaningful_signal": meaningful_signal}
        context.record_act("retrieve_authorized_evidence", args)
        results = agent_tools.retrieve_evidence(query)
        available_inputs = (
            context.lifestyle_available_inputs if context.last_lifestyle_context else None
        )
        decision = agent_tools.evaluate_evidence_policy(
            results,
            available_inputs=available_inputs,
            meaningful_signal=meaningful_signal,
        )
        context.last_policy_decision = decision
        _insight_worthy, recommendation_worthy = salience_flags_from_signals(context.candidate_signals)
        allowed = compute_final_recommendation_allowed(
            recommendation_worthy=recommendation_worthy,
            recommendation_authorized=decision.recommendation_authorized,
        )
        result = {
            "query": query,
            "retrieval_count": len(results),
            "authorized_count": len(decision.authorized_results),
            "overall_verdict": decision.overall_verdict.value,
            "evidence_authorized": decision.evidence_authorized,
            "recommendation_authorized": decision.recommendation_authorized,
            "recommendation_worthy": recommendation_worthy,
            "final_recommendation_allowed": allowed,
            "available_inputs": sorted(available_inputs or []),
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
            f" recommendation_authorized={summary.get('recommendation_authorized')};"
            f" recommendation_worthy={summary.get('recommendation_worthy')};"
            f" final_recommendation_allowed={summary.get('final_recommendation_allowed')}.{rel_part}"
        )
        return result

    return get_trend_signals, get_lifestyle_context, retrieve_authorized_evidence
