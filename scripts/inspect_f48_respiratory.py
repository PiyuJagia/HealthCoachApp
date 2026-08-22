"""Write F4.8 respiratory-rate control inspection artifacts from Marcus seed."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.database import get_engine, get_session_factory, init_database, reset_engine_cache
from data.demo_seed import seed_demo_health_data
from evals.respiratory_inspection import inspect_respiratory, write_respiratory_inspection_artifacts


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_stdout()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "healthcoach.db"
        os.environ["DATABASE_URL"] = "sqlite:///" + db_path.as_posix()
        reset_engine_cache()
        init_database(drop_existing=True)
        session = get_session_factory()()
        try:
            user = seed_demo_health_data(session, reset=True)
            session.commit()
            report = inspect_respiratory(session, user.id)
            paths = write_respiratory_inspection_artifacts(report)
        finally:
            session.close()
            get_engine().dispose()
            reset_engine_cache()
    e1_rr = report["marcus"]["e1"]["metrics"]["respiratory_rate"]
    print("E1 RR direction", e1_rr["direction"], e1_rr["percent_change"])
    print("E1 RR candidate", e1_rr["salience"]["insight_candidate"])
    print("E1 worthy", report["marcus"]["e1"]["insight_salience"]["insight_worthy"])
    print("B1 worthy", report["marcus"]["b1"]["insight_salience"]["insight_worthy"])
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
