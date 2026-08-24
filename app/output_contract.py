"""T7/T8 output interpretation contract.

Stamps supporting_metric_facts from the existing F4.1–F4.9 payload and
enforces the quiet-path / primary-card split. Does not recompute analytics,
salience, evidence policy, or the F4.7 recommendation gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.recommendation_boundary import (
    INSIGHT_STATUS,
    NO_PATTERN_STATUS,
    RECOMMENDATION_STATUS,
    salience_flags_from_signals,
)
from evals.trace_schema import (
    ORIGIN_DETERMINISTIC_ANALYTICS,
    ORIGIN_OUTPUT_CONTRACT,
    ORIGIN_SPREAD_ANALYTICS,
    sanitize_for_trace,
)

ROLE_PRIMARY = "primary"
ROLE_SUPPORTING = "supporting"
ROLE_CONTROL = "control"
ROLE_SPREAD_CONTEXT = "spread_context"
SOURCE_TREND_TOOL = "get_trend_signals"

_ELEVATED_STATUSES = {INSIGHT_STATUS, RECOMMENDATION_STATUS}


def _text_present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _level_fact(trend: dict[str, Any], *, role: str, origin: str) -> dict[str, Any]:
    salience = _as_dict(trend.get("salience"))
    longitudinal = _as_dict(trend.get("longitudinal"))
    return {
        "metric": trend.get("metric"),
        "role": role,
        "current_value": trend.get("current_value"),
        "baseline_value": trend.get("baseline_value"),
        "percent_change": trend.get("percent_change"),
        "absolute_change": trend.get("absolute_change"),
        "direction": trend.get("direction"),
        "data_maturity_state": trend.get("data_maturity_state"),
        "coverage_ratio": trend.get("coverage_ratio"),
        "observation_count_current": trend.get("observation_count_current"),
        "expected_observation_count_current": trend.get("expected_observation_count_current"),
        "partial_coverage": trend.get("partial_coverage"),
        "gap_caveat_required": trend.get("gap_caveat_required"),
        "control_metric": bool(trend.get("control_metric") or salience.get("control_metric")),
        "insight_candidate": bool(salience.get("insight_candidate")),
        "maintenance_of_gain": bool(longitudinal.get("maintenance_of_gain")),
        "maintenance_of_decline": bool(longitudinal.get("maintenance_of_decline")),
        "origin": origin,
        "source": SOURCE_TREND_TOOL,
    }


def _spread_fact(trend: dict[str, Any], spread: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric": trend.get("metric"),
        "role": ROLE_SPREAD_CONTEXT,
        "current_value": spread.get("mean", trend.get("current_value")),
        "direction": trend.get("direction"),
        "data_maturity_state": trend.get("data_maturity_state"),
        "spread_observation_allowed": spread.get("spread_observation_allowed"),
        "spread_comparison_allowed": spread.get("spread_comparison_allowed"),
        "observation_count": spread.get("observation_count"),
        "mean": spread.get("mean"),
        "sample_standard_deviation": spread.get("sample_standard_deviation"),
        "min": spread.get("min"),
        "max": spread.get("max"),
        "range": spread.get("range"),
        "baseline_standard_deviation": spread.get("baseline_standard_deviation"),
        "spread_ratio": spread.get("spread_ratio"),
        "control_metric": False,
        "origin": ORIGIN_SPREAD_ANALYTICS,
        "source": SOURCE_TREND_TOOL,
    }


def stamp_supporting_metric_facts(signals: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build compact metric facts from get_trend_signals. Model-invented lists are ignored."""
    payload = signals or {}
    trends = [item for item in (payload.get("trends") or []) if isinstance(item, dict)]
    salience = _as_dict(payload.get("insight_salience"))
    insight_worthy = bool(salience.get("insight_worthy"))
    primary_metrics = [str(item) for item in (salience.get("primary_metrics") or [])]
    control_names = {str(item) for item in (salience.get("control_metrics") or [])}
    by_metric = {str(item.get("metric")): item for item in trends if item.get("metric")}

    primaries: list[dict[str, Any]] = []
    supporting: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    spreads: list[dict[str, Any]] = []
    stamped_level: set[str] = set()

    def _is_control(trend: dict[str, Any]) -> bool:
        metric = str(trend.get("metric") or "")
        salience_row = _as_dict(trend.get("salience"))
        return bool(
            trend.get("control_metric")
            or salience_row.get("control_metric")
            or metric in control_names
        )

    for metric in primary_metrics:
        trend = by_metric.get(metric)
        if trend is None or _is_control(trend):
            continue
        if insight_worthy:
            primaries.append(
                _level_fact(trend, role=ROLE_PRIMARY, origin=ORIGIN_DETERMINISTIC_ANALYTICS)
            )
            stamped_level.add(metric)

    for trend in trends:
        metric = str(trend.get("metric") or "")
        if not metric:
            continue
        if _is_control(trend):
            controls.append(
                _level_fact(trend, role=ROLE_CONTROL, origin=ORIGIN_DETERMINISTIC_ANALYTICS)
            )
            stamped_level.add(metric)
            continue
        salience_row = _as_dict(trend.get("salience"))
        if metric not in stamped_level and salience_row.get("insight_candidate"):
            supporting.append(
                _level_fact(trend, role=ROLE_SUPPORTING, origin=ORIGIN_DETERMINISTIC_ANALYTICS)
            )
            stamped_level.add(metric)

    for trend in trends:
        metric = str(trend.get("metric") or "")
        spread = trend.get("within_window_spread")
        if not isinstance(spread, dict) or not spread.get("spread_observation_allowed"):
            continue
        if metric not in stamped_level and not _is_control(trend):
            supporting.append(
                _level_fact(trend, role=ROLE_SUPPORTING, origin=ORIGIN_DETERMINISTIC_ANALYTICS)
            )
            stamped_level.add(metric)
        spreads.append(_spread_fact(trend, spread))

    return primaries + supporting + controls + spreads


