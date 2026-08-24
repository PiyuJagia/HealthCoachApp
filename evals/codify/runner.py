"""Run CODIFY graders against archived TRACE JSON. Does not call Gemini."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from evals.codify.catalog import DETERMINISTIC_SPECS, SEMANTIC_SPECS, spec_by_id
from evals.codify.deterministic import DETERMINISTIC_GRADERS
from evals.codify.schema import (
    GRADER_DETERMINISTIC,
    OUTCOME_FAIL,
    OUTCOME_NOT_APPLICABLE,
    OUTCOME_PASS,
    GraderResult,
    ScenarioGrade,
)
from evals.failure_taxonomy_analysis import parse_human_review_extract
from evals.trace_schema import sanitize_for_trace

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
COVERAGE_JSON = RESULTS_DIR / "f60_codify_coverage_v1.json"
COVERAGE_CSV = RESULTS_DIR / "f60_codify_coverage_v1.csv"
F52_SMOKE_JSON = RESULTS_DIR / "f60_codify_f52_smoke_v1.json"
F52_TRACE_DIR = RESULTS_DIR / "f52_targeted_live_traces"


def _frozen_labels() -> dict[str, str]:
    try:
        return {
            record.scenario_id: record.normalized_pass_fail
            for record in parse_human_review_extract()
        }
    except (OSError, ValueError):
        return {}


def grade_trace(trace: dict[str, Any]) -> ScenarioGrade:
    labels = _frozen_labels()
    scenario_id = str(trace.get("scenario_id") or "")
    frozen = labels.get(scenario_id) or None
    results: list[GraderResult] = []
    for grader in DETERMINISTIC_GRADERS:
        result = grader(trace)
        if frozen:
            result = GraderResult(
                scenario_id=result.scenario_id,
                grader_id=result.grader_id,
                grader_type=result.grader_type,
                contract=result.contract,
                taxonomy=result.taxonomy,
                outcome=result.outcome,
                observed_value=result.observed_value,
                expected_behavior=result.expected_behavior,
                evidence=result.evidence,
                reason=result.reason,
                trace_run_id=result.trace_run_id,
                frozen_human_pass_fail=frozen,
            )
        results.append(result)
    return ScenarioGrade(
        scenario_id=scenario_id,
        trace_run_id=str(trace.get("run_id") or "") or None,
        results=results,
    )


def load_trace(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def grade_trace_paths(paths: list[Path]) -> list[ScenarioGrade]:
    grades: list[ScenarioGrade] = []
    for path in paths:
        if path.name.endswith(".raw_model.json"):
            continue
        if path.name in {"analysis.json", "run_manifest.json"}:
            continue
        payload = load_trace(path)
        if not payload.get("scenario_id"):
            continue
        grades.append(grade_trace(payload))
    return grades


def grade_trace_directory(directory: Path) -> list[ScenarioGrade]:
    paths = sorted(path for path in directory.glob("*.json") if path.is_file())
    return grade_trace_paths(paths)


def coverage_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in (*DETERMINISTIC_SPECS, *SEMANTIC_SPECS):
        if spec.grader_type == GRADER_DETERMINISTIC:
            coverage = "implemented"
            gap = spec.remaining_gap or ""
        elif spec.grader_type == "HYBRID":
            coverage = "spec_only"
            gap = spec.remaining_gap or "Deterministic phrase half exists in the product guard; semantic half is not executed."
        else:
            coverage = "spec_only"
            gap = spec.remaining_gap or "Requires LLM-as-judge or human review. Not invoked in offline CODIFY."
        rows.append(
            {
                "grader_id": spec.grader_id,
                "contract": spec.contract,
                "taxonomy": spec.taxonomy or "",
                "grader_type": spec.grader_type,
                "executable": spec.executable,
                "current_coverage": coverage,
                "remaining_gap": gap,
                "expected_behavior": spec.expected_behavior,
                "notes": spec.notes,
            }
        )
    return rows


def write_coverage_artifacts(
    *,
    json_path: Path = COVERAGE_JSON,
    csv_path: Path = COVERAGE_CSV,
) -> tuple[Path, Path]:
    rows = coverage_matrix()
    json_path.write_text(json.dumps(sanitize_for_trace({"graders": rows}), indent=2), encoding="utf-8")
    fieldnames = [
        "grader_id",
        "contract",
        "taxonomy",
        "grader_type",
        "executable",
        "current_coverage",
        "remaining_gap",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def summarize_grades(grades: list[ScenarioGrade]) -> dict[str, Any]:
    results = [item for grade in grades for item in grade.results]
    return {
        "scenario_count": len(grades),
        "result_count": len(results),
        "deterministic_pass": sum(
            1 for item in results if item.grader_type == GRADER_DETERMINISTIC and item.outcome == OUTCOME_PASS
        ),
        "deterministic_fail": sum(
            1 for item in results if item.grader_type == GRADER_DETERMINISTIC and item.outcome == OUTCOME_FAIL
        ),
        "deterministic_not_applicable": sum(
            1
            for item in results
            if item.grader_type == GRADER_DETERMINISTIC and item.outcome == OUTCOME_NOT_APPLICABLE
        ),
        "failed_grader_ids": sorted(
            {item.grader_id for item in results if item.outcome == OUTCOME_FAIL}
        ),
        "catalog_deterministic": len(DETERMINISTIC_SPECS),
        "catalog_semantic": len(SEMANTIC_SPECS),
        "catalog": [item.grader_id for item in spec_by_id().values()],
    }


def write_f52_smoke(directory: Path = F52_TRACE_DIR, output: Path = F52_SMOKE_JSON) -> dict[str, Any]:
    grades = grade_trace_directory(directory) if directory.exists() else []
    payload = {
        "trace_directory": str(directory),
        "summary": summarize_grades(grades),
        "scenarios": [grade.to_dict() for grade in grades],
    }
    output.write_text(json.dumps(sanitize_for_trace(payload), indent=2), encoding="utf-8")
    return payload
