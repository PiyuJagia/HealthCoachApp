"""Shared helpers for database-backed tests."""

from __future__ import annotations

import os

from data.database import get_session_factory, init_database, reset_engine_cache


def use_in_memory_database() -> None:
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    reset_engine_cache()
    init_database(drop_existing=True)


def open_test_session():
    use_in_memory_database()
    return get_session_factory()()
