"""Assignment 4 TRACE eval dashboard data loaders.

Reads frozen eval artifacts and invokes existing CODIFY graders.
Does not call Gemini, mutate traces, or change grader logic.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.codify.catalog import DETERMINISTIC_SPECS
from evals.codify.runner import grade_trace_paths, summarize_grades
from evals.failure_taxonomy_analysis import parse_human_review_extract

RESULTS_DIR = Path(__file__).resolve().parent / "results"
EXTRACT_PATH = RESULTS_DIR / "baseline_human_review_extract_v1.json"
TAXONOMY_COUNTS_PATH = RESULTS_DIR / "failure_taxonomy_counts_v1.csv"
CODIFY_SUMMARY_PATH = RESULTS_DIR / "post_remediation_codify_summary_v1.json"
TRACE_INDEX_PATH = RESULTS_DIR / "post_remediation_trace_index_v1.csv"
TRACES_DIR = RESULTS_DIR / "post_remediation_traces_v1"
REVIEW_BUNDLE_PATH = RESULTS_DIR / "post_remediation_review_bundle_v1.md"
COMPARISON_PATH = RESULTS_DIR / "post_remediation_comparison_v1.md"

SCENARIO_ORDER = (
    "HC-EVAL-A1",
    "HC-EVAL-A2",
    "HC-EVAL-A3",
    "HC-EVAL-A4",
    "HC-EVAL-B1",
    "HC-EVAL-B2",
    "HC-EVAL-B3",
    "HC-EVAL-C1",
    "HC-EVAL-C2",
    "HC-EVAL-C3",
    "HC-EVAL-C4",
    "HC-EVAL-D1",
    "HC-EVAL-D2",
    "HC-EVAL-D3",
    "HC-EVAL-E1",
)

# F7.1 synthesis mapping. No structured JSON exists; historical F3 CSV is not mutated.
F71_TAXONOMY_STATUS = {
    "T1": "CLOSED",
    "T2": "CLOSED",
    "T3": "CLOSED",
    "T4": "CLOSED",
    "T5": "CLOSED",
    "T6": "CLOSED",
    "T7": "IMPROVED",
    "T8": "IMPROVED",
    "T9": "NOT MEANINGFULLY TESTED",
    "T10": "EVAL DESIGN ISSUE",
    "T11": "STILL PRESENT",
    "T12": "CLOSED",
}

TAXONOMY_DASHBOARD_NAMES = {
    "T1": "Lifestyle context",
    "T2": "As-of provenance",
    "T3": "Data maturity / eligibility",
    "T4": "Longitudinal maintenance",
    "T5": "Salience",
    "T6": "Respiratory control",
    "T7": "Output contract",
    "T8": "Physiological over-generalization",
    "T9": "Redundant retrieval",
    "T10": "Eval design mismatch",
    "T11": "Eval overlap",
    "T12": "Within-window spread",
}

GRADER_CATEGORY_BY_CONTRACT = {
    "F4.1": "maturity / claim eligibility",
    "F4.3": "weekly-summary gates",
    "F4.4": "lifestyle provenance",
    "F4.5": "longitudinal maintenance",
    "F4.5/F4.7": "longitudinal maintenance",
    "F4.6": "salience",
    "F4.7": "recommendation boundary",
    "F4.8": "respiratory control",
    "F4.9": "spread vs level",
    "F5.1": "output-contract shape",
    "F5.1A": "quiet path",
}

REMEDIATION_EXAMPLES = (
    {
        "example": "B1 / T5",
        "before": "Small activity movement became INSIGHT",
        "fix": "Deterministic salience / insight-worthiness",
        "after": "NO_SIGNIFICANT_NEW_PATTERN",
    },
    {
        "example": "B3 / T4",
        "before": "Maintenance of prior gains missed",
        "fix": "Longitudinal context",
        "after": "maintenance_of_gain INSIGHT",
    },
    {
        "example": "C1–C3 / T1",
        "before": "Lifestyle context inaccessible to ADK",
        "fix": "get_lifestyle_context + policy input wiring",
        "after": "Lifestyle context visible and traceable",
    },
    {
        "example": "D1/D2 / T2",
        "before": "Missing same-day measurements invisible",
        "fix": "As-of provenance / coverage",
        "after": "Missingness visible; historical context kept",
    },
    {
        "example": "E1 / T6",
        "before": "Respiratory rate absent from agent contract",
        "fix": "Daily control metric",
        "after": "RR bounding context, no broad reassurance",
    },
)

EVIDENCE_ROWS = (
    {"stage": "Target", "artifact": "healthcoach_trace_baseline_v1 (A1–E1)"},
    {"stage": "Run", "artifact": "evals/traces/ · baseline_trace_index_v1.csv"},
    {"stage": "Analyze", "artifact": "baseline_human_review_bundle_v1.md / extract JSON"},
    {"stage": "Cluster", "artifact": "failure_taxonomy_v1.md · failure_taxonomy_counts_v1.csv"},
    {"stage": "Evaluate / Codify", "artifact": "evals/codify/ · f60_codify_v1.md"},
    {"stage": "Remediate", "artifact": "F4.1–F4.9 · F5.1 / F5.1A inspection artifacts"},
    {"stage": "Rerun", "artifact": "post_remediation_v1 traces · comparison · F7.1 synthesis"},
)

KNOWN_LIMITATIONS = (
    "Motivational quote may occasionally become more directive than intended.",
    "Caffeine relationship may dominate when R-07 is recommendation-eligible.",
    "No equal-confounder narration rule.",
    "T9 redundant retrieval was not meaningfully evaluated.",
    "T10 / T11 are evaluation-design limitations.",
)


class DashboardDataError(FileNotFoundError):
    """A required dashboard artifact is missing or unreadable."""


@dataclass(frozen=True)
class Scorecard:
    baseline_pass: int
    baseline_fail: int
    baseline_total: int
    v2_pass: int
    v2_fail: int
    v2_needs_review: int
    v2_total: int
    codify_pass: int
    codify_fail: int
    codify_na: int
    codify_evaluations: int
    deterministic_grader_count: int

    @property
    def baseline_pass_rate(self) -> float:
        return 100.0 * self.baseline_pass / self.baseline_total if self.baseline_total else 0.0

    @property
    def v2_pass_rate(self) -> float:
        return 100.0 * self.v2_pass / self.v2_total if self.v2_total else 0.0

    @property
    def improvement_pp(self) -> float:
        return self.v2_pass_rate - self.baseline_pass_rate


@dataclass
class DashboardBundle:
    scorecard: Scorecard
    taxonomy_rows: list[dict[str, str]]
    comparison_rows: list[dict[str, str]]
    grader_rows: list[dict[str, str]]
    remediation_examples: tuple[dict[str, str], ...] = REMEDIATION_EXAMPLES
    evidence_rows: tuple[dict[str, str], ...] = EVIDENCE_ROWS
    known_limitations: tuple[str, ...] = KNOWN_LIMITATIONS
    sources: dict[str, str] = field(default_factory=dict)


def _require(path: Path) -> Path:
    if not path.exists():
        raise DashboardDataError(f"Missing dashboard artifact: {path}")
    return path


def _scenario_key(raw: str) -> str:
    text = raw.strip()
    if text.startswith("HC-EVAL-"):
        return text
    if re.fullmatch(r"[A-E]\d", text):
        return f"HC-EVAL-{text}"
    return text


def _family(scenario_id: str) -> str:
    return scenario_id.replace("HC-EVAL-", "")[:1]


def load_baseline_labels(results_dir: Path | None = None) -> dict[str, str]:
    extract_path = (results_dir or RESULTS_DIR) / EXTRACT_PATH.name
    _require(extract_path)
    records = parse_human_review_extract(extract_path)
    return {record.scenario_id: record.normalized_pass_fail for record in records}


def load_v2_quality_labels(results_dir: Path | None = None) -> dict[str, str]:
    review_path = (results_dir or RESULTS_DIR) / REVIEW_BUNDLE_PATH.name
    _require(review_path)
    text = review_path.read_text(encoding="utf-8")
    labels: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        heading = re.match(r"^## (HC-EVAL-[A-E]\d)\b", line)
        if heading:
            current = heading.group(1)
            continue
        if current:
            match = re.search(r"V2 label\s*\|\s*\*\*(PASS|FAIL|NEEDS_REVIEW)\*\*", line)
            if match:
                labels[current] = match.group(1)
                current = None
    if len(labels) != 15:
        raise DashboardDataError(
            f"Expected 15 V2 quality labels in {review_path}, found {len(labels)}"
        )
    return labels


def load_codify_summary(results_dir: Path | None = None) -> dict[str, Any]:
    path = (results_dir or RESULTS_DIR) / CODIFY_SUMMARY_PATH.name
    _require(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_v2_index(results_dir: Path | None = None) -> dict[str, dict[str, str]]:
    path = (results_dir or RESULTS_DIR) / TRACE_INDEX_PATH.name
    _require(path)
    rows = {row["scenario_id"]: row for row in csv.DictReader(path.open(encoding="utf-8"))}
    missing = [item for item in SCENARIO_ORDER if item not in rows]
    if missing:
        raise DashboardDataError(f"V2 index missing scenarios: {', '.join(missing)}")
    return rows


def official_trace_paths(results_dir: Path | None = None) -> list[Path]:
    root = results_dir or RESULTS_DIR
    index = load_v2_index(root)
    traces_dir = root / TRACES_DIR.name
    paths: list[Path] = []
    for scenario_id in SCENARIO_ORDER:
        path = traces_dir / index[scenario_id]["trace_file"]
        _require(path)
        paths.append(path)
    return paths


def load_taxonomy_rows(results_dir: Path | None = None) -> list[dict[str, str]]:
    path = (results_dir or RESULTS_DIR) / TAXONOMY_COUNTS_PATH.name
    _require(path)
    by_id = {row["taxonomy_id"]: row for row in csv.DictReader(path.open(encoding="utf-8"))}
    rows: list[dict[str, str]] = []
    for taxonomy_id in TAXONOMY_DASHBOARD_NAMES:
        source = by_id.get(taxonomy_id, {})
        rows.append(
            {
                "id": taxonomy_id,
                "name": TAXONOMY_DASHBOARD_NAMES[taxonomy_id],
                "original": source.get("cluster_name", ""),
                "status": F71_TAXONOMY_STATUS[taxonomy_id],
                "baseline_scenarios": source.get("all_affected_scenarios", ""),
            }
        )
    return rows


def _parse_comparison_table(text: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    in_table = False
    for line in text.splitlines():
        if line.startswith("| scenario_id |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            if re.match(r"^\|[\s\-|]+\|$", line):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) < 14:
                continue
            scenario_id = _scenario_key(cells[0])
            rows[scenario_id] = {
                "scenario_id": scenario_id,
                "family": cells[1],
                "change": cells[12],
                "remaining_issue": cells[13],
            }
    return rows


def load_comparison_rows(
    results_dir: Path | None = None,
    *,
    baseline_labels: dict[str, str] | None = None,
    v2_labels: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    root = results_dir or RESULTS_DIR
    baseline = baseline_labels or load_baseline_labels(root)
    v2 = v2_labels or load_v2_quality_labels(root)
    extras = _parse_comparison_table(_require(root / COMPARISON_PATH.name).read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for scenario_id in SCENARIO_ORDER:
        extra = extras.get(scenario_id, {})
        rows.append(
            {
                "scenario": scenario_id.replace("HC-EVAL-", ""),
                "family": extra.get("family") or _family(scenario_id),
                "baseline": baseline.get(scenario_id, ""),
                "v2": v2.get(scenario_id, ""),
                "change": extra.get("change", ""),
                "remaining_issue": extra.get("remaining_issue", ""),
            }
        )
    return rows


def load_grader_catalog_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for spec in DETERMINISTIC_SPECS:
        rows.append(
            {
                "grader_id": spec.grader_id,
                "category": GRADER_CATEGORY_BY_CONTRACT.get(spec.contract, spec.contract),
                "contract": spec.contract,
                "taxonomy": spec.taxonomy or "",
                "expected_behavior": spec.expected_behavior,
            }
        )
    return rows


def load_scorecard(
    results_dir: Path | None = None,
    *,
    baseline_labels: dict[str, str] | None = None,
    v2_labels: dict[str, str] | None = None,
    codify_summary: dict[str, Any] | None = None,
) -> Scorecard:
    root = results_dir or RESULTS_DIR
    baseline = baseline_labels or load_baseline_labels(root)
    v2 = v2_labels or load_v2_quality_labels(root)
    summary = codify_summary or load_codify_summary(root)
    return Scorecard(
        baseline_pass=sum(1 for value in baseline.values() if value == "PASS"),
        baseline_fail=sum(1 for value in baseline.values() if value == "FAIL"),
        baseline_total=len(baseline),
        v2_pass=sum(1 for value in v2.values() if value == "PASS"),
        v2_fail=sum(1 for value in v2.values() if value == "FAIL"),
        v2_needs_review=sum(1 for value in v2.values() if value == "NEEDS_REVIEW"),
        v2_total=len(v2),
        codify_pass=int(summary["deterministic_pass"]),
        codify_fail=int(summary["deterministic_fail"]),
        codify_na=int(summary["deterministic_not_applicable"]),
        codify_evaluations=int(summary["result_count"]),
        deterministic_grader_count=len(DETERMINISTIC_SPECS),
    )


def load_dashboard_bundle(results_dir: Path | None = None) -> DashboardBundle:
    root = results_dir or RESULTS_DIR
    baseline = load_baseline_labels(root)
    v2 = load_v2_quality_labels(root)
    summary = load_codify_summary(root)
    return DashboardBundle(
        scorecard=load_scorecard(
            root,
            baseline_labels=baseline,
            v2_labels=v2,
            codify_summary=summary,
        ),
        taxonomy_rows=load_taxonomy_rows(root),
        comparison_rows=load_comparison_rows(root, baseline_labels=baseline, v2_labels=v2),
        grader_rows=load_grader_catalog_rows(),
        sources={
            "baseline_extract": str((root / EXTRACT_PATH.name).as_posix()),
            "taxonomy_counts": str((root / TAXONOMY_COUNTS_PATH.name).as_posix()),
            "codify_summary": str((root / CODIFY_SUMMARY_PATH.name).as_posix()),
            "v2_index": str((root / TRACE_INDEX_PATH.name).as_posix()),
            "v2_review": str((root / REVIEW_BUNDLE_PATH.name).as_posix()),
            "comparison": str((root / COMPARISON_PATH.name).as_posix()),
        },
    )


def run_deterministic_codify(results_dir: Path | None = None) -> dict[str, Any]:
    """Grade official V2 traces in memory. Does not write files or call Gemini."""
    root = results_dir or RESULTS_DIR
    started = datetime.now(timezone.utc)
    try:
        paths = official_trace_paths(root)
        grades = grade_trace_paths(paths)
        summary = summarize_grades(grades)
        return {
            "ok": True,
            "error": None,
            "timestamp_utc": started.isoformat(),
            "trace_count": len(paths),
            "summary": summary,
            "failed_grader_ids": summary.get("failed_grader_ids", []),
        }
    except Exception as exc:  # noqa: BLE001 — UI needs a clean error payload
        return {
            "ok": False,
            "error": str(exc),
            "timestamp_utc": started.isoformat(),
            "trace_count": 0,
            "summary": {},
            "failed_grader_ids": [],
        }
