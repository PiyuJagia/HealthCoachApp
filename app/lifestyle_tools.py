"""Deterministic lifestyle-context facts for agent consumption.

User-specific observational context. Not scientific evidence. Not causal scoring.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from statistics import mean
from typing import Any

from data.database import get_session_factory
from data.models import LifestyleEvent
from data.repository import list_lifestyle_events_for_user

DEFAULT_LOOKBACK_DAYS = 14
MIN_LOOKBACK_DAYS = 1
MAX_LOOKBACK_DAYS = 30

# Maps stored (event_type, unit) onto relationship-policy available_inputs.
# Presence of an input enables evaluation; it does not prove causation or
# authorize a recommendation.
POLICY_INPUT_BY_EVENT_UNIT = {
    ("caffeine", "mg"): "caffeine_mg",
    ("alcohol", "standard_drinks"): "alcohol_units",
}

LATE_WORK_NOTE_MARKER = "late work"


def clamp_lookback_days(lookback_days: int | None) -> int:
    days = DEFAULT_LOOKBACK_DAYS if lookback_days is None else int(lookback_days)
    return max(MIN_LOOKBACK_DAYS, min(MAX_LOOKBACK_DAYS, days))


def lifestyle_window(
    as_of_date: date, lookback_days: int
) -> tuple[date, date, datetime, datetime]:
    window_end = as_of_date
    window_start = as_of_date - timedelta(days=lookback_days - 1)
    start_at = datetime.combine(window_start, time.min)
    end_at = datetime.combine(window_end, time.max.replace(microsecond=0))
    return window_start, window_end, start_at, end_at


def policy_inputs_from_events(events: list[LifestyleEvent]) -> list[str]:
    inputs: set[str] = set()
    for event in events:
        if event.quantity is None or not event.unit:
            continue
        mapped = POLICY_INPUT_BY_EVENT_UNIT.get((event.event_type, event.unit))
        if mapped:
            inputs.add(mapped)
    return sorted(inputs)


def _event_payload(event: LifestyleEvent) -> dict[str, Any]:
    occurred = event.occurred_at
    return {
        "event_type": event.event_type,
        "occurred_at": occurred.isoformat(sep=" "),
        "occurred_on": occurred.date().isoformat(),
        "hour": occurred.hour,
        "minute": occurred.minute,
        "quantity": event.quantity,
        "unit": event.unit,
        "notes": event.notes,
    }


def _type_summary(event_type: str, group: list[LifestyleEvent]) -> dict[str, Any]:
    quantities = [event.quantity for event in group if event.quantity is not None]
    units = {event.unit for event in group if event.unit}
    unit = next(iter(units)) if len(units) == 1 else None
    numeric_ok = bool(quantities) and unit is not None
    return {
        "event_type": event_type,
        "count": len(group),
        "dates": sorted({event.occurred_at.date().isoformat() for event in group}),
        "latest_occurred_at": max(event.occurred_at for event in group).isoformat(sep=" "),
        "hours": [event.occurred_at.hour for event in group],
        "quantity_sum": round(sum(quantities), 2) if numeric_ok else None,
        "quantity_mean": round(mean(quantities), 2) if numeric_ok else None,
        "unit": unit,
        "distinct_notes": sorted({event.notes for event in group if event.notes}),
    }


def _late_work_count(events: list[LifestyleEvent]) -> int:
    return sum(
        1
        for event in events
        if event.notes and LATE_WORK_NOTE_MARKER in event.notes.lower()
    )


def get_lifestyle_context_for_agent(
    user_id: int,
    *,
    as_of_date: date,
    lookback_days: int | None = None,
) -> dict[str, Any]:
    """Return JSON-serializable lifestyle observations. No LLM. No Pinecone. No policy verdict."""
    lookback = clamp_lookback_days(lookback_days)
    window_start, window_end, start_at, end_at = lifestyle_window(as_of_date, lookback)
    session_factory = get_session_factory()
    with session_factory() as session:
        events = list_lifestyle_events_for_user(
            session, user_id, start_at=start_at, end_at=end_at
        )
    grouped: dict[str, list[LifestyleEvent]] = defaultdict(list)
    for event in events:
        grouped[event.event_type].append(event)
    policy_inputs = policy_inputs_from_events(events)
    return {
        "user_id": user_id,
        "as_of_date": as_of_date.isoformat(),
        "lookback_days": lookback,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "event_count": len(events),
        "events": [_event_payload(event) for event in events],
        "by_type": [_type_summary(event_type, group) for event_type, group in sorted(grouped.items())],
        "late_work_context_event_count": _late_work_count(events),
        "policy_available_inputs": policy_inputs,
        "disclaimer": (
            "Lifestyle events are user-specific observational context, not scientific "
            "evidence. Co-occurrence is not causation. This tool does not authorize "
            "recommendations. Relationship claims require retrieve_authorized_evidence "
            "and the deterministic evidence policy."
        ),
    }
