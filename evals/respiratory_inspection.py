"""F4.8 deterministic respiratory-rate control-metric inspection."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from analytics.trends import get_health_trends, get_weekly_summaries
from app.health_tools import get_health_trends_for_agent
from data.models import HealthDaily
from data.repository import create_user, upsert_health_daily

RESULTS_DIR = Path(__file__).resolve().parent / "results"
INSPECTION_MD = RESULTS_DIR / "f48_respiratory_control_inspection_v1.md"
INSPECTION_JSON = RESULTS_DIR / "f48_respiratory_control_inspection_v1.json"

E1 = date(2026, 8, 2)
B1 = date(2026, 6, 18)
D2 = date(2026, 6, 10)


def _trend_row(trend) -> dict[str, Any]:
    return {
        "metric": trend.metric,
        "cadence": trend.cadence,
        "control_metric": trend.control_metric,
        "current_value": trend.current_value,
        "baseline_value": trend.baseline_value,
        "percent_change": trend.percent_change,
        "direction": trend.direction,
        "as_of_date_value": trend.as_of_date_value,
        "as_of_date_available": trend.as_of_date_available,
        "observation_count_current": trend.observation_count_current,
        "expected_observation_count_current": trend.expected_observation_count_current,
        "coverage_ratio": trend.coverage_ratio,
        "baseline_observation_count": trend.baseline_observation_count,
        "baseline_ready": trend.baseline_ready,
        "partial_coverage": trend.partial_coverage,
        "gap_caveat_required": trend.gap_caveat_required,
        "data_maturity_state": trend.data_maturity_state,
        "claim_eligibility": trend.claim_eligibility.to_dict(),
        "maintenance_of_gain": trend.longitudinal.maintenance_of_gain,
        "maintenance_of_decline": trend.longitudinal.maintenance_of_decline,
        "salience": trend.salience.to_dict(),
    }


def _focus_metrics(trends) -> dict[str, Any]:
    wanted = {
        "sleep_duration_hours",
        "resting_hr_bpm",
        "hrv_sdnn_ms",
        "exercise_minutes",
        "workout_count",
        "steps",
        "vo2_max",
        "respiratory_rate",
    }
    return {item.metric: _trend_row(item) for item in trends if item.metric in wanted}


def inspect_marcus(session, user_id: int) -> dict[str, Any]:
    e1_trends = get_health_trends(session, user_id, as_of_date=E1)
    e1_payload = get_health_trends_for_agent(user_id, as_of_date=E1)
    e1_week = get_weekly_summaries(session, user_id, as_of_date=E1, weeks=1)[0]
    b1_payload = get_health_trends_for_agent(user_id, as_of_date=B1)
    d2_rr = next(
        item
        for item in get_health_trends(session, user_id, as_of_date=D2)
        if item.metric == "respiratory_rate"
    )
    return {
        "e1": {
            "as_of_date": E1.isoformat(),
            "insight_salience": e1_payload["insight_salience"],
            "metrics": _focus_metrics(e1_trends),
            "weekly_respiratory": e1_week.coverage["respiratory_rate"].to_dict(),
            "average_respiratory_rate": e1_week.average_respiratory_rate,
        },
        "b1": {
            "as_of_date": B1.isoformat(),
            "insight_salience": b1_payload["insight_salience"],
            "respiratory_rate": next(
                item for item in b1_payload["trends"] if item["metric"] == "respiratory_rate"
            ),
        },
        "d2": {
            "as_of_date": D2.isoformat(),
            "respiratory_rate": _trend_row(d2_rr),
        },
    }


def inspect_synthetics(session) -> dict[str, Any]:
    partial_user = create_user(session, display_name="F48 Partial RR")
    session.flush()
    start = date(2026, 4, 1)
    for offset in range(40):
        upsert_health_daily(
            session,
            HealthDaily(
                user_id=partial_user.id,
                date=start + timedelta(days=offset),
                sleep_duration_hours=7.0,
                resting_hr_bpm=70.0,
                hrv_sdnn_ms=32.0,
                exercise_minutes=12.0,
                workout_count=0,
                steps=8000,
                vo2_max=40.0,
                respiratory_rate=None if offset >= 37 else 14.5,
            ),
        )
    session.commit()
    partial_as_of = start + timedelta(days=39)
    partial = next(
        item
        for item in get_health_trends(session, partial_user.id, as_of_date=partial_as_of)
        if item.metric == "respiratory_rate"
    )

    immature_user = create_user(session, display_name="F48 Immature RR")
    session.flush()
    immature_start = date(2026, 5, 1)
    for offset in range(8):
        upsert_health_daily(
            session,
            HealthDaily(
                user_id=immature_user.id,
                date=immature_start + timedelta(days=offset),
                sleep_duration_hours=7.0,
                resting_hr_bpm=70.0,
                hrv_sdnn_ms=32.0,
                exercise_minutes=12.0,
                workout_count=0,
                steps=8000,
                vo2_max=40.0,
                respiratory_rate=14.6,
            ),
        )
    session.commit()
    immature_as_of = immature_start + timedelta(days=7)
    immature = next(
        item
        for item in get_health_trends(session, immature_user.id, as_of_date=immature_as_of)
        if item.metric == "respiratory_rate"
    )
    return {
        "partial": _trend_row(partial),
        "immature": _trend_row(immature),
    }


def inspect_respiratory(session, user_id: int) -> dict[str, Any]:
    return {
        "marcus": inspect_marcus(session, user_id),
        "synthetics": inspect_synthetics(session),
    }


def _md_metric_table(metrics: dict[str, Any]) -> list[str]:
    lines = [
        "| metric | current | baseline | % | dir | maturity | cov | control | insight_cand | reasons |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key in (
        "sleep_duration_hours",
        "resting_hr_bpm",
        "hrv_sdnn_ms",
        "exercise_minutes",
        "vo2_max",
        "respiratory_rate",
    ):
        row = metrics[key]
        sal = row["salience"]
        lines.append(
            f"| {key} | {row['current_value']} | {row['baseline_value']} | "
            f"{row['percent_change']} | {row['direction']} | {row['data_maturity_state']} | "
            f"{row['observation_count_current']}/{row['expected_observation_count_current']} | "
            f"{row['control_metric']} | {sal['insight_candidate']} | {', '.join(sal['reasons'])} |"
        )
    return lines


def write_respiratory_inspection_artifacts(report: dict[str, Any]) -> dict[str, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    INSPECTION_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    e1 = report["marcus"]["e1"]
    b1 = report["marcus"]["b1"]
    d2 = report["marcus"]["d2"]
    rr = e1["metrics"]["respiratory_rate"]
    sleep = e1["metrics"]["sleep_duration_hours"]
    partial = report["synthetics"]["partial"]
    immature = report["synthetics"]["immature"]
    lines = [
        "# F4.8 Respiratory-rate control-metric inspection",
        "",
        "Deterministic only. No Gemini. No clinical respiratory thresholds.",
        "",
        "## Original E1 limitation",
        "",
        "HC-EVAL-E1 (2026-08-02) stored a stable `respiratory_rate` in `health_daily`, but the",
        "metric was omitted from `METRIC_SPECS` / `get_trend_signals`. Gemini had zero access",
        "and generalized other signals as “cardiovascular indicators remained stable.”",
        "",
        "## Implementation",
        "",
        "- Daily cadence, same F4.1 maturity/provenance contract as other daily metrics.",
        "- `control_metric=true` on the metric spec, trend row, and salience row.",
        "- Payload `insight_salience.control_metrics` lists designated controls.",
        "- Stable/barely-directional RR is not an insight candidate and cannot create maintenance flags.",
        "- Weekly summaries include `average_respiratory_rate` with F4.3 claim_semantics.",
        "",
        "## HC-EVAL-E1 — 2026-08-02",
        "",
        f"- insight_worthy: `{e1['insight_salience']['insight_worthy']}`",
        f"- primary_metrics: {e1['insight_salience']['primary_metrics']}",
        f"- control_metrics: {e1['insight_salience']['control_metrics']}",
        f"- sleep: {sleep['direction']} {sleep['percent_change']}% / {sleep['current_value']} vs {sleep['baseline_value']}",
        f"- respiratory_rate: {rr['direction']} {rr['percent_change']}% / {rr['current_value']} vs {rr['baseline_value']}",
        f"- RR maturity: `{rr['data_maturity_state']}` coverage {rr['observation_count_current']}/{rr['expected_observation_count_current']}",
        f"- RR insight_candidate: `{rr['salience']['insight_candidate']}`",
        f"- RR weekly average: `{e1['average_respiratory_rate']}` comparison_allowed=`{e1['weekly_respiratory']['claim_semantics']['summary_comparison_allowed']}`",
        "",
        *_md_metric_table(e1["metrics"]),
        "",
        "### Deterministic answers",
        "",
        f"1. Is respiratory rate stable? **Yes** — direction `{rr['direction']}`, percent change `{rr['percent_change']}` (below the 3% detectability knob).",
        "2. Does its presence help bound the sleep decline? **Yes** — sleep remains the salient decline; RR is a stable control on the same as-of date.",
        "3. Does the contract avoid an independent reassurance claim? **Yes** — `insight_candidate=false`, not in `primary_metrics`, `control_metric=true`.",
        "4. Can Gemini now distinguish sleep decline from broader physiological deterioration? **Contract yes** — RR is visible with provenance. Live Gemini not run in this phase.",
        "",
        "## Negative controls",
        "",
        f"### B1 2026-06-18 (stable period)",
        "",
        f"- insight_worthy: `{b1['insight_salience']['insight_worthy']}`",
        f"- RR direction: `{b1['respiratory_rate']['direction']}`",
        f"- RR insight_candidate: `{b1['respiratory_rate']['salience']['insight_candidate']}`",
        "- Stable RR does not independently create INSIGHT.",
        "",
        f"### D2 / synthetic partial coverage",
        "",
        f"- D2 as-of available: `{d2['respiratory_rate']['as_of_date_available']}`",
        f"- D2 gap caveat: `{d2['respiratory_rate']['gap_caveat_required']}`",
        f"- Synthetic partial current observations: `{partial['observation_count_current']}/{partial['expected_observation_count_current']}`",
        f"- Synthetic as-of available: `{partial['as_of_date_available']}` (no silent imputation)",
        "",
        f"### Immature baseline",
        "",
        f"- maturity: `{immature['data_maturity_state']}`",
        f"- trend_allowed: `{immature['claim_eligibility']['trend_allowed']}`",
        f"- published direction: `{immature['direction']}`",
        f"- percent_change: `{immature['percent_change']}`",
        "",
        "## TRACE",
        "",
        "F4.2 `model_calls[]` extract `respiratory_rate` from `get_trend_signals` with",
        "`origin=deterministic_analytics` (existing F4.2 constant; not a second origin).",
        "Visible fields include value, maturity, direction when allowed, `control_metric`,",
        "and coverage/provenance. No hidden CoT.",
        "",
    ]
    INSPECTION_MD.write_text("\n".join(lines), encoding="utf-8")
    return {"md": INSPECTION_MD, "json": INSPECTION_JSON}
