"""Product salience / insight-worthiness (F4.6).

Orthogonal to F4.1 claim eligibility and F4.5 longitudinal context.
Does not hide direction. Does not authorize recommendations.
Does not treat lifestyle events as physiological importance.

Thresholds below are PRODUCT SALIENCE KNOBS for Directive-page
surfacing. They are not physiological or clinical cutoffs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from analytics.longitudinal import HIGHER_IS_BETTER
from analytics.maturity import METRIC_SPECS, STABLE_PERCENT_THRESHOLD
from analytics.schemas import InsightSalienceSummary, MetricSalience, TrendResult

CONTROL_METRICS = frozenset(spec.metric for spec in METRIC_SPECS if spec.control_metric)

# Percent bands above the F4.1 3% detectability knob.
SALIENCE_PERCENT_CLEAR = 10.0
SALIENCE_PERCENT_STRONG = 15.0

# Absolute "clear" knobs. Product display materiality only.
ABSOLUTE_CLEAR_KNOBS: dict[str, float] = {
    "sleep_duration_hours": 0.50,
    "resting_hr_bpm": 3.0,
    "hrv_sdnn_ms": 3.0,
    "exercise_minutes": 8.0,
    "workout_count": 0.20,
    "steps": 1500.0,
    "vo2_max": 1.0,
}

FAMILY_ACTIVITY = "activity"
FAMILY_RECOVERY = "recovery"
FAMILY_FITNESS = "fitness"

METRIC_FAMILIES: dict[str, frozenset[str]] = {
    FAMILY_ACTIVITY: frozenset({"exercise_minutes", "workout_count", "steps"}),
    FAMILY_RECOVERY: frozenset({"sleep_duration_hours", "hrv_sdnn_ms", "resting_hr_bpm"}),
    FAMILY_FITNESS: frozenset({"vo2_max", "resting_hr_bpm", "exercise_minutes"}),
}

LEVEL_NONE = "none"
LEVEL_LOW = "low"
LEVEL_MODERATE = "moderate"
LEVEL_HIGH = "high"
LEVEL_RANK = {LEVEL_NONE: 0, LEVEL_LOW: 1, LEVEL_MODERATE: 2, LEVEL_HIGH: 3}

BAND_NONE = "none"
BAND_BARELY = "barely_directional"
BAND_CLEAR = "clear"
BAND_STRONG = "strong"

REASON_SMALL_ABSOLUTE = "detectable_but_small_absolute"
REASON_ISOLATED_BARELY = "isolated_barely_directional"
REASON_WEAK_ACTIVITY_PAIR = "same_family_weak_corroboration"
REASON_RECOVERY_CORROBORATION = "recovery_family_corroboration"
REASON_CLEAR = "clear_recent_change"
REASON_STRONG = "strong_recent_change"
REASON_MAINT_GAIN = "maintenance_of_gain"
REASON_MAINT_DECLINE = "maintenance_of_decline"
REASON_COVERAGE = "coverage_caveat"
REASON_TREND_NOT_ALLOWED = "trend_not_allowed"
REASON_EARLY_PATTERN = "early_pattern_observation"
REASON_NO_OLDER_HORIZON = "no_older_horizon"
REASON_LIFESTYLE_NOT_CAUSAL = "lifestyle_context_present_not_causal"
REASON_STABLE_CONTROL = "stable_control_context"

REASON_ORDER = (
    REASON_STRONG,
    REASON_CLEAR,
    REASON_MAINT_GAIN,
    REASON_MAINT_DECLINE,
    REASON_RECOVERY_CORROBORATION,
    REASON_EARLY_PATTERN,
    REASON_WEAK_ACTIVITY_PAIR,
    REASON_SMALL_ABSOLUTE,
    REASON_ISOLATED_BARELY,
    REASON_STABLE_CONTROL,
    REASON_COVERAGE,
    REASON_NO_OLDER_HORIZON,
    REASON_TREND_NOT_ALLOWED,
    REASON_LIFESTYLE_NOT_CAUSAL,
)


def _ordered_reasons(reasons: set[str]) -> tuple[str, ...]:
    return tuple(item for item in REASON_ORDER if item in reasons)


def _percent_change(current: float, baseline: float) -> float | None:
    if baseline == 0:
        return None
    return ((current - baseline) / baseline) * 100.0


def observed_delta(trend: TrendResult) -> tuple[float | None, float | None]:
    """Magnitude used for salience. Uses published deltas when F4.1 exposes them.

    For early-pattern rows, F4.1 blanks percent/direction; compare stored
    current vs baseline values without changing eligibility or published direction.
    """
    if trend.percent_change is not None or trend.absolute_change is not None:
        return trend.percent_change, trend.absolute_change
    if trend.current_value is None or trend.baseline_value in (None, 0):
        return None, None
    return (
        round(_percent_change(trend.current_value, trend.baseline_value) or 0.0, 2),
        round(trend.current_value - trend.baseline_value, 2),
    )


def magnitude_band(metric: str, percent_change: float | None, absolute_change: float | None) -> str:
    if percent_change is None or abs(percent_change) < STABLE_PERCENT_THRESHOLD:
        return BAND_NONE
    abs_knob = ABSOLUTE_CLEAR_KNOBS.get(metric)
    abs_clear = (
        absolute_change is not None and abs_knob is not None and abs(absolute_change) >= abs_knob
    )
    percent_clear = abs(percent_change) >= SALIENCE_PERCENT_CLEAR
    percent_strong = abs(percent_change) >= SALIENCE_PERCENT_STRONG
    if percent_strong and abs_clear:
        return BAND_STRONG
    if percent_clear or abs_clear:
        return BAND_CLEAR
    return BAND_BARELY


def movement_sign(metric: str, percent_change: float | None) -> int:
    if percent_change is None or abs(percent_change) < STABLE_PERCENT_THRESHOLD:
        return 0
    higher_is_better = HIGHER_IS_BETTER.get(metric, True)
    improved = percent_change > 0 if higher_is_better else percent_change < 0
    return 1 if improved else -1


def _cap_level(level: str, *, partial_coverage: bool, gap_caveat: bool) -> str:
    if (partial_coverage or gap_caveat) and level == LEVEL_HIGH:
        return LEVEL_MODERATE
    return level


def attach_salience(trends: Sequence[TrendResult]) -> list[TrendResult]:
    """Attach per-metric salience. Does not mutate F4.1 eligibility or direction."""
    deltas = {trend.metric: observed_delta(trend) for trend in trends}
    bands = {
        trend.metric: magnitude_band(trend.metric, *deltas[trend.metric])
        for trend in trends
    }
    signs = {
        trend.metric: movement_sign(trend.metric, deltas[trend.metric][0])
        for trend in trends
    }
    by_metric = {trend.metric: trend for trend in trends}

    promoting: dict[str, list[str]] = {trend.metric: [] for trend in trends}
    weak_activity_pair: set[str] = set()
    recovery_promoting: set[str] = set()

    for family_name, members in METRIC_FAMILIES.items():
        present = [metric for metric in members if metric in by_metric]
        for metric in present:
            others = [other for other in present if other != metric]
            band = bands[metric]
            for other in others:
                other_band = bands[other]
                if band == BAND_NONE or other_band == BAND_NONE:
                    continue
                if family_name == FAMILY_ACTIVITY and band == BAND_BARELY and other_band == BAND_BARELY:
                    weak_activity_pair.add(metric)
                    continue
                if family_name == FAMILY_RECOVERY and signs[metric] != 0 and signs[metric] == signs[other]:
                    if other not in promoting[metric]:
                        promoting[metric].append(other)
                    recovery_promoting.add(metric)
                    continue
                one_clear = band in {BAND_CLEAR, BAND_STRONG} or other_band in {BAND_CLEAR, BAND_STRONG}
                if one_clear:
                    if other not in promoting[metric]:
                        promoting[metric].append(other)

    attached: list[TrendResult] = []
    for trend in trends:
        metric = trend.metric
        band = bands[metric]
        pct, abs_ch = deltas[metric]
        abs_knob = ABSOLUTE_CLEAR_KNOBS.get(metric, 0.0)
        small_absolute = abs_ch is not None and abs(abs_ch) < abs_knob
        claim = trend.claim_eligibility
        long = trend.longitudinal
        eligible_observation = claim.trend_allowed or claim.early_pattern_allowed
        maintenance_gain = bool(long.maintenance_of_gain)
        maintenance_decline = bool(long.maintenance_of_decline)
        has_recovery = metric in recovery_promoting
        has_promoting = bool(promoting[metric])

        is_control = metric in CONTROL_METRICS
        insight_candidate = False
        if not is_control and (maintenance_gain or maintenance_decline):
            insight_candidate = True
        elif eligible_observation and band in {BAND_CLEAR, BAND_STRONG}:
            insight_candidate = True
        elif not is_control and eligible_observation and has_recovery:
            insight_candidate = True

        recommendation_candidate = bool(
            (not is_control)
            and insight_candidate
            and claim.recommendation_support_allowed
            and (
                band in {BAND_CLEAR, BAND_STRONG} or has_recovery
            )
        )

        if band == BAND_NONE:
            if is_control:
                level = LEVEL_NONE
            else:
                level = LEVEL_MODERATE if (maintenance_gain or maintenance_decline) else LEVEL_NONE
        elif band == BAND_BARELY:
            level = LEVEL_MODERATE if (has_recovery or maintenance_gain or maintenance_decline) else LEVEL_LOW
        elif band == BAND_CLEAR:
            level = LEVEL_HIGH if has_promoting else LEVEL_MODERATE
        else:
            level = LEVEL_HIGH

        level = _cap_level(
            level,
            partial_coverage=trend.partial_coverage,
            gap_caveat=trend.gap_caveat_required,
        )

        reasons: set[str] = set()
        if band == BAND_STRONG:
            reasons.add(REASON_STRONG)
        elif band == BAND_CLEAR:
            reasons.add(REASON_CLEAR)
        if maintenance_gain:
            reasons.add(REASON_MAINT_GAIN)
        if maintenance_decline:
            reasons.add(REASON_MAINT_DECLINE)
        if has_recovery:
            reasons.add(REASON_RECOVERY_CORROBORATION)
        if metric in weak_activity_pair:
            reasons.add(REASON_WEAK_ACTIVITY_PAIR)
        if band == BAND_BARELY and small_absolute:
            reasons.add(REASON_SMALL_ABSOLUTE)
        if band == BAND_BARELY and not has_recovery and metric not in weak_activity_pair:
            reasons.add(REASON_ISOLATED_BARELY)
        if claim.early_pattern_allowed and not claim.trend_allowed:
            reasons.add(REASON_EARLY_PATTERN)
        elif not claim.trend_allowed and not claim.early_pattern_allowed:
            reasons.add(REASON_TREND_NOT_ALLOWED)
        if trend.partial_coverage or trend.gap_caveat_required:
            reasons.add(REASON_COVERAGE)
        if not long.longitudinal_context_available:
            reasons.add(REASON_NO_OLDER_HORIZON)
        if is_control and not insight_candidate:
            reasons.add(REASON_STABLE_CONTROL)

        attached.append(
            replace(
                trend,
                salience=MetricSalience(
                    salience_level=level,
                    magnitude_band=band,
                    insight_candidate=insight_candidate,
                    recommendation_candidate=recommendation_candidate,
                    corroborating_metrics=tuple(promoting[metric]),
                    reasons=_ordered_reasons(reasons),
                    control_metric=is_control,
                ),
            )
        )
    return attached


def summarize_salience(trends: Sequence[TrendResult]) -> InsightSalienceSummary:
    candidates = [trend for trend in trends if trend.salience.insight_candidate]
    rec_candidates = [trend for trend in trends if trend.salience.recommendation_candidate]

    def _sort_key(trend: TrendResult) -> tuple:
        pct, _ = observed_delta(trend)
        return (
            -LEVEL_RANK.get(trend.salience.salience_level, 0),
            -(abs(pct) if pct is not None else 0.0),
            trend.metric,
        )

    primaries = tuple(trend.metric for trend in sorted(candidates, key=_sort_key))
    corroborators: list[str] = []
    for trend in candidates:
        for metric in trend.salience.corroborating_metrics:
            if metric not in primaries and metric not in corroborators:
                corroborators.append(metric)
    reason_set: set[str] = set()
    for trend in trends:
        if trend.salience.insight_candidate or trend.metric in primaries:
            reason_set.update(trend.salience.reasons)
    if not candidates:
        for trend in trends:
            reason_set.update(
                reason
                for reason in trend.salience.reasons
                if reason
                in {
                    REASON_WEAK_ACTIVITY_PAIR,
                    REASON_SMALL_ABSOLUTE,
                    REASON_ISOLATED_BARELY,
                    REASON_NO_OLDER_HORIZON,
                }
            )

    if candidates:
        level = max(
            (trend.salience.salience_level for trend in candidates),
            key=lambda item: LEVEL_RANK[item],
        )
    else:
        detectable = [
            trend
            for trend in trends
            if trend.salience.magnitude_band != BAND_NONE
            or trend.direction not in {"stable", "unknown", None}
        ]
        if detectable:
            level = LEVEL_LOW
        else:
            level = LEVEL_NONE

    return InsightSalienceSummary(
        insight_worthy=bool(candidates),
        recommendation_worthy=bool(rec_candidates),
        primary_metrics=primaries,
        corroborating_metrics=tuple(corroborators),
        reasons=_ordered_reasons(reason_set),
        salience_level=level,
        control_metrics=tuple(
            trend.metric for trend in trends if trend.salience.control_metric
        ),
    )
