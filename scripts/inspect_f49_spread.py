"""Write F4.9 within-window HRV spread inspection artifacts from Marcus seed."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.database import get_engine, get_session_factory, init_database, reset_engine_cache
from data.demo_seed import seed_demo_health_data
from evals.spread_inspection import inspect_spread, write_spread_inspection_artifacts


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
            report = inspect_spread(session, user.id)
            paths = write_spread_inspection_artifacts(report)
        finally:
            session.close()
            get_engine().dispose()
            reset_engine_cache()
    c4 = report["marcus"]["c4"]
    spread = c4["hrv"]["within_window_spread"]
    print("C4 direction", c4["hrv"]["direction"], c4["hrv"]["percent_change"])
    print("C4 spread n/mean/sd", spread["observation_count"], spread["mean"], spread["sample_standard_deviation"])
    print("C4 baseline sd / ratio", spread["baseline_standard_deviation"], spread["spread_ratio"])
    print("C4 comparison", spread["spread_comparison_allowed"])
    print("C4 HRV candidate", c4["hrv"]["salience"]["insight_candidate"])
    print("B1 worthy", report["marcus"]["b1"]["insight_salience"]["insight_worthy"])
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
