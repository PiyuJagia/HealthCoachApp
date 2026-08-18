"""Framework-independent health data tools for a future ADK agent."""

from __future__ import annotations

from datetime import date
from typing import Any

from analytics.trends import get_health_trends, get_weekly_summaries
from data.database import get_session_factory


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
        payload: dict[str, Any] = {
            "user_id": user_id,
            "as_of_date": (as_of_date or trends[0].period_end).isoformat(),
            "trends": [trend.to_dict() for trend in trends],
            "disclaimer": (
                "Trend outputs describe observed changes in stored health data. "
                "They do not explain causes."
            ),
        }
        if include_weekly_summaries:
            summaries = get_weekly_summaries(
                session,
                user_id,
                as_of_date=as_of_date,
                weeks=weekly_weeks,
            )
            payload["weekly_summaries"] = [summary.to_dict() for summary in summaries]
        return payload
