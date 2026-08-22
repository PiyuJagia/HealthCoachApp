"""Write F4.1.1 deterministic contract inspection artifacts from canonical Marcus seed."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.database import get_session_factory, init_database, reset_engine_cache
from data.demo_seed import seed_demo_health_data
from evals.contract_inspection import inspect_selected_scenarios, write_inspection_artifacts


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_stdout()
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    reset_engine_cache()
    init_database(drop_existing=True)
    session = get_session_factory()()
    try:
        user = seed_demo_health_data(session, reset=True)
        report = inspect_selected_scenarios(session, user.id)
        paths = write_inspection_artifacts(report)
    finally:
        session.close()
    print(f"scenarios={len(report['scenarios'])} contradictions={report['contradiction_count']}")
    print(f"foundation_safe_to_accept={report['foundation_safe_to_accept']}")
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0 if report["foundation_safe_to_accept"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
