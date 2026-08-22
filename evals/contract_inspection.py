"""F4.1.1 deterministic contract inspection against Marcus seed dates."""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from analytics.maturity import (
    BASELINE_LOOKBACK_DAYS,
    CADENCE_EPISODIC,
    CURRENT_WINDOW_DAYS,
    METRIC_SPECS,
)
from analytics.trends import get_health_trends, get_weekly_summaries
from data.repository import list_health_daily_for_user

RESULTS_DIR = Path(__file__).resolve().parent / "results"
INSPECTION_JSON = RESULTS_DIR / "f41_contract_inspection_v1.json"
INSPECTION_CSV = RESULTS_DIR / "f41_contract_inspection_v1.csv"
INSPECTION_MD = RESULTS_DIR / "f41_contract_inspection_v1.md"

INSPECTION_SCENARIOS: tuple[dict[str, str], ...] = (
    {
        "scenario_id": "HC-EVAL-D1",
        "role": "HRV missing on as-of date; recent history exists",
        "as_of_date": "2026-07-13",
    },
    {
        "scenario_id": "HC-EVAL-D2",
        "role": "Full same-day wearable sync gap; recent history exists",
        "as_of_date": "2026-06-10",
    },
    {
        "scenario_id": "HC-EVAL-D3",
        "role": "Shorter history that failed the old 15-in-30 rule",
        "as_of_date": "2026-06-08",
    },
    {
        "scenario_id": "HC-EVAL-A1",
        "role": "Mature-data control — clear sleep deterioration",
        "as_of_date": "2026-08-02",
    },
)

DIRECTIONAL = {"improving", "declining", "increasing", "decreasing"}

CSV_FIELDS = (
    "scenario_id",
    "metric",
    "cadence",
    "as_of_date_value",
    "as_of_date_available",
    "observation_count_current",
    "expected_observation_count_current",
    "raw_current_count",
    "coverage_ratio",
    "baseline_observation_count",
    "raw_baseline_count",
    "baseline_ready",
    "latest_valid_observation_date",
    "latest_valid_observation_value",
    "partial_coverage",
    "gap_caveat_required",
    "data_maturity_state",
    "direction",
    "percent_change",
    "snapshot_allowed",
    "early_pattern_allowed",
    "trend_allowed",
    "recommendation_support_allowed",
    "recommendation_basis",
)


def _window_bounds(as_of: date) -> tuple[date, date, date, date]:
    current_end = as_of
    current_start = current_end - timedelta(days=CURRENT_WINDOW_DAYS - 1)
    baseline_end = current_start - timedelta(days=1)
    baseline_start = current_end - timedelta(days=BASELINE_LOOKBACK_DAYS - 1)
    if baseline_start > baseline_end:
        baseline_start = baseline_end
    return current_start, current_end, baseline_start, baseline_end


def _raw_counts(records: list, field_name: str, start: date, end: date) -> int:
    count = 0
    for record in records:
        if start <= record.date <= end and getattr(record, field_name) is not None:
            count += 1
    return count


def _contradictions(trend_payload: dict[str, Any], raw_current: int, raw_baseline: int) -> list[str]:
    issues: list[str] = []
    metric = trend_payload["metric"]
    eligibility = trend_payload["claim_eligibility"]
    if not eligibility["trend_allowed"] and trend_payload["direction"] in DIRECTIONAL:
        issues.append(f"{metric}: trend_allowed=false but direction={trend_payload['direction']}")
    if not eligibility["trend_allowed"] and trend_payload["percent_change"] is not None:
        issues.append(f"{metric}: trend_allowed=false but percent_change exposed")
    if not trend_payload["baseline_ready"] and eligibility["trend_allowed"]:
        issues.append(f"{metric}: baseline_ready=false but trend_allowed=true")
    if not trend_payload["as_of_date_available"] and trend_payload["as_of_date_value"] is not None:
        issues.append(f"{metric}: as_of_date_available=false but as_of_date_value populated")
    if trend_payload["as_of_date_available"] and trend_payload["as_of_date_value"] is None:
        issues.append(f"{metric}: as_of_date_available=true but as_of_date_value is null")
    if trend_payload["observation_count_current"] != raw_current:
        issues.append(
            f"{metric}: current count {trend_payload['observation_count_current']} != raw {raw_current}"
        )
    if trend_payload["baseline_observation_count"] != raw_baseline:
        issues.append(
            f"{metric}: baseline count {trend_payload['baseline_observation_count']} != raw {raw_baseline}"
        )
    if trend_payload["cadence"] == CADENCE_EPISODIC and trend_payload["gap_caveat_required"]:
        issues.append(f"{metric}: episodic cadence should not set gap_caveat_required")
    if (
        eligibility["recommendation_support_allowed"]
        and eligibility["recommendation_basis"] == "none"
    ):
        issues.append(f"{metric}: recommendation allowed with basis=none")
    if trend_payload["data_maturity_state"] == "ESTABLISHED_TREND" and not eligibility["trend_allowed"]:
        issues.append(f"{metric}: ESTABLISHED_TREND but trend_allowed=false")
    if trend_payload["data_maturity_state"] == "NO_USABLE_DATA" and eligibility["snapshot_allowed"]:
        issues.append(f"{metric}: NO_USABLE_DATA but snapshot_allowed=true")
    return issues


