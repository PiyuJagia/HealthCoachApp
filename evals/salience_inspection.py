"""F4.6 deterministic salience inspection (B1 / A1 / B3 / C3 / early-pattern)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from analytics.trends import get_health_trends
from app.health_tools import get_health_trends_for_agent
from app.lifestyle_tools import get_lifestyle_context_for_agent
from data.models import HealthDaily
from data.repository import create_user, upsert_health_daily

RESULTS_DIR = Path(__file__).resolve().parent / "results"
INSPECTION_MD = RESULTS_DIR / "f46_salience_inspection_v1.md"
INSPECTION_JSON = RESULTS_DIR / "f46_salience_inspection_v1.json"

SCENARIOS = (
    {"scenario_id": "HC-EVAL-B1", "as_of_date": "2026-06-18", "role": "Low-salience negative control"},
    {"scenario_id": "HC-EVAL-A1", "as_of_date": "2026-08-02", "role": "Large isolated sleep decline"},
    {"scenario_id": "HC-EVAL-B3", "as_of_date": "2026-08-17", "role": "F4.5 maintenance must remain eligible"},
    {"scenario_id": "HC-EVAL-C3", "as_of_date": "2026-06-29", "role": "Lifestyle must not manufacture sleep salience"},
)


def _metric_row(trend) -> dict[str, Any]:
    salience = trend.salience
    long = trend.longitudinal
    return {
        "metric": trend.metric,
        "direction": trend.direction,
        "percent_change": trend.percent_change,
        "absolute_change": trend.absolute_change,
        "data_maturity_state": trend.data_maturity_state,
        "trend_allowed": trend.claim_eligibility.trend_allowed,
        "early_pattern_allowed": trend.claim_eligibility.early_pattern_allowed,
        "baseline_ready": trend.baseline_ready,
        "maintenance_of_gain": long.maintenance_of_gain,
        "maintenance_of_decline": long.maintenance_of_decline,
        "salience": salience.to_dict(),
    }


def inspect_scenario(session, user_id: int, spec: dict[str, str]) -> dict[str, Any]:
    as_of = date.fromisoformat(spec["as_of_date"])
    trends = get_health_trends(session, user_id, as_of_date=as_of)
    payload = get_health_trends_for_agent(user_id, as_of_date=as_of)
    lifestyle = get_lifestyle_context_for_agent(user_id, as_of_date=as_of)
    return {
        "scenario_id": spec["scenario_id"],
        "role": spec["role"],
        "as_of_date": spec["as_of_date"],
        "insight_salience": payload["insight_salience"],
        "metrics": [_metric_row(item) for item in trends],
        "lifestyle_event_count": lifestyle.get("event_count"),
        "lifestyle_inputs": list(lifestyle.get("policy_available_inputs") or []),
    }


def inspect_early_pattern(session) -> dict[str, Any]:
    user = create_user(session, display_name="F46 Early Pattern")
    session.flush()
    start = date(2026, 6, 1)
    for offset in range(12):
        sleep = 7.5 if offset < 5 else 5.4
        hrv = 32.0 if offset < 5 else 24.0
        upsert_health_daily(
            session,
            HealthDaily(
                user_id=user.id,
                date=start + timedelta(days=offset),
                sleep_duration_hours=sleep,
                resting_hr_bpm=70.0,
                hrv_sdnn_ms=hrv,
                exercise_minutes=12.0,
                workout_count=0,
                steps=8000,
                vo2_max=40.0,
            ),
        )
    session.commit()
    as_of = start + timedelta(days=11)
    trends = get_health_trends(session, user.id, as_of_date=as_of)
    payload = get_health_trends_for_agent(user.id, as_of_date=as_of)
    sleep = next(item for item in trends if item.metric == "sleep_duration_hours")
    return {
        "scenario_id": "SYNTHETIC-EARLY-PATTERN",
        "role": "Strong early-pattern observation must not be auto-suppressed",
        "as_of_date": as_of.isoformat(),
        "insight_salience": payload["insight_salience"],
        "sleep": _metric_row(sleep),
    }


def inspect_salience(session, user_id: int) -> dict[str, Any]:
    scenarios = [inspect_scenario(session, user_id, spec) for spec in SCENARIOS]
    early = inspect_early_pattern(session)
    return {"scenarios": scenarios, "early_pattern": early}


def write_salience_inspection_artifacts(report: dict[str, Any]) -> dict[str, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    INSPECTION_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# F4.6 Salience inspection",
        "",
        "Deterministic only. No Gemini. Salience knobs are product surfacing thresholds, not clinical cutoffs.",
        "",
    ]
    for item in report["scenarios"]:
        salience = item["insight_salience"]
        lines.extend(
            [
                f"## {item['scenario_id']} — {item['as_of_date']}",
                "",
                item["role"],
                "",
                f"- insight_worthy: `{salience['insight_worthy']}`",
                f"- recommendation_worthy: `{salience['recommendation_worthy']}`",
                f"- salience_level: `{salience['salience_level']}`",
                f"- primary_metrics: {salience['primary_metrics']}",
                f"- reasons: {salience['reasons']}",
                f"- lifestyle events: {item['lifestyle_event_count']} inputs={item['lifestyle_inputs']}",
                "",
                "| metric | dir | % | abs | maturity | trend_ok | early | maint_gain | level | band | insight_cand | reasons |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for row in item["metrics"]:
            sal = row["salience"]
            lines.append(
                f"| {row['metric']} | {row['direction']} | {row['percent_change']} | "
                f"{row['absolute_change']} | {row['data_maturity_state']} | {row['trend_allowed']} | "
                f"{row['early_pattern_allowed']} | {row['maintenance_of_gain']} | {sal['salience_level']} | "
                f"{sal['magnitude_band']} | {sal['insight_candidate']} | {', '.join(sal['reasons'])} |"
            )
        lines.append("")
    early = report["early_pattern"]
    sleep = early["sleep"]
    lines.extend(
        [
            f"## {early['scenario_id']} — {early['as_of_date']}",
            "",
            early["role"],
            "",
            f"- insight_worthy: `{early['insight_salience']['insight_worthy']}`",
            f"- recommendation_worthy: `{early['insight_salience']['recommendation_worthy']}`",
            f"- sleep maturity: `{sleep['data_maturity_state']}`",
            f"- baseline_ready: `{sleep['baseline_ready']}`",
            f"- trend_allowed: `{sleep['trend_allowed']}`",
            f"- early_pattern_allowed: `{sleep['early_pattern_allowed']}`",
            f"- published direction: `{sleep['direction']}` (F4.1 still blanks established-trend direction)",
            f"- salience band: `{sleep['salience']['magnitude_band']}`",
            f"- insight_candidate: `{sleep['salience']['insight_candidate']}`",
            f"- reasons: {sleep['salience']['reasons']}",
            "",
        ]
    )
    INSPECTION_MD.write_text("\n".join(lines), encoding="utf-8")
    return {"md": INSPECTION_MD, "json": INSPECTION_JSON}
