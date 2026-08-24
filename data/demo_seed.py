"""Deterministic synthetic demo health dataset generation.

Three-phase fictional narrative (observational patterns only — no causal labels):

Phase 1 (days 1–30):  baseline / calibration — noise without strong directional signal
Phase 2 (days 31–60): structured exercise consistency — cardiovascular improvement pattern
Phase 3 (days 61–90): disruption (61–75) then recovery (76–90) — mixed-signal period
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from data.models import HealthDaily, LifestyleEvent, User
from data.repository import add_lifestyle_event, create_user, upsert_health_daily

DEMO_DISPLAY_NAME = "Marcus Chen"
DEMO_AGE = 36
DEMO_SEX = "male"
DEMO_HEIGHT_CM = 177.0
DEMO_WEIGHT_KG = 84.0
DEMO_GOAL = "Improve sleep consistency and establish sustainable cardiovascular fitness"

DEMO_END_DATE = date(2026, 8, 17)
DEMO_DAY_COUNT = 90
DEMO_RANDOM_SEED = 42

# Phase boundaries (0-based day index)
PHASE1_END_INDEX = 29
PHASE2_ROUTINE_START_INDEX = 34  # day 35
PHASE2_END_INDEX = 59
PHASE3_DISRUPTION_START_INDEX = 60  # day 61
PHASE3_DISRUPTION_END_INDEX = 74  # day 75
PHASE3_RECOVERY_START_INDEX = 75  # day 76

# Missing-data pattern aligned to 90-day spec (1-based days 22–23, 47, 54–55)
FULL_SYNC_GAP_DAYS = frozenset({21, 22})
INCOMPLETE_SLEEP_DAYS = frozenset({46})
HRV_MISSING_DAYS = frozenset({53, 54})
VO2_MISSING_DAYS = frozenset({39})

# Trend inspection checkpoints (0-based offsets from start date)
CHECKPOINT_DAY_30_INDEX = 29
CHECKPOINT_DAY_60_INDEX = 59
CHECKPOINT_DAY_75_INDEX = 74
CHECKPOINT_DAY_90_INDEX = 89

WORKOUT_WEEKDAYS = (0, 2, 4)  # Mon, Wed, Fri


def demo_start_date() -> date:
    return DEMO_END_DATE - timedelta(days=DEMO_DAY_COUNT - 1)


def checkpoint_date(day_index: int) -> date:
    """Return calendar date for a 0-based day index in the demo window."""
    return demo_start_date() + timedelta(days=day_index)


def _day_index(record_date: date) -> int:
    return (record_date - demo_start_date()).days


def _is_structured_workout_day(day_index: int, record_date: date) -> bool:
    if day_index < PHASE2_ROUTINE_START_INDEX:
        return False
    return record_date.weekday() in WORKOUT_WEEKDAYS


def _phase1_workout_day(day_index: int) -> bool:
    """Exploratory 1–2 sessions/week in phase 1 — fixed set for reproducibility."""
    if day_index >= PHASE2_ROUTINE_START_INDEX or day_index in FULL_SYNC_GAP_DAYS:
        return False
    return day_index in {3, 8, 11, 14, 16, 19, 25, 28}


def _exercise_minutes(day_index: int, record_date: date, rng: random.Random) -> tuple[float, int]:
    if day_index in FULL_SYNC_GAP_DAYS:
        return 0.0, 0

    if day_index < PHASE2_ROUTINE_START_INDEX:
        if _phase1_workout_day(day_index):
            minutes = round(rng.uniform(18, 34), 1)
            return minutes, 1
        return round(rng.uniform(0, 12), 1), 0

    if _is_structured_workout_day(day_index, record_date):
        minutes = round(rng.uniform(40, 50), 1)
        return minutes, 1
    return round(rng.uniform(5, 18), 1), 0


def _sleep_hours(day_index: int, rng: random.Random) -> float | None:
    if day_index in FULL_SYNC_GAP_DAYS:
        return None
    if day_index in INCOMPLETE_SLEEP_DAYS:
        return None

    if day_index <= PHASE1_END_INDEX:
        return round(rng.uniform(6.5, 7.5), 2)

    if day_index <= PHASE2_END_INDEX:
        # Somewhat more consistent sleep during structured routine phase
        center = 7.15 + min(0.25, (day_index - 30) * 0.008)
        return round(center + rng.uniform(-0.35, 0.35), 2)

    if day_index <= PHASE3_DISRUPTION_END_INDEX:
        progress = (day_index - PHASE3_DISRUPTION_START_INDEX) / max(
            1, PHASE3_DISRUPTION_END_INDEX - PHASE3_DISRUPTION_START_INDEX
        )
        base = 7.0 - (1.35 * progress)
        return round(base + rng.uniform(-0.3, 0.25), 2)

    # Recovery phase
    recovery_progress = (day_index - PHASE3_RECOVERY_START_INDEX) / max(
        1, DEMO_DAY_COUNT - 1 - PHASE3_RECOVERY_START_INDEX
    )
    base = 5.85 + (0.95 * recovery_progress)
    return round(base + rng.uniform(-0.25, 0.3), 2)


def _resting_hr(day_index: int, rng: random.Random) -> float | None:
    if day_index in FULL_SYNC_GAP_DAYS:
        return None

    if day_index <= PHASE1_END_INDEX:
        return round(71.0 + rng.uniform(-2.0, 2.0), 1)

    if day_index <= PHASE2_END_INDEX:
        progress = (day_index - 30) / max(1, PHASE2_END_INDEX - 30)
        return round(71.0 - (4.0 * progress) + rng.uniform(-1.0, 1.0), 1)

    if day_index <= PHASE3_DISRUPTION_END_INDEX:
        progress = (day_index - PHASE3_DISRUPTION_START_INDEX) / max(
            1, PHASE3_DISRUPTION_END_INDEX - PHASE3_DISRUPTION_START_INDEX
        )
        return round(67.0 + (3.0 * progress) + rng.uniform(-1.0, 1.0), 1)

    recovery_progress = (day_index - PHASE3_RECOVERY_START_INDEX) / max(
        1, DEMO_DAY_COUNT - 1 - PHASE3_RECOVERY_START_INDEX
    )
    return round(69.5 - (2.5 * recovery_progress) + rng.uniform(-0.9, 0.9), 1)


def _hrv(day_index: int, rng: random.Random) -> float | None:
    if day_index in FULL_SYNC_GAP_DAYS or day_index in HRV_MISSING_DAYS:
        return None

    if day_index <= PHASE1_END_INDEX:
        return round(32.0 + rng.uniform(-5.0, 5.0), 1)

    if day_index <= PHASE2_END_INDEX:
        base = 32.0 + min(6.0, (day_index - 30) * 0.15)
        return round(base + rng.uniform(-5.0, 5.0), 1)

    if day_index <= PHASE3_DISRUPTION_END_INDEX:
        swing = 10.0 if (day_index - PHASE3_DISRUPTION_START_INDEX) % 2 == 0 else -8.0
        return round(36.0 + swing + rng.uniform(-3.5, 3.5), 1)

    return round(38.0 + rng.uniform(-4.5, 4.5), 1)


def _vo2_max(day_index: int, rng: random.Random) -> float | None:
    if day_index in FULL_SYNC_GAP_DAYS or day_index in VO2_MISSING_DAYS:
        return None

    if day_index <= PHASE1_END_INDEX:
        return round(38.5 + rng.uniform(-0.15, 0.15), 2)

    if day_index <= PHASE2_END_INDEX:
        progress = (day_index - 30) / max(1, PHASE2_END_INDEX - 30)
        return round(38.5 + (1.8 * progress) + rng.uniform(-0.2, 0.2), 2)

    if day_index <= PHASE3_DISRUPTION_END_INDEX:
        return round(40.1 + rng.uniform(-0.25, 0.15), 2)

    recovery_progress = (day_index - PHASE3_RECOVERY_START_INDEX) / max(
        1, DEMO_DAY_COUNT - 1 - PHASE3_RECOVERY_START_INDEX
    )
    return round(40.0 + (0.7 * recovery_progress) + rng.uniform(-0.2, 0.2), 2)


def _respiratory_rate(day_index: int, rng: random.Random) -> float | None:
    """Non-signal control metric — stable noise, independent of other patterns."""
    if day_index in FULL_SYNC_GAP_DAYS:
        return None
    return round(14.5 + rng.uniform(-0.5, 0.5), 1)


def _steps(day_index: int, is_workout: bool, rng: random.Random) -> int | None:
    if day_index in FULL_SYNC_GAP_DAYS:
        return None
    base = rng.randint(7000, 12000) if day_index <= PHASE1_END_INDEX else rng.randint(6500, 8500)
    if is_workout:
        base += rng.randint(1800, 2800)
    return int(base)


def build_demo_daily_record(user_id: int, record_date: date, rng: random.Random) -> HealthDaily:
    day_index = _day_index(record_date)
    exercise_minutes, workout_count = _exercise_minutes(day_index, record_date, rng)
    sleep_hours = _sleep_hours(day_index, rng)

    sleep_score = None
    if sleep_hours is not None:
        sleep_score = round(min(95.0, max(55.0, sleep_hours * 11.5 + rng.uniform(-4, 4))), 1)

    active_calories = None
    if day_index not in FULL_SYNC_GAP_DAYS:
        active_calories = round(280 + exercise_minutes * 4.2 + rng.uniform(-30, 40), 1)

    return HealthDaily(
        user_id=user_id,
        date=record_date,
        resting_hr_bpm=_resting_hr(day_index, rng),
        hrv_sdnn_ms=_hrv(day_index, rng),
        sleep_duration_hours=sleep_hours,
        sleep_score=sleep_score,
        steps=_steps(day_index, workout_count == 1, rng),
        exercise_minutes=exercise_minutes if day_index not in FULL_SYNC_GAP_DAYS else None,
        active_calories=active_calories,
        workout_count=workout_count if day_index not in FULL_SYNC_GAP_DAYS else None,
        vo2_max=_vo2_max(day_index, rng),
        respiratory_rate=_respiratory_rate(day_index, rng),
    )


def build_demo_lifestyle_events(user_id: int, start_date: date, rng: random.Random) -> list[LifestyleEvent]:
    events: list[LifestyleEvent] = []

    # Exploratory caffeine (spec days 15–20) and routine use outside disruption
    routine_caffeine_days = [14, 16, 18, 37, 40, 43, 49, 55]
    for offset in routine_caffeine_days:
        event_date = start_date + timedelta(days=offset)
        events.append(
            LifestyleEvent(
                user_id=user_id,
                occurred_at=datetime.combine(event_date, datetime.min.time()).replace(
                    hour=15, minute=int(rng.choice([0, 15, 30]))
                ),
                event_type="caffeine",
                quantity=180,
                unit="mg",
                notes="Synthetic afternoon coffee",
            )
        )

    # Disruption-clustered caffeine (spec days 72–78; confounded — not sole cause)
    disruption_caffeine_days = [60, 62, 64, 66, 68, 70, 72, 74]
    for offset in disruption_caffeine_days:
        event_date = start_date + timedelta(days=offset)
        events.append(
            LifestyleEvent(
                user_id=user_id,
                occurred_at=datetime.combine(event_date, datetime.min.time()).replace(
                    hour=16, minute=int(rng.choice([0, 30, 45]))
                ),
                event_type="caffeine",
                quantity=200,
                unit="mg",
                notes="Synthetic afternoon coffee",
            )
        )

    # Post-disruption / recovery — moderate caffeine continues
    late_caffeine_days = [82, 86]
    for offset in late_caffeine_days:
        event_date = start_date + timedelta(days=offset)
        events.append(
            LifestyleEvent(
                user_id=user_id,
                occurred_at=datetime.combine(event_date, datetime.min.time()).replace(hour=14, minute=45),
                event_type="caffeine",
                quantity=160,
                unit="mg",
                notes="Synthetic afternoon coffee",
            )
        )

    alcohol_offsets = [8, 22, 35, 48, 62, 80]
    for offset in alcohol_offsets:
        event_date = start_date + timedelta(days=offset)
        events.append(
            LifestyleEvent(
                user_id=user_id,
                occurred_at=datetime.combine(event_date, datetime.min.time()).replace(hour=20, minute=30),
                event_type="alcohol",
                quantity=1.0 if offset not in {63} else 1.5,
                unit="standard_drinks",
                notes="Synthetic social evening",
            )
        )

    mood_offsets = [4, 11, 17, 30, 47, 62, 71, 87]
    for offset in mood_offsets:
        event_date = start_date + timedelta(days=offset)
        events.append(
            LifestyleEvent(
                user_id=user_id,
                occurred_at=datetime.combine(event_date, datetime.min.time()).replace(hour=12, minute=0),
                event_type="mood",
                quantity=float(rng.choice([2, 3, 4])),
                unit="scale_1_5",
                notes="Synthetic self-report",
            )
        )

    # Work/lifestyle context during disruption — observational only, not causal labels
    work_context_days = [61, 63, 65, 67, 69, 71, 73]
    for offset in work_context_days:
        event_date = start_date + timedelta(days=offset)
        events.append(
            LifestyleEvent(
                user_id=user_id,
                occurred_at=datetime.combine(event_date, datetime.min.time()).replace(hour=21, minute=15),
                event_type="mood",
                quantity=3.0,
                unit="scale_1_5",
                notes="Synthetic late work evening",
            )
        )

    rng.shuffle(events)
    return events


def _existing_demo_user(session) -> User | None:
    from sqlalchemy import select

    return session.scalar(
        select(User).where(User.display_name == DEMO_DISPLAY_NAME).order_by(User.id.asc())
    )


def ensure_demo_health_data(session=None) -> User:
    """Idempotently create the Marcus demo dataset if it is not already present.

    Does not reset tables or insert a second demo user when one already exists.
    Safe for Streamlit reruns and local use of an existing SQLite file.
    """
    from data.database import get_session_factory, init_database

    init_database(drop_existing=False)
    owns_session = session is None
    if owns_session:
        session = get_session_factory()()
    try:
        user = _existing_demo_user(session)
        if user is None:
            user = seed_demo_health_data(session, reset=False)
        _ = user.id, user.display_name
        if owns_session:
            session.expunge(user)
        return user
    finally:
        if owns_session:
            session.close()


def seed_demo_health_data(session, *, reset: bool = False) -> User:
    """Create the fictional demo user and ~90 days of synthetic observations."""
    from data.database import init_database

    init_database(drop_existing=reset)

    start_date = demo_start_date()
    rng = random.Random(DEMO_RANDOM_SEED)

    user = create_user(
        session,
        display_name=DEMO_DISPLAY_NAME,
        age=DEMO_AGE,
        sex=DEMO_SEX,
        height_cm=DEMO_HEIGHT_CM,
        weight_kg=DEMO_WEIGHT_KG,
        goal=DEMO_GOAL,
        created_at=datetime.combine(start_date, datetime.min.time()),
    )

    for offset in range(DEMO_DAY_COUNT):
        record_date = start_date + timedelta(days=offset)
        upsert_health_daily(session, build_demo_daily_record(user.id, record_date, rng))

    for event in build_demo_lifestyle_events(user.id, start_date, rng):
        add_lifestyle_event(session, event)

    session.commit()
    return user
