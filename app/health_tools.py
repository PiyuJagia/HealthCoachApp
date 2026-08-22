"""Framework-independent health data tools for a future ADK agent."""

from __future__ import annotations

from datetime import date
from typing import Any

from analytics.longitudinal import summarize_longitudinal
from analytics.maturity import CADENCE_EPISODIC
from analytics.salience import summarize_salience
from analytics.trends import get_health_trends, get_weekly_summaries
from data.database import get_session_factory


def _payload_provenance(trends: list) -> dict[str, Any]:
    daily_like = [trend for trend in trends if trend.cadence != CADENCE_EPISODIC]
    return {
        "as_of_any_daily_metric_available": any(trend.as_of_date_available for trend in daily_like),
        "gap_caveat_required": any(trend.gap_caveat_required for trend in daily_like),
    }


def get_health_trends_for_agent(
    user_id: int,
    *,
    as_of_date: date | None = None,
    include_weekly_summaries: bool = True,
    weekly_weeks: int = 4,
) -> dict[str, Any]:
    """
    Return JSON-serializable trend facts for agent consumption.

    No LLM calls. No Pinecone. Observational metrics only.
    """
    session_factory = get_session_factory()
    with session_factory() as session:
        trends = get_health_trends(session, user_id, as_of_date=as_of_date)
        resolved_as_of = as_of_date or trends[0].period_end
        provenance = _payload_provenance(trends)
        longitudinal_summary = summarize_longitudinal(trends)
        insight_salience = summarize_salience(trends)
        payload: dict[str, Any] = {
            "user_id": user_id,
            "as_of_date": resolved_as_of.isoformat(),
            "as_of_any_daily_metric_available": provenance["as_of_any_daily_metric_available"],
            "gap_caveat_required": provenance["gap_caveat_required"],
            "longitudinal_summary": longitudinal_summary,
            "insight_salience": insight_salience.to_dict(),
            "trends": [trend.to_dict() for trend in trends],
            "disclaimer": (
                "Trend outputs describe observed changes in stored health data. "
                "They do not explain causes. Follow claim_eligibility: do not make "
                "directional trend claims unless trend_allowed is true; if "
                "gap_caveat_required is true, state that as-of-date wearable data "
                "are missing. Weekly summaries describe recorded values in a week; "
                "they are not trends. Honor coverage.claim_semantics: describe "
                "averages only when summary_value_allowed, with observed/expected "
                "counts; do not treat a partial week as complete. Do not make "
                "directional comparisons from weekly summaries unless "
                "summary_comparison_allowed is true. Do not use weekly summaries "
                "to support recommendations unless "
                "summary_recommendation_support_allowed is true. "
                "longitudinal_context compares the recent window to an older "
                "personal reference outside the 7-vs-60 baseline. "
                "maintenance_of_gain means recent values are stable and still "
                "materially better than that older reference; it is not a "
                "celebration directive and does not authorize recommendations. "
                "Weekly summaries cannot independently create a maintenance claim. "
                "insight_salience is a product surfacing contract: direction can "
                "be detectable without being insight_worthy. Salience knobs are "
                "not clinical thresholds. insight_worthy and recommendation_worthy "
                "do not authorize recommendations; evidence policy remains the "
                "recommendation authority. Do not treat an early_pattern "
                "observation as an established personalized trend. "
                "control_metric=true / insight_salience.control_metrics are "
                "bounding context only; a stable control metric does not "
                "authorize an independent reassurance insight or a broader "
                "cardiorespiratory-health claim. "
                "within_window_spread is day-to-day spread of readings, not a "
                "change in average level. A stable or improving mean with "
                "higher spread is not a decline. Do not infer stress, poor "
                "recovery, or cardiovascular instability from spread alone. "
                "Compare current spread to baseline only when "
                "spread_comparison_allowed is true."
            ),
        }
        if include_weekly_summaries:
            summaries = get_weekly_summaries(
                session,
                user_id,
                as_of_date=resolved_as_of,
                weeks=weekly_weeks,
                trend_results=trends,
            )
            payload["weekly_summaries"] = [summary.to_dict() for summary in summaries]
        return payload
