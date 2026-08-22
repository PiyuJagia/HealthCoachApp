"""F4.3 weekly-summary alignment inspection against Marcus seed dates."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from analytics.trends import get_health_trends, get_weekly_summaries
from agent.model_observe import assess_weekly_summary_bypass

RESULTS_DIR = Path(__file__).resolve().parent / "results"
INSPECTION_MD = RESULTS_DIR / "f43_weekly_summary_alignment_v1.md"
INSPECTION_JSON = RESULTS_DIR / "f43_weekly_summary_alignment_v1.json"

SCENARIOS = (
    {"scenario_id": "HC-EVAL-D1", "as_of_date": "2026-07-13", "role": "HRV missing today"},
    {"scenario_id": "HC-EVAL-D2", "as_of_date": "2026-06-10", "role": "Full same-day sync gap"},
    {"scenario_id": "HC-EVAL-A1", "as_of_date": "2026-08-02", "role": "Mature-data control"},
)

FOCUS_METRICS = (
    "sleep_duration_hours",
    "hrv_sdnn_ms",
    "exercise_minutes",
    "workout_count",
    "vo2_max",
)


def inspect_week(session, user_id: int, spec: dict[str, str]) -> dict[str, Any]:
    as_of = date.fromisoformat(spec["as_of_date"])
    trends = {item.metric: item for item in get_health_trends(session, user_id, as_of_date=as_of)}
    week = get_weekly_summaries(
        session, user_id, as_of_date=as_of, weeks=1, trend_results=list(trends.values())
    )[0]
    payload = {
        "trends": [item.to_dict() for item in trends.values()],
        "weekly_summaries": [week.to_dict()],
    }
    rows = []
    inconsistencies = []
    for metric in FOCUS_METRICS:
        coverage = week.coverage[metric]
        trend = trends[metric]
        row = {
            "metric": metric,
            "cadence": coverage.cadence,
            "aggregate_value": coverage.aggregate_value,
            "observed_count": coverage.observation_count,
            "expected_count": coverage.expected_observation_count,
            "missing_count": coverage.missing_count,
            "coverage_ratio": coverage.coverage_ratio,
            "partial_coverage": coverage.partial_coverage,
            "gap_caveat_required": coverage.gap_caveat_required,
            "as_of_date_available": coverage.as_of_date_available,
            "latest_valid_observation_date": (
                coverage.latest_valid_observation_date.isoformat()
                if coverage.latest_valid_observation_date
                else None
            ),
            "summary_value_allowed": coverage.claim_semantics.summary_value_allowed,
            "summary_comparison_allowed": coverage.claim_semantics.summary_comparison_allowed,
            "summary_recommendation_support_allowed": (
                coverage.claim_semantics.summary_recommendation_support_allowed
            ),
            "trend_allowed": trend.claim_eligibility.trend_allowed,
            "trend_recommendation_support_allowed": (
                trend.claim_eligibility.recommendation_support_allowed
            ),
            "trend_gap_caveat_required": trend.gap_caveat_required,
        }
        if row["summary_comparison_allowed"] and not row["trend_allowed"]:
            inconsistencies.append(f"{metric}: comparison without trend_allowed")
        if row["summary_recommendation_support_allowed"] and not row["trend_recommendation_support_allowed"]:
            inconsistencies.append(f"{metric}: weekly rec without trend rec")
        if coverage.cadence != "episodic" and row["gap_caveat_required"] != row["trend_gap_caveat_required"]:
            inconsistencies.append(f"{metric}: gap caveat mismatch")
        rows.append(row)
    bypass = assess_weekly_summary_bypass(payload)
    return {
        "scenario_id": spec["scenario_id"],
        "role": spec["role"],
        "as_of_date": spec["as_of_date"],
        "week_start": week.week_start.isoformat(),
        "week_end": week.week_end.isoformat(),
        "as_of_aligned": week.as_of_aligned,
        "metrics": rows,
        "inconsistencies": inconsistencies,
        "bypass_possible": bypass["bypass_possible"],
        "bypass": bypass,
    }


def inspect_weekly_alignment(session, user_id: int) -> dict[str, Any]:
    scenarios = [inspect_week(session, user_id, spec) for spec in SCENARIOS]
    inconsistencies = [item for scenario in scenarios for item in scenario["inconsistencies"]]
    return {
        "inspection_id": "f43_weekly_summary_alignment_v1",
        "scenarios": scenarios,
        "inconsistency_count": len(inconsistencies),
        "inconsistencies": inconsistencies,
        "bypass_closed": all(not scenario["bypass_possible"] for scenario in scenarios),
        "alignment_safe_to_accept": len(inconsistencies) == 0
        and all(not scenario["bypass_possible"] for scenario in scenarios),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# F4.3 Weekly-summary maturity / coverage alignment",
        "",
        "Weekly summaries describe observed values. Trends authorize directional comparison.",
        "",
        f"**Bypass closed:** {report['bypass_closed']}",
        f"**Alignment safe to accept:** {report['alignment_safe_to_accept']}",
        "",
    ]
    for scenario in report["scenarios"]:
        lines.extend(
            [
                f"## {scenario['scenario_id']} — {scenario['as_of_date']}",
                "",
                f"{scenario['role']}. Week {scenario['week_start']} → {scenario['week_end']}; "
                f"as_of_aligned={scenario['as_of_aligned']}; bypass_possible={scenario['bypass_possible']}",
                "",
                "| metric | cadence | aggregate | n/exp | miss | partial | gap | as_of | value | compare | rec | trend | trend rec |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for row in scenario["metrics"]:
            lines.append(
                "| {metric} | {cadence} | {aggregate} | {n}/{exp} | {miss} | {partial} | {gap} | {as_of} | {value} | {compare} | {rec} | {trend} | {trend_rec} |".format(
                    metric=row["metric"],
                    cadence=row["cadence"],
                    aggregate=row["aggregate_value"],
                    n=row["observed_count"],
                    exp=row["expected_count"],
                    miss=row["missing_count"],
                    partial=row["partial_coverage"],
                    gap=row["gap_caveat_required"],
                    as_of=row["as_of_date_available"],
                    value=row["summary_value_allowed"],
                    compare=row["summary_comparison_allowed"],
                    rec=row["summary_recommendation_support_allowed"],
                    trend=row["trend_allowed"],
                    trend_rec=row["trend_recommendation_support_allowed"],
                )
            )
        lines.append("")
        if scenario["inconsistencies"]:
            lines.extend(f"- {item}" for item in scenario["inconsistencies"])
        else:
            lines.append("Consistency: no weekly/trend contradictions.")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_weekly_inspection_artifacts(report: dict[str, Any], results_dir: Path | None = None) -> dict[str, Path]:
    out_dir = results_dir or RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / INSPECTION_JSON.name
    md_path = out_dir / INSPECTION_MD.name
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "md": md_path}
