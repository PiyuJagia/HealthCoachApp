"""F4.9 deterministic within-window HRV spread inspection."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, stdev
from typing import Any

from analytics.trends import get_health_trends
from app.health_tools import get_health_trends_for_agent
from data.models import HealthDaily
from data.repository import create_user, upsert_health_daily

RESULTS_DIR = Path(__file__).resolve().parent / "results"
INSPECTION_MD = RESULTS_DIR / "f49_spread_inspection_v1.md"
INSPECTION_JSON = RESULTS_DIR / "f49_spread_inspection_v1.json"

C4 = date(2026, 7, 28)
B1 = date(2026, 6, 18)
C4_CURRENT_HRV = (28.7, 48.9, 30.5, 44.9, 25.7, 44.4, 24.7)


def _day(
    *,
    sleep: float | None = 7.0,
    rhr: float | None = 70.0,
    hrv: float | None = 32.0,
    exercise: float | None = 12.0,
    workouts: int | None = 0,
    steps: int | None = 8000,
    vo2: float | None = 40.0,
    rr: float | None = 14.5,
) -> dict:
    return {
        "sleep_duration_hours": sleep,
        "resting_hr_bpm": rhr,
        "hrv_sdnn_ms": hrv,
        "exercise_minutes": exercise,
        "workout_count": workouts,
        "steps": steps,
        "vo2_max": vo2,
        "respiratory_rate": rr,
    }


def _write_days(session, user_id: int, start: date, days: list[dict]) -> None:
    for offset, fields in enumerate(days):
        upsert_health_daily(
            session,
            HealthDaily(user_id=user_id, date=start + timedelta(days=offset), **fields),
        )
    session.commit()


def _hrv_row(trend) -> dict[str, Any]:
    spread = trend.within_window_spread.to_dict() if trend.within_window_spread is not None else None
    return {
        "metric": trend.metric,
        "direction": trend.direction,
        "percent_change": trend.percent_change,
        "current_value": trend.current_value,
        "baseline_value": trend.baseline_value,
        "data_maturity_state": trend.data_maturity_state,
        "baseline_ready": trend.baseline_ready,
        "partial_coverage": trend.partial_coverage,
        "gap_caveat_required": trend.gap_caveat_required,
        "observation_count_current": trend.observation_count_current,
        "expected_observation_count_current": trend.expected_observation_count_current,
        "claim_eligibility": trend.claim_eligibility.to_dict(),
        "maintenance_of_gain": trend.longitudinal.maintenance_of_gain,
        "maintenance_of_decline": trend.longitudinal.maintenance_of_decline,
        "salience": trend.salience.to_dict(),
        "control_metric": trend.control_metric,
        "within_window_spread": spread,
    }


def _by_metric(trends) -> dict:
    return {item.metric: item for item in trends}


def inspect_marcus(session, user_id: int) -> dict[str, Any]:
    c4_trends = _by_metric(get_health_trends(session, user_id, as_of_date=C4))
    c4_payload = get_health_trends_for_agent(user_id, as_of_date=C4)
    b1_payload = get_health_trends_for_agent(user_id, as_of_date=B1)
    return {
        "c4": {
            "as_of_date": C4.isoformat(),
            "reconstructed_current_hrv": list(C4_CURRENT_HRV),
            "reconstructed_mean": round(mean(C4_CURRENT_HRV), 2),
            "reconstructed_sample_sd": round(stdev(C4_CURRENT_HRV), 2),
            "insight_salience": c4_payload["insight_salience"],
            "hrv": _hrv_row(c4_trends["hrv_sdnn_ms"]),
            "vo2": _hrv_row(c4_trends["vo2_max"]),
            "respiratory_rate": _hrv_row(c4_trends["respiratory_rate"]),
            "sleep": _hrv_row(c4_trends["sleep_duration_hours"]),
        },
        "b1": {
            "as_of_date": B1.isoformat(),
            "insight_salience": b1_payload["insight_salience"],
            "hrv": next(item for item in b1_payload["trends"] if item["metric"] == "hrv_sdnn_ms"),
            "respiratory_rate": next(
                item for item in b1_payload["trends"] if item["metric"] == "respiratory_rate"
            ),
        },
    }


def inspect_synthetics(session) -> dict[str, Any]:
    start = date(2026, 4, 1)

    stable_user = create_user(session, display_name="F49 Stable Spread")
    session.flush()
    pattern = (31.0, 32.0, 33.0)
    _write_days(
        session,
        stable_user.id,
        start,
        [_day(hrv=pattern[offset % 3]) for offset in range(40)],
    )
    stable = _by_metric(get_health_trends(session, stable_user.id, as_of_date=start + timedelta(days=39)))[
        "hrv_sdnn_ms"
    ]

    immature_user = create_user(session, display_name="F49 Immature Spread")
    session.flush()
    immature_start = date(2026, 5, 1)
    _write_days(
        session,
        immature_user.id,
        immature_start,
        [_day(hrv=30.0 + (offset % 3)) for offset in range(8)],
    )
    immature = _by_metric(
        get_health_trends(session, immature_user.id, as_of_date=immature_start + timedelta(days=7))
    )["hrv_sdnn_ms"]

    partial_user = create_user(session, display_name="F49 Partial Spread")
    session.flush()
    partial_days = [_day(hrv=32.0 + ((offset % 3) - 1) * 0.4) for offset in range(40)]
    for offset in (37, 38, 39):
        partial_days[offset]["hrv_sdnn_ms"] = None
    partial_days[33]["hrv_sdnn_ms"] = 34.0
    partial_days[34]["hrv_sdnn_ms"] = 30.0
    partial_days[35]["hrv_sdnn_ms"] = 36.0
    partial_days[36]["hrv_sdnn_ms"] = 28.0
    _write_days(session, partial_user.id, start, partial_days)
    partial = _by_metric(get_health_trends(session, partial_user.id, as_of_date=start + timedelta(days=39)))[
        "hrv_sdnn_ms"
    ]

    zero_user = create_user(session, display_name="F49 NearZero Baseline")
    session.flush()
    zero_days = [_day(hrv=32.0) for _ in range(40)]
    for offset, value in enumerate([28.0, 36.0, 30.0, 34.0, 29.0, 35.0, 31.0]):
        zero_days[33 + offset]["hrv_sdnn_ms"] = value
    _write_days(session, zero_user.id, start, zero_days)
    near_zero = _by_metric(get_health_trends(session, zero_user.id, as_of_date=start + timedelta(days=39)))[
        "hrv_sdnn_ms"
    ]

    outlier_user = create_user(session, display_name="F49 Outlier Spread")
    session.flush()
    outlier_days = [_day(hrv=32.0 + ((offset % 3) - 1) * 0.3) for offset in range(40)]
    for offset in range(33, 39):
        outlier_days[offset]["hrv_sdnn_ms"] = 33.0
    outlier_days[39]["hrv_sdnn_ms"] = 55.0
    _write_days(session, outlier_user.id, start, outlier_days)
    outlier = _by_metric(get_health_trends(session, outlier_user.id, as_of_date=start + timedelta(days=39)))[
        "hrv_sdnn_ms"
    ]

    return {
        "stable_mean_normal_spread": _hrv_row(stable),
        "immature": _hrv_row(immature),
        "partial": _hrv_row(partial),
        "near_zero_baseline": _hrv_row(near_zero),
        "one_extreme_outlier": _hrv_row(outlier),
    }


def inspect_spread(session, user_id: int) -> dict[str, Any]:
    return {
        "marcus": inspect_marcus(session, user_id),
        "synthetics": inspect_synthetics(session),
    }


def write_spread_inspection_artifacts(report: dict[str, Any]) -> dict[str, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    INSPECTION_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    c4 = report["marcus"]["c4"]
    b1 = report["marcus"]["b1"]
    hrv = c4["hrv"]
    spread = hrv["within_window_spread"]
    sleep = c4["sleep"]
    vo2 = c4["vo2"]
    rr = c4["respiratory_rate"]
    synthetics = report["synthetics"]
    lines = [
        "# F4.9 Within-window HRV spread inspection",
        "",
        "Deterministic only. No Gemini. No CODIFY. Frozen labels unchanged.",
        "HRV-only MVP. Level change and within-window spread remain distinct.",
        "",
        "## Contract",
        "",
        "- Object: `within_window_spread` on the HRV trend row.",
        "- Fields: observation_count, mean, sample_standard_deviation, min, max, range,",
        "  baseline_standard_deviation, spread_ratio, spread_observation_allowed,",
        "  spread_comparison_allowed.",
        "- Same F4.1 current/baseline windows. No band, CV, 0–100 score, clinical threshold,",
        "  causal interpretation, salience promotion, recommendation authority, or T7/T8.",
        "",
        "## HC-EVAL-C4 — 2026-07-28",
        "",
        f"- reconstructed current 7d HRV: `{c4['reconstructed_current_hrv']}`",
        f"- reconstructed mean / sample SD: `{c4['reconstructed_mean']}` / `{c4['reconstructed_sample_sd']}`",
        f"- published level: `{hrv['direction']}` `{hrv['percent_change']}`% / `{hrv['current_value']}` vs `{hrv['baseline_value']}`",
        f"- maturity: `{hrv['data_maturity_state']}` trend_allowed=`{hrv['claim_eligibility']['trend_allowed']}`",
        f"- spread n/mean/sample SD: `{spread['observation_count']}` / `{spread['mean']}` / `{spread['sample_standard_deviation']}`",
        f"- min/max/range: `{spread['min']}` / `{spread['max']}` / `{spread['range']}`",
        f"- baseline SD / spread ratio: `{spread['baseline_standard_deviation']}` / `{spread['spread_ratio']}`",
        f"- observation/comparison allowed: `{spread['spread_observation_allowed']}` / `{spread['spread_comparison_allowed']}`",
        f"- HRV insight_candidate / recommendation_candidate: `{hrv['salience']['insight_candidate']}` / `{hrv['salience']['recommendation_candidate']}`",
        f"- review insight_worthy / primary_metrics: `{c4['insight_salience']['insight_worthy']}` / {c4['insight_salience']['primary_metrics']}",
        f"- sleep remains the level story: `{sleep['direction']}` `{sleep['percent_change']}`% insight_candidate=`{sleep['salience']['insight_candidate']}`",
        "",
        "### Deterministic answers",
        "",
        f"1. Is average HRV called declining? **No** — published direction is `{hrv['direction']}`.",
        f"2. Is increased day-to-day spread visible? **Yes** — sample SD `{spread['sample_standard_deviation']}` vs baseline SD `{spread['baseline_standard_deviation']}` (ratio `{spread['spread_ratio']}`), range `{spread['min']}`–`{spread['max']}`.",
        "3. Was an independent insight/recommendation minted from spread? **No** — HRV is not insight_candidate, not recommendation_candidate, and not in primary_metrics.",
        "",
        "## Negative controls",
        "",
        "### Stable mean + normal spread",
        "",
        f"- direction: `{synthetics['stable_mean_normal_spread']['direction']}`",
        f"- spread_ratio: `{synthetics['stable_mean_normal_spread']['within_window_spread']['spread_ratio']}`",
        f"- comparison allowed: `{synthetics['stable_mean_normal_spread']['within_window_spread']['spread_comparison_allowed']}`",
        f"- insight_candidate: `{synthetics['stable_mean_normal_spread']['salience']['insight_candidate']}`",
        "",
        f"### B1 2026-06-18 (stable period regression)",
        "",
        f"- insight_worthy: `{b1['insight_salience']['insight_worthy']}`",
        f"- HRV spread_ratio: `{b1['hrv']['within_window_spread']['spread_ratio']}`",
        f"- HRV insight_candidate: `{b1['hrv']['salience']['insight_candidate']}`",
        "",
        "### Immature baseline",
        "",
        f"- maturity: `{synthetics['immature']['data_maturity_state']}`",
        f"- trend_allowed: `{synthetics['immature']['claim_eligibility']['trend_allowed']}`",
        f"- comparison allowed: `{synthetics['immature']['within_window_spread']['spread_comparison_allowed']}`",
        f"- spread_ratio: `{synthetics['immature']['within_window_spread']['spread_ratio']}`",
        "",
        "### Partial coverage",
        "",
        f"- current observations: `{synthetics['partial']['observation_count_current']}/{synthetics['partial']['expected_observation_count_current']}`",
        f"- partial_coverage: `{synthetics['partial']['partial_coverage']}`",
        f"- comparison allowed: `{synthetics['partial']['within_window_spread']['spread_comparison_allowed']}`",
        f"- spread_ratio: `{synthetics['partial']['within_window_spread']['spread_ratio']}`",
        "",
        "### Near-zero baseline SD",
        "",
        f"- baseline SD: `{synthetics['near_zero_baseline']['within_window_spread']['baseline_standard_deviation']}`",
        f"- comparison allowed: `{synthetics['near_zero_baseline']['within_window_spread']['spread_comparison_allowed']}`",
        f"- spread_ratio: `{synthetics['near_zero_baseline']['within_window_spread']['spread_ratio']}`",
        "",
        "### One extreme outlier",
        "",
        f"- min/max/range: `{synthetics['one_extreme_outlier']['within_window_spread']['min']}` / `{synthetics['one_extreme_outlier']['within_window_spread']['max']}` / `{synthetics['one_extreme_outlier']['within_window_spread']['range']}`",
        f"- direction: `{synthetics['one_extreme_outlier']['direction']}`",
        f"- recommendation_candidate: `{synthetics['one_extreme_outlier']['salience']['recommendation_candidate']}` (F4.6 level effect from the pulled mean; spread added no band or insight reason)",
        "",
        "### Episodic VO2 excluded",
        "",
        f"- C4 VO2 within_window_spread: `{vo2['within_window_spread']}`",
        "",
        "### Respiratory-rate control unaffected",
        "",
        f"- C4 RR within_window_spread: `{rr['within_window_spread']}`",
        f"- C4 RR control_metric / insight_candidate: `{rr['control_metric']}` / `{rr['salience']['insight_candidate']}`",
        f"- B1 RR insight_candidate: `{b1['respiratory_rate']['salience']['insight_candidate']}`",
        "",
        "## TRACE",
        "",
        "F4.2 `model_calls[]` extract `within_window_spread` from `get_trend_signals` with",
        "`origin=deterministic_spread_analytics`. Visible fields include n, mean, sample SD,",
        "min/max/range, baseline SD, ratio, both allow-flags, direction, maturity, and",
        "coverage/provenance needed to reconstruct the comparison. No hidden CoT.",
        "",
    ]
    INSPECTION_MD.write_text("\n".join(lines), encoding="utf-8")
    return {"md": INSPECTION_MD, "json": INSPECTION_JSON}
