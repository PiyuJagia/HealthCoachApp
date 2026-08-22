"""Deterministic health analytics — no LLM, no Pinecone."""

from analytics.maturity import (
    BASELINE_LOOKBACK_DAYS,
    CURRENT_WINDOW_DAYS,
    LONG_HORIZON_DAYS,
    MEDIUM_HORIZON_DAYS,
    MIN_BASELINE_VALID_DAYS,
    MIN_EARLY_PATTERN_OBSERVATIONS,
)
from analytics.schemas import (
    ClaimEligibility,
    InsightSalienceSummary,
    LongitudinalContext,
    MetricSalience,
    TrendResult,
    WeeklyClaimSemantics,
    WeeklySummary,
    WithinWindowSpread,
)
from analytics.trends import get_health_trends, get_weekly_summaries

__all__ = [
    "BASELINE_LOOKBACK_DAYS",
    "CURRENT_WINDOW_DAYS",
    "LONG_HORIZON_DAYS",
    "MEDIUM_HORIZON_DAYS",
    "MIN_BASELINE_VALID_DAYS",
    "MIN_EARLY_PATTERN_OBSERVATIONS",
    "ClaimEligibility",
    "InsightSalienceSummary",
    "LongitudinalContext",
    "MetricSalience",
    "TrendResult",
    "WeeklyClaimSemantics",
    "WeeklySummary",
    "WithinWindowSpread",
    "get_health_trends",
    "get_weekly_summaries",
]