@dataclass(frozen=True)
class OutputInterpretationDecision:
    insight_worthy: bool
    model_status: str | None
    model_primary_present: bool
    model_motivational_quote_present: bool
    final_status: str | None
    primary_message_present: bool
    motivational_quote_present: bool
    supporting_metric_facts: tuple[dict[str, Any], ...]
    supporting_metric_facts_origin: str = ORIGIN_OUTPUT_CONTRACT
    quiet_path_applied: bool = False
    motivational_quote_removed_on_quiet_path: bool = False
    model_respected_quiet_path: bool = True
    violations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_trace(
            {
                "insight_worthy": self.insight_worthy,
                "model_status": self.model_status,
                "model_primary_present": self.model_primary_present,
                "model_motivational_quote_present": self.model_motivational_quote_present,
                "final_status": self.final_status,
                "primary_message_present": self.primary_message_present,
                "motivational_quote_present": self.motivational_quote_present,
                "supporting_metric_facts": list(self.supporting_metric_facts),
                "supporting_metric_facts_origin": self.supporting_metric_facts_origin,
                "quiet_path_applied": self.quiet_path_applied,
                "motivational_quote_removed_on_quiet_path": self.motivational_quote_removed_on_quiet_path,
                "model_respected_quiet_path": self.model_respected_quiet_path,
                "violations": list(self.violations),
            }
        )


def apply_output_interpretation_contract(
    structured: dict[str, Any],
    *,
    signals: dict[str, Any] | None,
) -> tuple[dict[str, Any], OutputInterpretationDecision]:
    """Stamp facts and rewrite a non-worthy review onto the quiet path.

    Does not invent primary_message copy. Does not change F4.7 rec permission.
    """
    insight_worthy, _recommendation_worthy = salience_flags_from_signals(signals)
    facts = stamp_supporting_metric_facts(signals)
    updated = dict(structured)
    updated["supporting_metric_facts"] = facts
    model_status = str(updated.get("status") or "") or None
    model_primary = _text_present(updated.get("primary_message"))
    model_quote = _text_present(updated.get("motivational_quote"))
    violations: list[str] = []
    quiet_applied = False
    quote_removed = False

    if not insight_worthy:
        if model_status in _ELEVATED_STATUSES:
            violations.append("elevated_status_without_insight_worthiness")
            updated["status"] = NO_PATTERN_STATUS
            quiet_applied = True
        if model_primary:
            violations.append("primary_message_on_quiet_path")
            updated["primary_message"] = None
            quiet_applied = True
        if _text_present(updated.get("subtext")):
            updated["subtext"] = None
            quiet_applied = True

    quiet_now = (
        str(updated.get("status") or "") == NO_PATTERN_STATUS
        or not _text_present(updated.get("primary_message"))
    )
    if quiet_now and _text_present(updated.get("motivational_quote")):
        violations.append("motivational_quote_on_quiet_path")
        updated["motivational_quote"] = None
        quote_removed = True
        quiet_applied = True

    final_status = str(updated.get("status") or "") or None
    decision = OutputInterpretationDecision(
        insight_worthy=insight_worthy,
        model_status=model_status,
        model_primary_present=model_primary,
        model_motivational_quote_present=model_quote,
        final_status=final_status,
        primary_message_present=_text_present(updated.get("primary_message")),
        motivational_quote_present=_text_present(updated.get("motivational_quote")),
        supporting_metric_facts=tuple(facts),
        quiet_path_applied=quiet_applied,
        motivational_quote_removed_on_quiet_path=quote_removed,
        model_respected_quiet_path=not violations,
        violations=tuple(dict.fromkeys(violations)),
    )
    return updated, decision
