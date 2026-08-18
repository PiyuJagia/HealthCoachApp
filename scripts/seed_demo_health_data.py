"""Seed one fictional demo user with ~90 days of synthetic health data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.database import get_database_url, get_session_factory
from data.demo_seed import DEMO_DAY_COUNT, DEMO_DISPLAY_NAME, DEMO_END_DATE, seed_demo_health_data


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed synthetic demo health data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate tables before seeding.",
    )
    return parser


def main() -> None:
    _configure_stdout()
    load_dotenv(PROJECT_ROOT / ".env")
    args = build_parser().parse_args()

    session_factory = get_session_factory()
    with session_factory() as session:
        user = seed_demo_health_data(session, reset=args.reset)
        user_id = user.id

    print("Demo health data seeded")
    print("=" * 72)
    print(f"database_url: {get_database_url()}")
    print(f"user_id: {user_id}")
    print(f"display_name: {DEMO_DISPLAY_NAME}")
    print(f"days_seeded: {DEMO_DAY_COUNT}")
    print(f"end_date: {DEMO_END_DATE.isoformat()}")
    print("data_label: synthetic demo data — not clinical reference data")


if __name__ == "__main__":
    main()
