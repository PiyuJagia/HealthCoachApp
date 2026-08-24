"""CODIFY evaluation result schema.

Machine-evaluable expectations for the remediated architecture.
Does not rewrite frozen human PASS/FAIL labels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from evals.trace_schema import sanitize_for_trace

GRADER_DETERMINISTIC = "DETERMINISTIC"
GRADER_LLM_AS_JUDGE = "LLM_AS_JUDGE"
GRADER_HUMAN_REVIEW = "HUMAN_REVIEW"
GRADER_HYBRID = "HYBRID"

OUTCOME_PASS = "pass"
OUTCOME_FAIL = "fail"
OUTCOME_NOT_APPLICABLE = "not_applicable"

VALID_GRADER_TYPES = frozenset(
    {
        GRADER_DETERMINISTIC,
        GRADER_LLM_AS_JUDGE,
        GRADER_HUMAN_REVIEW,
        GRADER_HYBRID,
    }
)
VALID_OUTCOMES = frozenset({OUTCOME_PASS, OUTCOME_FAIL, OUTCOME_NOT_APPLICABLE})


@dataclass(frozen=True)
class GraderResult:
    scenario_id: str
    grader_id: str
    grader_type: str
    contract: str
    taxonomy: str | None
    outcome: str
    observed_value: Any
    expected_behavior: str
    evidence: dict[str, Any]
    reason: str
    trace_run_id: str | None = None
    frozen_human_pass_fail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.grader_type not in VALID_GRADER_TYPES:
            raise ValueError(f"Invalid grader_type: {self.grader_type}")
        if self.outcome not in VALID_OUTCOMES:
            raise ValueError(f"Invalid outcome: {self.outcome}")
        return sanitize_for_trace(asdict(self))


@dataclass(frozen=True)
class GraderSpec:
    grader_id: str
    grader_type: str
    contract: str
    taxonomy: str | None
    expected_behavior: str
    executable: bool
    notes: str = ""
    remaining_gap: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioGrade:
    scenario_id: str
    trace_run_id: str | None
    results: list[GraderResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "trace_run_id": self.trace_run_id,
            "results": [item.to_dict() for item in self.results],
            "deterministic_fail_count": sum(
                1
                for item in self.results
                if item.grader_type == GRADER_DETERMINISTIC and item.outcome == OUTCOME_FAIL
            ),
            "deterministic_pass_count": sum(
                1
                for item in self.results
                if item.grader_type == GRADER_DETERMINISTIC and item.outcome == OUTCOME_PASS
            ),
        }
