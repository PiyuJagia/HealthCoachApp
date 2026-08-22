"""Write F4.6 salience inspection artifacts from canonical Marcus seed."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.database import get_engine, get_session_factory, init_database, reset_engine_cache
from data.demo_seed import seed_demo_health_data
from evals.salience_inspection import inspect_salience, write_salience_inspection_artifacts


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
            report = inspect_salience(session, user.id)
            paths = write_salience_inspection_artifacts(report)
        finally:
            session.close()
            get_engine().dispose()
            reset_engine_cache()
    by_id = {item["scenario_id"]: item for item in report["scenarios"]}
    print("B1 worthy", by_id["HC-EVAL-B1"]["insight_salience"]["insight_worthy"])
    print("A1 worthy", by_id["HC-EVAL-A1"]["insight_salience"]["insight_worthy"])
    print("B3 worthy", by_id["HC-EVAL-B3"]["insight_salience"]["insight_worthy"])
    print("C3 sleep cand", next(
        row["salience"]["insight_candidate"]
        for row in by_id["HC-EVAL-C3"]["metrics"]
        if row["metric"] == "sleep_duration_hours"
    ))
    print("early worthy", report["early_pattern"]["insight_salience"]["insight_worthy"])
    print("early maturity", report["early_pattern"]["sleep"]["data_maturity_state"])
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