def inspect_as_of(session, user_id: int, spec: dict[str, str]) -> dict[str, Any]:
    as_of = date.fromisoformat(spec["as_of_date"])
    current_start, current_end, baseline_start, baseline_end = _window_bounds(as_of)
    records = list_health_daily_for_user(
        session, user_id, start_date=baseline_start, end_date=current_end
    )
    trends = get_health_trends(session, user_id, as_of_date=as_of)
    weekly = get_weekly_summaries(session, user_id, as_of_date=as_of, weeks=1)
    latest_week = weekly[-1] if weekly else None
    daily_like = [trend for trend in trends if trend.cadence != CADENCE_EPISODIC]
    payload_flags = {
        "gap_caveat_required": any(trend.gap_caveat_required for trend in daily_like),
        "as_of_any_daily_metric_available": any(trend.as_of_date_available for trend in daily_like),
        "data_sufficient_present": any("data_sufficient" in trend.to_dict() for trend in trends),
    }

    metric_rows: list[dict[str, Any]] = []
    issues: list[str] = []
    for trend in trends:
        spec_row = next(item for item in METRIC_SPECS if item.metric == trend.metric)
        raw_current = _raw_counts(records, spec_row.field_name, current_start, current_end)
        raw_baseline = _raw_counts(records, spec_row.field_name, baseline_start, baseline_end)
        row = trend.to_dict()
        row["raw_current_count"] = raw_current
        row["raw_baseline_count"] = raw_baseline
        issues.extend(_contradictions(row, raw_current, raw_baseline))
        metric_rows.append(row)

    weekly_bypass: list[str] = []
    if latest_week is not None:
        for metric, coverage in latest_week.coverage.items():
            semantics = coverage.claim_semantics
            trend_row = next((row for row in metric_rows if row["metric"] == metric), None)
            trend_allowed = bool((trend_row or {}).get("claim_eligibility", {}).get("trend_allowed"))
            rec_allowed = bool(
                (trend_row or {}).get("claim_eligibility", {}).get("recommendation_support_allowed")
            )
            if semantics.summary_comparison_allowed and not trend_allowed:
                weekly_bypass.append(f"{metric}: weekly comparison allowed while trend_allowed=false")
            if semantics.summary_recommendation_support_allowed and not rec_allowed:
                weekly_bypass.append(
                    f"{metric}: weekly recommendation support allowed while trend rec=false"
                )
            if coverage.observation_count == 0 and coverage.aggregate_value is not None:
                weekly_bypass.append(f"{metric}: aggregate present with zero observations")

    vo2 = next(row for row in metric_rows if row["metric"] == "vo2_max")
    return {
        "scenario_id": spec["scenario_id"],
        "role": spec["role"],
        "as_of_date": spec["as_of_date"],
        "windows": {
            "current_start": current_start.isoformat(),
            "current_end": current_end.isoformat(),
            "baseline_start": baseline_start.isoformat(),
            "baseline_end": baseline_end.isoformat(),
        },
        "payload": payload_flags,
        "metrics": metric_rows,
        "weekly_latest": latest_week.to_dict() if latest_week is not None else None,
        "contradictions": issues,
        "weekly_bypass_notes": weekly_bypass,
        "vo2": {
            "cadence": vo2["cadence"],
            "expected_observation_count_current": vo2["expected_observation_count_current"],
            "observation_count_current": vo2["observation_count_current"],
            "coverage_ratio": vo2["coverage_ratio"],
            "gap_caveat_required": vo2["gap_caveat_required"],
            "as_of_date_available": vo2["as_of_date_available"],
            "data_maturity_state": vo2["data_maturity_state"],
        },
    }


