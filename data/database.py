"""Database engine and session management."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from data.models import Base

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_URL = "sqlite:///./data/healthcoach.db"


def get_database_url() -> str:
    """Return DATABASE_URL from the environment or the local SQLite default."""
    return os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL).strip() or DEFAULT_SQLITE_URL


def _sqlite_path_from_url(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None
    relative = url.removeprefix("sqlite:///")
    if relative == ":memory:":
        return None
    path = Path(relative)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create a cached SQLAlchemy engine for the configured DATABASE_URL."""
    url = get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, future=True, connect_args=connect_args)
    db_path = _sqlite_path_from_url(url)
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return engine


def get_session_factory() -> sessionmaker[Session]:
    """Return a session factory bound to the configured engine."""
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def init_database(*, drop_existing: bool = False) -> None:
    """Create database tables."""
    engine = get_engine()
    if drop_existing:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def reset_engine_cache() -> None:
    """Clear cached engine (useful when DATABASE_URL changes in tests)."""
    get_engine.cache_clear()
