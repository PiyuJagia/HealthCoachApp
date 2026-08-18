"""Marcus demo scenario definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from data.database import get_session_factory
from data.demo_seed import (
    CHECKPOINT_DAY_30_INDEX,
    CHECKPOINT_DAY_60_INDEX,
    CHECKPOINT_DAY_75_INDEX,
    CHECKPOINT_DAY_90_INDEX,
    DEMO_DISPLAY_NAME,
    checkpoint_date,
)
from data.models import User


@dataclass(frozen=True)
class HealthScenario:
    scenario_id: str
    label: str
    day_index: int
    purpose: str

    @property
    def as_of_date(self) -> date:
        return checkpoint_date(self.day_index)


SCENARIOS: dict[str, HealthScenario] = {
    "day30": HealthScenario(
        scenario_id="day30",
        label="Baseline (~Day 30)",
        day_index=CHECKPOINT_DAY_30_INDEX,
        purpose="baseline/calibration — expect little meaningful signal",
    ),
    "day60": HealthScenario(
        scenario_id="day60",
        label="Fitness improvement (~Day 60)",
        day_index=CHECKPOINT_DAY_60_INDEX,
        purpose="positive fitness/exercise pattern",
    ),
    "day75": HealthScenario(
        scenario_id="day75",
        label="Disruption / ambiguity (~Day 75)",
        day_index=CHECKPOINT_DAY_75_INDEX,
        purpose="disruption / mixed signals — avoid causal claims",
    ),
    "day90": HealthScenario(
        scenario_id="day90",
        label="Recovery (~Day 90)",
        day_index=CHECKPOINT_DAY_90_INDEX,
        purpose="recovery / current-state context",
    ),
}


def resolve_demo_user_id() -> int:
    session_factory = get_session_factory()
    with session_factory() as session:
        user = session.scalar(
            select(User).where(User.display_name == DEMO_DISPLAY_NAME).order_by(User.id.asc())
        )
        if user is None:
            raise RuntimeError(
                f"Demo user '{DEMO_DISPLAY_NAME}' not found. Run scripts/seed_demo_health_data.py first."
            )
        return int(user.id)
