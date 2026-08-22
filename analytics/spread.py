"""Within-window spread of daily readings (F4.9 / T12).

LEVEL (F4.1 mean / direction) and SPREAD (day-to-day dispersion) are
different properties. This module does not diagnose, score, or promote
salience. HRV-only for MVP.

Do not call this object “HRV variability.” That name already belongs to
the nightly SDNN metric.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import mean, stdev

from analytics.schemas import ClaimEligibility, WithinWindowSpread

SPREAD_METRICS = frozenset({"hrv_sdnn_ms"})

# Facts require two current observations to compute sample SD.
MIN_SPREAD_OBSERVATIONS = 2
# Personal comparison needs a fuller current week than a two-point SD.
MIN_SPREAD_COMPARISON_CURRENT = 4
# Numerical floor so ratio never divides by ~0. Not a clinical cutoff.
MIN_USABLE_BASELINE_SPREAD = 1e-6


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _sample_sd(values: Sequence[float]) -> float | None:
    if len(values) < MIN_SPREAD_OBSERVATIONS:
        return None
    return float(stdev(values))


def build_within_window_spread(
    *,
    metric: str,
    current_values: Sequence[float],
    baseline_values: Sequence[float],
    claim: ClaimEligibility,
    baseline_ready: bool,
    partial_coverage: bool,
    gap_caveat_required: bool,
) -> WithinWindowSpread | None:
    """Build HRV spread from the same F4.1 current/baseline value lists."""
    if metric not in SPREAD_METRICS:
        return None

    current = list(current_values)
    baseline = list(baseline_values)
    observation_count = len(current)
    current_mean = mean(current) if current else None
    current_sd = _sample_sd(current)
    current_min = min(current) if current else None
    current_max = max(current) if current else None
    current_range = (
        current_max - current_min if current_min is not None and current_max is not None else None
    )
    baseline_sd = _sample_sd(baseline)

    spread_observation_allowed = current_sd is not None
    usable_baseline = baseline_sd is not None and baseline_sd >= MIN_USABLE_BASELINE_SPREAD
    spread_comparison_allowed = (
        spread_observation_allowed
        and usable_baseline
        and baseline_ready
        and claim.trend_allowed
        and observation_count >= MIN_SPREAD_COMPARISON_CURRENT
        and not partial_coverage
        and not gap_caveat_required
    )
    spread_ratio = (
        current_sd / baseline_sd if spread_comparison_allowed and current_sd is not None and baseline_sd else None
    )
    return WithinWindowSpread(
        observation_count=observation_count,
        mean=_round_or_none(current_mean),
        sample_standard_deviation=_round_or_none(current_sd),
        min=_round_or_none(current_min),
        max=_round_or_none(current_max),
        range=_round_or_none(current_range),
        baseline_standard_deviation=_round_or_none(baseline_sd),
        spread_ratio=_round_or_none(spread_ratio),
        spread_observation_allowed=spread_observation_allowed,
        spread_comparison_allowed=spread_comparison_allowed,
    )
