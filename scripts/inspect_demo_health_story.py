"""Print the synthetic 3-phase demo health story and trend checkpoints."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from statistics import mean, pstdev

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analytics.trends import get_health_trends
from app.health_tools import get_health_trends_for_agent
from data.database import get_database_url, get_session_factory
from data.demo_seed import (
    CHECKPOINT_DAY_30_INDEX,
    CHECKPOINT_DAY_60_INDEX,
    CHECKPOINT_DAY_75_INDEX,
    CHECKPOINT_DAY_90_INDEX,
    DEMO_DAY_COUNT,
    DEMO_DISPLAY_NAME,
    DEMO_END_DATE,
    DEMO_GOAL,
    FULL_SYNC_GAP_DAYS,
    HRV_MISSING_DAYS,
    INCOMPLETE_SLEEP_DAYS,
    PHASE1_END_INDEX,
    PHASE2_END_INDEX,
    PHASE3_DISRUPTION_END_INDEX,
    PHASE3_DISRUPTION_START_INDEX,
    PHASE3_RECOVERY_START_INDEX,
    VO2_MISSING_DAYS,
    checkpoint_date,
    demo_start_date,
    seed_demo_health_data,
)


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(mean(values), 2)


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return round(pstdev(values), 2)


def _phase_slice(records, start: int, end: int):
    return records[start : end + 1]


def _summarize_phase(name: str, records) -> None:
    sleep = [r.sleep_duration_hours for r in records if r.sleep_duration_hours is not None]
    rhr = [r.resting_hr_bpm for r in records if r.resting_hr_bpm is not None]
    hrv = [r.hrv_sdnn_ms for r in records if r.hrv_sdnn_ms is not None]
    exercise = [r.exercise_minutes for r in records if r.exercise_minutes is not None]
    vo2 = [r.vo2_max for r in records if r.vo2_max is not None]
    resp = [r.respiratory_rate for r in records if r.respiratory_rate is not None]
    workouts = sum(r.workout_count or 0 for r in records)

    print(f"  {name}:")
    print(f"    days: {len(records)} | workouts: {workouts}")
    print(
        f"    avg sleep: {_avg(sleep)} | avg RHR: {_avg(rhr)} | avg HRV: {_avg(hrv)} | HRV stdev: {_std(hrv)}"
    )
    print(f"    avg exercise: {_avg(exercise)} | avg VO2: {_avg(vo2)} | avg resp rate: {_avg(resp)}")


def _print_trend_checkpoint(session, user_id: int, day_index: int, label: str) -> None:
    as_of = checkpoint_date(day_index)
    print(f"\n--- Trend checkpoint {label} ({as_of.isoformat()}) ---")
    trends = get_health_trends(session, user_id, as_of_date=as_of)
    for trend in trends:
        print(
            f"  {trend.metric:24} current={trend.current_value} baseline={trend.baseline_value} "
            f"change={trend.absolute_change} pct={trend.percent_change} dir={trend.direction} "
            f"state={trend.data_maturity_state} as_of={trend.as_of_date_available} "
            f"trend_allowed={trend.claim_eligibility.trend_allowed}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect synthetic demo health story.")
    parser.add_argument("--reset", action="store_true", help="Drop and reseed demo data before inspection.")
    return parser


def main() -> None:
    _configure_stdout()
    load_dotenv(PROJECT_ROOT / ".env")
    args = build_parser().parse_args()

    session_factory = get_session_factory()
    with session_factory() as session:
        if args.reset:
            user = seed_demo_health_data(session, reset=True)
            user_id = user.id
        else:
            from data.repository import get_user, list_health_daily_for_user

            user = get_user(session, 1)
            if user is None:
                user = seed_demo_health_data(session, reset=True)
            user_id = user.id
            daily = list_health_daily_for_user(session, user_id)
            if len(daily) < DEMO_DAY_COUNT:
                user = seed_demo_health_data(session, reset=True)
                user_id = user.id

        from data.repository import list_health_daily_for_user, list_lifestyle_events_for_user

        daily = list_health_daily_for_user(session, user_id)
        events = list_lifestyle_events_for_user(session, user_id)

        start = demo_start_date()
        print("Synthetic Demo Health Story Inspection")
        print("=" * 72)
        print(f"database_url: {get_database_url()}")
        print("data_label: synthetic demo data — not clinical reference data")
        print(f"user: {DEMO_DISPLAY_NAME} | goal: {DEMO_GOAL}")
        print(f"date_range: {start.isoformat()} -> {DEMO_END_DATE.isoformat()} ({len(daily)} daily rows)")
        print()
        print("Phase boundaries (1-based days): 1-30 | 31-60 | 61-75 disruption | 76-90 recovery")

        phase1 = _phase_slice(daily, 0, PHASE1_END_INDEX)
        phase2 = _phase_slice(daily, PHASE1_END_INDEX + 1, PHASE2_END_INDEX)
        phase3_disruption = _phase_slice(daily, PHASE3_DISRUPTION_START_INDEX, PHASE3_DISRUPTION_END_INDEX)
        phase3_recovery = _phase_slice(daily, PHASE3_RECOVERY_START_INDEX, DEMO_DAY_COUNT - 1)

        print()
        print("Phase summaries:")
        _summarize_phase("Phase 1 — baseline / calibration", phase1)
        _summarize_phase("Phase 2 — exercise consistency", phase2)
        _summarize_phase("Phase 3 — disruption", phase3_disruption)
        _summarize_phase("Phase 3 — recovery", phase3_recovery)

        caffeine = [e for e in events if e.event_type == "caffeine"]
        alcohol = [e for e in events if e.event_type == "alcohol"]
        mood = [e for e in events if e.event_type == "mood"]
        disruption_start = checkpoint_date(PHASE3_DISRUPTION_START_INDEX)
        disruption_end = checkpoint_date(PHASE3_DISRUPTION_END_INDEX)
        caffeine_in_disruption = [
            e for e in caffeine if disruption_start <= e.occurred_at.date() <= disruption_end
        ]
        caffeine_outside = len(caffeine) - len(caffeine_in_disruption)

        print()
        print("Lifestyle events:")
        print(f"  caffeine: {len(caffeine)} ({caffeine_outside} outside disruption, {len(caffeine_in_disruption)} during)")
        print(f"  alcohol: {len(alcohol)} | mood/context: {len(mood)}")

        print()
        print("Missing data:")
        print(f"  full sync gap day indices: {sorted(FULL_SYNC_GAP_DAYS)}")
        print(f"  incomplete sleep day indices: {sorted(INCOMPLETE_SLEEP_DAYS)}")
        print(f"  HRV-only missing indices: {sorted(HRV_MISSING_DAYS)}")
        print(f"  VO2 missing indices: {sorted(VO2_MISSING_DAYS)}")
        print(f"  null sleep rows: {sum(1 for r in daily if r.sleep_duration_hours is None)}")
        print(f"  null HRV rows: {sum(1 for r in daily if r.hrv_sdnn_ms is None)}")

        print()
        print("Pattern visibility (observational — not causal):")
        print("  baseline: Phase 1 RHR/sleep/exercise show noise without strong directional shift")
        print("  improvement: Phase 2 structured workouts + lower RHR + higher VO2")
        print("  disruption: Phase 3a lower sleep, higher RHR, wider HRV swings, more caffeine")
        print("  recovery: Phase 3b sleep/RHR moving back toward improved levels")
        print("  ambiguity: caffeine + late-work context overlap sleep/RHR changes in days 61-75")
        print("  non-signal: respiratory_rate stable across phases")

        print()
        print("Recent trend vs longer-term history:")
        print("  Recent trend = 7-day avg vs prior 30-day baseline at each checkpoint.")
        print("  Longer-term = phase summaries above across the full 90-day window.")

        _print_trend_checkpoint(session, user_id, CHECKPOINT_DAY_30_INDEX, "~Day 30")
        _print_trend_checkpoint(session, user_id, CHECKPOINT_DAY_60_INDEX, "~Day 60")
        _print_trend_checkpoint(session, user_id, CHECKPOINT_DAY_75_INDEX, "~Day 75")
        _print_trend_checkpoint(session, user_id, CHECKPOINT_DAY_90_INDEX, "Day 90")

        payload = get_health_trends_for_agent(user_id, as_of_date=checkpoint_date(CHECKPOINT_DAY_90_INDEX))
        print()
        print(f"Agent tool (Day 90): {len(payload['trends'])} trends, JSON-serializable")


if __name__ == "__main__":
    main()