def inspect_selected_scenarios(session, user_id: int) -> dict[str, Any]:
    scenarios = [inspect_as_of(session, user_id, spec) for spec in INSPECTION_SCENARIOS]
    all_issues = [issue for item in scenarios for issue in item["contradictions"]]
    answers = _answers(scenarios)
    return {
        "inspection_id": "f41_contract_inspection_v1",
        "scenarios": scenarios,
        "contradiction_count": len(all_issues),
        "contradictions": all_issues,
        "answers": answers,
        "foundation_safe_to_accept": len(all_issues) == 0
        and answers["d1_hrv_trend_with_missing_today"]
        and answers["d2_history_with_sync_gap"]
        and answers["d3_not_blocked_by_old_rule"]
        and answers["a1_mature_control_normal"],
    }


def _answers(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {item["scenario_id"]: item for item in scenarios}
    d1_hrv = next(row for row in by_id["HC-EVAL-D1"]["metrics"] if row["metric"] == "hrv_sdnn_ms")
    d2 = by_id["HC-EVAL-D2"]
    d3_sleep = next(
        row for row in by_id["HC-EVAL-D3"]["metrics"] if row["metric"] == "sleep_duration_hours"
    )
    a1_sleep = next(
        row for row in by_id["HC-EVAL-A1"]["metrics"] if row["metric"] == "sleep_duration_hours"
    )
    return {
        "d1_hrv_trend_with_missing_today": (
            d1_hrv["as_of_date_available"] is False
            and d1_hrv["gap_caveat_required"] is True
            and d1_hrv["claim_eligibility"]["trend_allowed"] is True
            and d1_hrv["observation_count_current"] >= 3
        ),
        "d2_history_with_sync_gap": (
            d2["payload"]["gap_caveat_required"] is True
            and d2["payload"]["as_of_any_daily_metric_available"] is False
            and all(
                row["claim_eligibility"]["trend_allowed"]
                for row in d2["metrics"]
                if row["cadence"] != CADENCE_EPISODIC
            )
        ),
        "d3_not_blocked_by_old_rule": (
            d3_sleep["baseline_observation_count"] >= 10
            and d3_sleep["baseline_observation_count"] < 15
            and d3_sleep["claim_eligibility"]["trend_allowed"] is True
        ),
        "a1_mature_control_normal": (
            a1_sleep["claim_eligibility"]["trend_allowed"] is True
            and a1_sleep["direction"] in {"decreasing", "declining"}
            and a1_sleep["as_of_date_available"] is True
            and a1_sleep["gap_caveat_required"] is False
        ),
    }


def _md_bool(value: bool) -> str:
    return "true" if value else "false"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# F4.1.1 Deterministic contract inspection",
        "",
        "Inspection only. No Gemini. Canonical Marcus seed dates.",
        "",
        f"**Contradiction count:** {report['contradiction_count']}",
        f"**Foundation safe to accept:** {report['foundation_safe_to_accept']}",
        "",
        "## Answers",
        "",
        f"1. D1 preserves recent HRV trend while marking today missing: **{report['answers']['d1_hrv_trend_with_missing_today']}**",
        f"2. D2 preserves history while identifying the same-day sync gap: **{report['answers']['d2_history_with_sync_gap']}**",
        f"3. D3 allows trend reasoning (10 valid days, not 15-in-30): **{report['answers']['d3_not_blocked_by_old_rule']}**",
        f"4. A1 mature-data control behaves normally: **{report['answers']['a1_mature_control_normal']}**",
        "",
    ]
    for scenario in report["scenarios"]:
        lines.extend(
            [
                f"## {scenario['scenario_id']} — {scenario['as_of_date']}",
                "",
                scenario["role"],
                "",
                f"Payload: gap_caveat_required={scenario['payload']['gap_caveat_required']}; "
                f"as_of_any_daily_metric_available={scenario['payload']['as_of_any_daily_metric_available']}; "
                f"data_sufficient_present={scenario['payload']['data_sufficient_present']}",
                "",
                "| metric | cadence | as_of_value | as_of_avail | n_cur/exp | cov | n_base | ready | latest | partial | gap | state | dir | pct | snap/early/trend | rec | basis |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for row in scenario["metrics"]:
            elig = row["claim_eligibility"]
            latest = row["latest_valid_observation_date"] or "—"
            latest_val = row["latest_valid_observation_value"]
            latest_cell = f"{latest} / {latest_val}"
            lines.append(
                "| {metric} | {cadence} | {as_of_date_value} | {as_of} | {n_cur}/{n_exp} | {cov} | {n_base} | {ready} | {latest} | {partial} | {gap} | {state} | {direction} | {pct} | {snap}/{early}/{trend} | {rec} | {basis} |".format(
                    metric=row["metric"],
                    cadence=row["cadence"],
                    as_of_date_value=row["as_of_date_value"],
                    as_of=_md_bool(row["as_of_date_available"]),
                    n_cur=row["observation_count_current"],
                    n_exp=row["expected_observation_count_current"],
                    cov=row["coverage_ratio"],
                    n_base=row["baseline_observation_count"],
                    ready=_md_bool(row["baseline_ready"]),
                    latest=latest_cell,
                    partial=_md_bool(row["partial_coverage"]),
                    gap=_md_bool(row["gap_caveat_required"]),
                    state=row["data_maturity_state"],
                    direction=row["direction"],
                    pct=row["percent_change"],
                    snap=_md_bool(elig["snapshot_allowed"]),
                    early=_md_bool(elig["early_pattern_allowed"]),
                    trend=_md_bool(elig["trend_allowed"]),
                    rec=_md_bool(elig["recommendation_support_allowed"]),
                    basis=elig["recommendation_basis"],
                )
            )
        lines.append("")
        if scenario["contradictions"]:
            lines.append("Contradictions:")
            lines.extend(f"- {item}" for item in scenario["contradictions"])
        else:
            lines.append("Contradictions: none.")
        lines.append("")
        lines.append("Weekly-summary notes:")
        lines.extend(f"- {note}" for note in scenario["weekly_bypass_notes"] or ["none"])
        lines.append("")
        vo2 = scenario["vo2"]
        lines.append(
            f"VO2: cadence={vo2['cadence']}; expected={vo2['expected_observation_count_current']}; "
            f"n_cur={vo2['observation_count_current']}; coverage={vo2['coverage_ratio']}; "
            f"as_of={vo2['as_of_date_available']}; gap={vo2['gap_caveat_required']}; "
            f"state={vo2['data_maturity_state']}"
        )
        lines.append("")
    return "\n".join(lines) + "\n"


def write_inspection_artifacts(report: dict[str, Any], results_dir: Path | None = None) -> dict[str, Path]:
    out_dir = results_dir or RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / INSPECTION_JSON.name
    csv_path = out_dir / INSPECTION_CSV.name
    md_path = out_dir / INSPECTION_MD.name
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_FIELDS))
        writer.writeheader()
        for scenario in report["scenarios"]:
            for row in scenario["metrics"]:
                elig = row["claim_eligibility"]
                writer.writerow(
                    {
                        "scenario_id": scenario["scenario_id"],
                        "metric": row["metric"],
                        "cadence": row["cadence"],
                        "as_of_date_value": row["as_of_date_value"],
                        "as_of_date_available": row["as_of_date_available"],
                        "observation_count_current": row["observation_count_current"],
                        "expected_observation_count_current": row["expected_observation_count_current"],
                        "raw_current_count": row["raw_current_count"],
                        "coverage_ratio": row["coverage_ratio"],
                        "baseline_observation_count": row["baseline_observation_count"],
                        "raw_baseline_count": row["raw_baseline_count"],
                        "baseline_ready": row["baseline_ready"],
                        "latest_valid_observation_date": row["latest_valid_observation_date"],
                        "latest_valid_observation_value": row["latest_valid_observation_value"],
                        "partial_coverage": row["partial_coverage"],
                        "gap_caveat_required": row["gap_caveat_required"],
                        "data_maturity_state": row["data_maturity_state"],
                        "direction": row["direction"],
                        "percent_change": row["percent_change"],
                        "snapshot_allowed": elig["snapshot_allowed"],
                        "early_pattern_allowed": elig["early_pattern_allowed"],
                        "trend_allowed": elig["trend_allowed"],
                        "recommendation_support_allowed": elig["recommendation_support_allowed"],
                        "recommendation_basis": elig["recommendation_basis"],
                    }
                )
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "md": md_path}
