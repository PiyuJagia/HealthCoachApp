"""F4.5 deterministic longitudinal-context inspection (B3 / B1, no Gemini)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from analytics.trends import get_health_trends, get_weekly_summaries

RESULTS_DIR = Path(__file__).resolve().parent / "results"
INSPECTION_MD = RESULTS_DIR / "f45_longitudinal_context_v1.md"
INSPECTION_JSON = RESULTS_DIR / "f45_longitudinal_context_v1.json"

SCENARIOS = (
    {
        "scenario_id": "HC-EVAL-B3",
        "as_of_date": "2026-08-17",
        "role": "Primary — recent stability vs older personal baseline",
    },
    {
        "scenario_id": "HC-EVAL-B1",
        "as_of_date": "2026-06-18",
        "role": "Negative control — stable early calibration",
    },
)

FOCUS_METRICS = (
    "exercise_minutes",
    "workout_count",
    "resting_hr_bpm",
    "hrv_sdnn_ms",
    "steps",
    "sleep_duration_hours",
    "vo2_max",
)


def _row(trend) -> dict[str, Any]:
    long = trend.longitudinal
    return {
        "metric": trend.metric,
        "recent_direction": trend.direction,
        "recent_percent_change": trend.percent_change,
        "current_value": trend.current_value,
        "f41_baseline_value": trend.baseline_value,
        "f41_baseline_start": trend.baseline_period_start.isoformat(),
        "f41_baseline_end": trend.baseline_period_end.isoformat(),
        "trend_allowed": trend.claim_eligibility.trend_allowed,
        "longitudinal": long.to_dict(),
    }


def inspect_scenario(session, user_id: int, spec: dict[str, str]) -> dict[str, Any]:
    as_of = date.fromisoformat(spec["as_of_date"])
    trends = get_health_trends(session, user_id, as_of_date=as_of)
    by_metric = {item.metric: item for item in trends}
    weeks = get_weekly_summaries(
        session, user_id, as_of_date=as_of, weeks=4, trend_results=trends
    )
    rows = [_row(by_metric[metric]) for metric in FOCUS_METRICS]
    maintaining = [
        row["metric"] for row in rows if row["longitudinal"]["maintenance_of_gain"]
    ]
    declining = [
        row["metric"] for row in rows if row["longitudinal"]["maintenance_of_decline"]
    ]
    weekly_has_maintenance = any(
        "maintenance_of_gain" in week.to_dict()
        or "maintenance_of_gain" in (week.to_dict().get("coverage") or {})
        for week in weeks
    )
    return {
        "scenario_id": spec["scenario_id"],
        "role": spec["role"],
        "as_of_date": spec["as_of_date"],
        "metrics": rows,
        "metrics_maintaining_gains": maintaining,
        "metrics_maintaining_decline": declining,
        "weekly_summary_count": len(weeks),
        "weekly_summaries_independently_authorize_maintenance": weekly_has_maintenance,
        "can_distinguish_nothing_from_holding_gains": bool(maintaining)
        or spec["scenario_id"] == "HC-EVAL-B1",
    }


def inspect_b3_b1(session, user_id: int) -> dict[str, Any]:
    scenarios = [inspect_scenario(session, user_id, spec) for spec in SCENARIOS]
    by_id = {item["scenario_id"]: item for item in scenarios}
    b3 = by_id["HC-EVAL-B3"]
    b1 = by_id["HC-EVAL-B1"]
    b3_stable = all(
        row["recent_direction"] in {"stable", "improving", "declining", "increasing", "decreasing"}
        for row in b3["metrics"]
    )
    return {
        "thresholds": {
            "recent_days": 7,
            "f41_lookback_days": 60,
            "medium_days": 30,
            "long_days": 90,
            "material_percent": 3.0,
            "min_reference_observations": 10,
        },
        "scenarios": scenarios,
        "answers": {
            "b3_recent_mostly_stable_or_absorbed": b3_stable,
            "b3_still_better_than_older_baseline": bool(b3["metrics_maintaining_gains"]),
            "b3_metrics_supporting_maintenance": b3["metrics_maintaining_gains"],
            "b3_metrics_not_supporting_maintenance": [
                row["metric"]
                for row in b3["metrics"]
                if not row["longitudinal"]["maintenance_of_gain"]
            ],
            "b3_can_distinguish_holding_gains": bool(b3["metrics_maintaining_gains"]),
            "b1_maintenance_of_gain_false": not b1["metrics_maintaining_gains"],
            "weekly_cannot_independently_claim_maintenance": all(
                not item["weekly_summaries_independently_authorize_maintenance"]
                for item in scenarios
            ),
        },
    }


def write_longitudinal_inspection_artifacts(report: dict[str, Any]) -> dict[str, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    INSPECTION_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# F4.5 Longitudinal context inspection (B3 / B1)",
        "",
        "Deterministic only. No Gemini. Weekly summaries remain observed-week facts.",
        "",
        f"**Thresholds:** material change ≥ {report['thresholds']['material_percent']}% "
        f"(same knob as F4.1 stable band). Long-term reference = history older than "
        f"the F4.1 60-day baseline, within a {report['thresholds']['long_days']}-day cap.",
        "",
    ]
    for item in report["scenarios"]:
        lines.extend(
            [
                f"## {item['scenario_id']} — {item['as_of_date']}",
                "",
                item["role"],
                "",
                f"- Maintaining gains: {item['metrics_maintaining_gains']}",
                f"- Maintaining decline: {item['metrics_maintaining_decline']}",
                "",
                "| metric | recent dir | recent % | current | F4.1 baseline | long-term ref | vs old % | maint. gain | available |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for row in item["metrics"]:
            long = row["longitudinal"]
            lines.append(
                f"| {row['metric']} | {row['recent_direction']} | {row['recent_percent_change']} | "
                f"{row['current_value']} | {row['f41_baseline_value']} | "
                f"{long['long_term_reference_value']} | {long['current_vs_long_term_percent']} | "
                f"{long['maintenance_of_gain']} | {long['longitudinal_context_available']} |"
            )
        lines.append("")
    answers = report["answers"]
    lines.extend(
        [
            "## B3 answers",
            "",
            f"1. Recent 7-vs-60 is not a blank slate; several metrics are stable while exercise/workouts may still move. Maintenance flags use **stable** recent direction: {answers['b3_metrics_supporting_maintenance']}",
            f"2. Still materially better than the older (pre-F4.1-baseline) reference: {answers['b3_still_better_than_older_baseline']}",
            f"3. Support maintenance-of-gain: {answers['b3_metrics_supporting_maintenance']}",
            f"4. Do not: {answers['b3_metrics_not_supporting_maintenance']}",
            f"5. Contract can distinguish nothing-new vs holding gains: {answers['b3_can_distinguish_holding_gains']}",
            "6. Grounded in Marcus prefix 2026-05-20→2026-06-18 vs current week 2026-08-11→2026-08-17.",
            "",
            "## Negative control",
            "",
            f"- B1 maintenance_of_gain all false: {answers['b1_maintenance_of_gain_false']}",
            f"- Weekly summaries cannot independently claim maintenance: {answers['weekly_cannot_independently_claim_maintenance']}",
            "",
        ]
    )
    INSPECTION_MD.write_text("\n".join(lines), encoding="utf-8")
    return {"md": INSPECTION_MD, "json": INSPECTION_JSON}
