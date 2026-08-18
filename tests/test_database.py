"""Offline tests for the health-data database layer."""

from __future__ import annotations

import unittest
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError

from data.models import HealthDaily, LifestyleEvent
from data.repository import (
    add_lifestyle_event,
    create_user,
    get_user,
    list_health_daily_for_user,
    list_lifestyle_events_for_user,
    upsert_health_daily,
)
from tests.test_helpers import open_test_session


class DatabaseInitializationTests(unittest.TestCase):
    def test_init_database_creates_tables(self) -> None:
        session = open_test_session()
        try:
            user = create_user(session, display_name="Table Check")
            session.commit()
            self.assertIsNotNone(user.id)
        finally:
            session.close()


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = open_test_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_create_and_read_demo_user(self) -> None:
        user = create_user(
            self.session,
            display_name="Alex Demo",
            age=34,
            sex="female",
            height_cm=168.0,
            weight_kg=62.0,
            goal="improve sleep consistency and cardiovascular fitness",
        )
        self.session.commit()

        loaded = get_user(self.session, user.id)
        assert loaded is not None
        self.assertEqual(loaded.display_name, "Alex Demo")
        self.assertEqual(loaded.age, 34)
        self.assertEqual(loaded.goal, "improve sleep consistency and cardiovascular fitness")

    def test_health_daily_user_date_uniqueness(self) -> None:
        user = create_user(self.session, display_name="Unique Daily")
        self.session.flush()

        upsert_health_daily(
            self.session,
            HealthDaily(user_id=user.id, date=date(2026, 1, 1), steps=8000),
        )
        self.session.commit()

        duplicate = HealthDaily(user_id=user.id, date=date(2026, 1, 1), steps=9000)
        self.session.add(duplicate)
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_upsert_health_daily_updates_existing_row(self) -> None:
        user = create_user(self.session, display_name="Upsert User")
        self.session.flush()

        upsert_health_daily(
            self.session,
            HealthDaily(user_id=user.id, date=date(2026, 2, 1), steps=7000),
        )
        upsert_health_daily(
            self.session,
            HealthDaily(user_id=user.id, date=date(2026, 2, 1), steps=8200),
        )
        self.session.commit()

        records = list_health_daily_for_user(self.session, user.id)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].steps, 8200)

    def test_lifestyle_events_store_timestamps(self) -> None:
        user = create_user(self.session, display_name="Event User")
        self.session.flush()
        occurred_at = datetime(2026, 3, 15, 15, 30)

        add_lifestyle_event(
            self.session,
            LifestyleEvent(
                user_id=user.id,
                occurred_at=occurred_at,
                event_type="caffeine",
                quantity=180,
                unit="mg",
                notes="Synthetic afternoon coffee",
            ),
        )
        self.session.commit()

        events = list_lifestyle_events_for_user(self.session, user.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].occurred_at, occurred_at)
        self.assertEqual(events[0].event_type, "caffeine")

    def test_repository_date_filters(self) -> None:
        user = create_user(self.session, display_name="Filter User")
        self.session.flush()

        for day in range(1, 6):
            upsert_health_daily(
                self.session,
                HealthDaily(user_id=user.id, date=date(2026, 4, day), steps=day * 1000),
            )
        self.session.commit()

        filtered = list_health_daily_for_user(
            self.session,
            user.id,
            start_date=date(2026, 4, 2),
            end_date=date(2026, 4, 4),
        )
        self.assertEqual([record.date.day for record in filtered], [2, 3, 4])


if __name__ == "__main__":
    unittest.main()
