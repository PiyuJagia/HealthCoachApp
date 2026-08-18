"""Narrow data-access helpers for health records."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models import HealthDaily, LifestyleEvent, User


def create_user(
    session: Session,
    *,
    display_name: str,
    age: int | None = None,
    sex: str | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    goal: str | None = None,
    created_at: datetime | None = None,
) -> User:
    user = User(
        display_name=display_name,
        age=age,
        sex=sex,
        height_cm=height_cm,
        weight_kg=weight_kg,
        goal=goal,
        created_at=created_at or datetime.utcnow(),
    )
    session.add(user)
    session.flush()
    return user


def get_user(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def upsert_health_daily(session: Session, record: HealthDaily) -> HealthDaily:
    existing = session.scalar(
        select(HealthDaily).where(
            HealthDaily.user_id == record.user_id,
            HealthDaily.date == record.date,
        )
    )
    if existing is None:
        session.add(record)
        session.flush()
        return record

    for field in (
        "resting_hr_bpm",
        "hrv_sdnn_ms",
        "sleep_duration_hours",
        "sleep_score",
        "steps",
        "exercise_minutes",
        "active_calories",
        "workout_count",
        "vo2_max",
        "respiratory_rate",
    ):
        setattr(existing, field, getattr(record, field))
    session.flush()
    return existing


def add_lifestyle_event(session: Session, event: LifestyleEvent) -> LifestyleEvent:
    session.add(event)
    session.flush()
    return event


def list_health_daily_for_user(
    session: Session,
    user_id: int,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[HealthDaily]:
    query = select(HealthDaily).where(HealthDaily.user_id == user_id)
    if start_date is not None:
        query = query.where(HealthDaily.date >= start_date)
    if end_date is not None:
        query = query.where(HealthDaily.date <= end_date)
    query = query.order_by(HealthDaily.date)
    return list(session.scalars(query))


def list_lifestyle_events_for_user(
    session: Session,
    user_id: int,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> list[LifestyleEvent]:
    query = select(LifestyleEvent).where(LifestyleEvent.user_id == user_id)
    if start_at is not None:
        query = query.where(LifestyleEvent.occurred_at >= start_at)
    if end_at is not None:
        query = query.where(LifestyleEvent.occurred_at <= end_at)
    query = query.order_by(LifestyleEvent.occurred_at)
    return list(session.scalars(query))
