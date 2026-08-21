"""Build F3 failure taxonomy analysis artifacts from completed human reviews."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.failure_taxonomy_analysis import parse_human_review_bundle

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"

# Bottom-up taxonomy derived from human open-coding (F3 analysis).
CLUSTERS = [
    {
        "taxonomy_id": "T1",
        "name": "Lifestyle context inaccessible to agent",
        "definition": (
            "User-specific lifestyle/context events exist in SQLite but no ADK tool exposes them; "
            "personalized ambiguity-preserving reasoning cannot occur."
        ),
        "layer": "product limitation",
        "root_cause_class": "ROOT CAUSE",
        "priority": "P0",
        "category": "PRODUCT",
        "primary": ["HC-EVAL-C1", "HC-EVAL-C2", "HC-EVAL-C3"],
        "secondary": [],
    },
    {
        "taxonomy_id": "T2",
        "name": "As-of-date measurement provenance gap",
        "definition": (
            "Rolling trend aggregates are returned without indicating whether the as-of-date measurement "
            "is missing; sync gaps and partial missingness are invisible to the model."
        ),
        "layer": "deterministic analytics",
        "root_cause_class": "ROOT CAUSE",
        "priority": "P0",
        "category": "PRODUCT",
        "primary": ["HC-EVAL-D1", "HC-EVAL-D2"],
        "secondary": [],
    },
    {
        "taxonomy_id": "T3",
        "name": "data_sufficient not enforced",
        "definition": (
            "data_sufficient=false is advisory metadata only; insufficient metrics still support "
            "insights, evidence retrieval (meaningful_signal=true), and confident generation."
        ),
        "layer": "product limitation",
        "root_cause_class": "ROOT CAUSE",
        "priority": "P0",
        "category": "PRODUCT",
        "primary": ["HC-EVAL-D3"],
        "secondary": [],
    },
    {
        "taxonomy_id": "T4",
        "name": "Longitudinal maintenance blind spot",
        "definition": (
            "Rolling 7-day vs 30-day comparison cannot distinguish maintained prior improvement "
            "from absence of new pattern; sustained gains may be reported as NO_SIGNIFICANT_NEW_PATTERN."
        ),
        "layer": "deterministic analytics; product limitation",
        "root_cause_class": "ROOT CAUSE",
        "priority": "P1",
        "category": "PRODUCT",
        "primary": ["HC-EVAL-B3"],
        "secondary": [],
    },
    {
        "taxonomy_id": "T5",
        "name": "Low-salience insight surfacing",
        "definition": (
            "Agent elevates modest isolated metric movement into INSIGHT during broadly stable periods "
            "without a product-level salience gate beyond deterministic direction flags."
        ),
        "layer": "agent trajectory / tool selection; product limitation",
        "root_cause_class": "MIXED",
        "priority": "P1",
        "category": "PRODUCT",
        "primary": ["HC-EVAL-B1"],
        "secondary": [],
    },
    {
        "taxonomy_id": "T6",
        "name": "Control metric excluded from agent contract",
        "definition": (
            "Non-signal control metrics (e.g., respiratory_rate) exist in raw data but are omitted "
            "from analytics and get_trend_signals, preventing intended bounding of interpretation."
        ),
        "layer": "deterministic analytics; product limitation",
        "root_cause_class": "ROOT CAUSE",
        "priority": "P1",
        "category": "PRODUCT",
        "primary": ["HC-EVAL-E1"],
        "secondary": [],
    },
    {
        "taxonomy_id": "T7",
        "name": "Directive-first output contract gap",
        "definition": (
            "Final responses are analytically grounded but report-like; they do not follow the intended "
            "Notice → Prioritize → Direct → Explain product structure even when policy/guard pass."
        ),
        "layer": "generation",
        "root_cause_class": "DOWNSTREAM SYMPTOM",
        "priority": "P2",
        "category": "PRODUCT",
        "primary": [],
        "secondary": ["HC-EVAL-A1", "HC-EVAL-A2", "HC-EVAL-A4"],
    },
    {
        "taxonomy_id": "T8",
        "name": "Physiological over-generalization in generation",
        "definition": (
            "Model bundles heterogeneous metric directions into broad stable/cardiovascular summaries "
            "not fully supported by tool outputs."
        ),
        "layer": "generation",
        "root_cause_class": "DOWNSTREAM SYMPTOM",
        "priority": "P2",
        "category": "PRODUCT",
        "primary": [],
        "secondary": ["HC-EVAL-E1"],
    },
    {
        "taxonomy_id": "T9",
        "name": "Redundant evidence retrieval",
        "definition": (
            "Agent performs additional evidence lookups after sufficient authorized evidence already "
            "exists for a bounded non-recommendation insight."
        ),
        "layer": "agent trajectory / tool selection",
        "root_cause_class": "DOWNSTREAM SYMPTOM",
        "priority": "P3",
        "category": "PRODUCT",
        "primary": [],
        "secondary": ["HC-EVAL-A1", "HC-EVAL-A4"],
    },
    {
        "taxonomy_id": "T10",
        "name": "Eval scenario design mismatch",
        "definition": (
            "Scenario ground truth or expected behavior is weak relative to underlying Marcus data; "
            "observed trace should not be penalized as product failure."
        ),
        "layer": "data / synthetic scenario",
        "root_cause_class": "ROOT CAUSE",
        "priority": "P2",
        "category": "EVAL_INFRA",
        "primary": ["HC-EVAL-B2"],
        "secondary": [],
    },
    {
        "taxonomy_id": "T11",
        "name": "Eval overlap / ambiguous scenario discrimination",
        "definition": (
            "Distinct scenarios share the same world state or cannot be fairly discriminated given "
            "current tooling, limiting eval interpretability."
        ),
        "layer": "data / synthetic scenario; product limitation",
        "root_cause_class": "MIXED",
        "priority": "P3",
        "category": "EVAL_INFRA",
        "primary": [],
        "secondary": ["HC-EVAL-A3"],
    },
    {
        "taxonomy_id": "T12",
        "name": "Within-window variability not exposed",
        "definition": (
            "Deterministic analytics and get_trend_signals expose rolling means, percent change, and "
            "direction but not within-window distributional structure such as standard deviation, "
            "range, or volatility. This can cause a stable mean to hide meaningful day-to-day swings."
        ),
        "layer": "deterministic analytics; product limitation",
        "root_cause_class": "ROOT CAUSE",
        "priority": "P1",
        "category": "PRODUCT",
        "primary": ["HC-EVAL-C4"],
        "secondary": [],
        "notes": (
            "The original narrow C4 negative rubric technically passed because the agent did not invent "
            "an HRV decline. The human FAIL represents a product-completeness gap because the system "
            "cannot observe volatility. Future C4 eval should be redesigned once volatility is exposed."
        ),
    },
]

REMEDIATION_THEMES = [
    {
        "theme": "Lifestyle context tool + policy input wiring",
        "clusters": ["T1"],
        "scenarios": ["HC-EVAL-C1", "HC-EVAL-C2", "HC-EVAL-C3"],
    },
    {
        "theme": "Analytics/tool data contract (as-of provenance)",
        "clusters": ["T2"],
        "scenarios": ["HC-EVAL-D1", "HC-EVAL-D2"],
    },
    {
        "theme": "Deterministic eligibility control for data_sufficient",
        "clusters": ["T3"],
        "scenarios": ["HC-EVAL-D3"],
    },
    {
        "theme": "Longitudinal context beyond rolling 7/30 windows",
        "clusters": ["T4"],
        "scenarios": ["HC-EVAL-B3"],
    },
    {
        "theme": "Product salience / insight-worthiness gate",
        "clusters": ["T5"],
        "scenarios": ["HC-EVAL-B1"],
    },
    {
        "theme": "Control-metric exposure in analytics contract",
        "clusters": ["T6"],
        "scenarios": ["HC-EVAL-E1"],
    },
    {
        "theme": "Within-window variability in analytics contract",
        "clusters": ["T12"],
        "scenarios": ["HC-EVAL-C4"],
    },
    {
        "theme": "Directive-first output contract / generation grounding",
        "clusters": ["T7", "T8"],
        "scenarios": ["HC-EVAL-A1", "HC-EVAL-A2", "HC-EVAL-A4", "HC-EVAL-E1"],
    },
    {
        "theme": "Eval dataset refinement",
        "clusters": ["T10", "T11"],
        "scenarios": ["HC-EVAL-B2", "HC-EVAL-A3"],
    },
]


def _write_taxonomy_md(records: list, path: Path) -> None:
    pass_count = sum(1 for r in records if r.normalized_pass_fail == "PASS")
    fail_count = sum(1 for r in records if r.normalized_pass_fail == "FAIL")
    lines = [
        "# Failure Taxonomy v1 — Baseline Human Review Clustering",
        "",
        "Derived bottom-up from completed human open-coding in",
        "`evals/results/baseline_human_review_bundle_v1.md`.",
        "",
        "**Source of truth (human reviews):** `evals/results/baseline_human_review_bundle_v1.md`",
        "**Machine-readable extract:** `evals/results/baseline_human_review_extract_v1.json` (verified against markdown).",
        "",
        f"**Baseline outcome:** {pass_count} PASS / {fail_count} FAIL (n=15)",
        f"**PASS rate:** {pass_count / 15 * 100:.1f}% | **FAIL rate:** {fail_count / 15 * 100:.1f}%",
        "",
        "## Review matrix (compact)",
        "",
        "| scenario_id | family | PASS/FAIL | originating layer | open-coding summary |",
        "|-------------|--------|-----------|-------------------|---------------------|",
    ]
    for record in records:
        summary = record.human_open_coding_notes.replace("\n", " ").strip()
        if not summary:
            summary = "— (blank; layer checked only)" if record.likely_originating_layer else "—"
        elif len(summary) > 100:
            summary = summary[:97] + "..."
        lines.append(
            f"| {record.scenario_id} | {record.family} | {record.normalized_pass_fail} | "
            f"{record.likely_originating_layer or '—'} | {summary} |"
        )
    lines.extend(
        [
            "",
            "**Uncoded FAIL scenarios:** none. HC-EVAL-C3 is clustered as T1; HC-EVAL-C4 is clustered as T12.",
            "",
            "## Derived taxonomy clusters",
            "",
        ]
    )
    evidence_quotes = {
        "T1": (
            "C1: 'cannot access lifestyle events' / C2: 'neither was available to the ADK agent' / "
            "C3: 'no access to lifestyle events, including caffeine'"
        ),
        "T2": "D1: 'measurement-level provenance was lost' / D2: 'Complete sync gap invisible to agent'",
        "T3": "D3: 'data_sufficient is currently advisory metadata rather than an enforced eligibility control'",
        "T4": "B3: 'sustained improvement as no significant new pattern'",
        "T5": "B1: 'elevated a modest isolated increase in steps into an INSIGHT'",
        "T6": "E1: 'excluded from the deterministic trend engine and therefore never reaches the ADK agent'",
        "T7": "A1/A2/A4: 'report-like rather than directive-first Health Coach output'",
        "T8": "E1: 'cardiovascular indicators have remained stable' despite HRV improving",
        "T9": "A1/A4: 'second evidence lookup also appeared potentially redundant'",
        "T10": "B2: 'weakness in the eval dataset/ground-truth design'",
        "T11": "A3: 'same underlying date and signals, suggesting potential redundancy'",
        "T12": (
            "C4: 'does not expose volatility or variability as a first-class signal' / "
            "'A stable mean can hide substantial day-to-day variation'"
        ),
    }
    for cluster in CLUSTERS:
        lines.extend(
            [
                f"### {cluster['taxonomy_id']} — {cluster['name']}",
                "",
                f"**Definition:** {cluster['definition']}",
                "",
                f"**Category:** {cluster['category']}",
                f"**Likely layer(s):** {cluster['layer']}",
                f"**Root cause class:** {cluster['root_cause_class']}",
                f"**Priority:** {cluster['priority']}",
                "",
                f"- **Primary scenarios:** {', '.join(cluster['primary']) or '—'}",
                f"- **Secondary scenarios:** {', '.join(cluster['secondary']) or '—'}",
                f"- **Human evidence:** {evidence_quotes.get(cluster['taxonomy_id'], '—')}",
                "",
            ]
        )
        if cluster.get("notes"):
            lines.append(f"- **Analyst note:** {cluster['notes']}")
            lines.append("")
    lines.extend(
        [
            "## Product failures vs eval infrastructure",
            "",
            "### A. Health Coach product / agent failures (T1–T9, T12)",
            "",
            "Tool contracts, analytics provenance, eligibility enforcement, longitudinal framing,",
            "salience gating, control-metric exposure, within-window variability, and generation/output",
            "symptoms.",
            "",
            "### B. Evaluation / observability limitations (T10–T11)",
            "",
            "B2 eval scenario design weakness (PASS — not penalized). A3 scenario overlap.",
            "Traces were sufficient to reconstruct tool outputs for F3; no primary observability-only",
            "failure cluster emerged from human notes.",
            "",
            "## Root cause vs symptom summary",
            "",
            "| Class | Clusters |",
            "|-------|----------|",
            "| ROOT CAUSE | T1, T2, T3, T4, T6, T10, T12 |",
            "| DOWNSTREAM SYMPTOM | T7, T8, T9 |",
            "| MIXED | T5, T11 |",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_counts_csv(path: Path) -> None:
    rows: list[dict[str, str]] = []
    for cluster in CLUSTERS:
        primary = cluster["primary"]
        secondary = cluster["secondary"]
        affected = sorted(set(primary) | set(secondary))
        rows.append(
            {
                "taxonomy_id": cluster["taxonomy_id"],
                "cluster_name": cluster["name"],
                "category": cluster["category"],
                "priority": cluster["priority"],
                "root_cause_class": cluster["root_cause_class"],
                "primary_count": str(len(primary)),
                "secondary_count": str(len(secondary)),
                "affected_scenario_count": str(len(affected)),
                "affected_percent_of_15": f"{(len(affected) / 15) * 100:.1f}",
                "primary_scenarios": ";".join(primary),
                "secondary_scenarios": ";".join(secondary),
                "all_affected_scenarios": ";".join(affected),
            }
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_remediation_md(path: Path) -> None:
    lines = [
        "# Remediation Priority v1",
        "",
        "Prioritization from F3 cluster analysis (frequency × product impact × architectural leverage).",
        "",
        "## Priority ranking",
        "",
        "### P0 — Must address before trusting eval behavior",
        "- **T1** Lifestyle context inaccessible (C1, C2, C3; blocks Family C intent)",
        "- **T2** As-of-date provenance gap (D1, D2; missingness invisible)",
        "- **T3** data_sufficient not enforced (D3; eligibility metadata only)",
        "",
        "### P1 — High-value architecture improvements",
        "- **T4** Longitudinal maintenance blind spot (B3)",
        "- **T5** Low-salience insight surfacing (B1)",
        "- **T6** Control metric excluded from contract (E1)",
        "- **T12** Within-window variability not exposed (C4)",
        "",
        "### P2 — Important but lower immediate priority",
        "- **T7** Directive-first output gap (PASS scenarios A1/A2/A4)",
        "- **T8** Physiological over-generalization (E1 secondary)",
        "- **T10** Eval scenario design mismatch (B2)",
        "",
        "### P3 — Polish / future",
        "- **T9** Redundant evidence retrieval (A1/A4 secondary)",
        "- **T11** Eval overlap / ambiguous discrimination (A3)",
        "",
        "## Remediation themes",
        "",
    ]
    for theme in REMEDIATION_THEMES:
        lines.extend(
            [
                f"### {theme['theme']}",
                f"- Clusters: {', '.join(theme['clusters'])}",
                f"- Scenarios: {', '.join(theme['scenarios'])}",
                "",
            ]
        )
    lines.extend(
        [
            "## Highest-leverage changes (3–5) before rerun",
            "",
            "1. **Add lifestyle context tool** (`get_lifestyle_context`) and wire caffeine/alcohol/mood "
            "into evidence-policy `available_inputs` → addresses T1 (C1/C2/C3).",
            "2. **Extend trend contract with as-of provenance** (`as_of_date_available`, "
            "`as_of_date_value`, missing counts, latest observation date) → addresses T2 (D1/D2).",
            "3. **Enforce data_sufficient as eligibility gate** in tools, evidence path, and/or output "
            "guard → addresses T3 (D3).",
            "4. **Add longitudinal maintenance signal** (phase-aware or longer-horizon comparison) → "
            "addresses T4 (B3).",
            "5. **Expose selected control metrics + salience gate** (respiratory_rate read-only; "
            "insight-worthiness threshold) → addresses T6 (E1) and T5 (B1).",
            "",
            "Related P1 contract gap: expose within-window variability (standard deviation, range, or "
            "volatility) on metrics already in `get_trend_signals` → addresses T12 (C4). Redesign the "
            "C4 eval after that signal exists; the original negative rubric (do not invent an HRV "
            "decline) already passed.",
            "",
            "Directive-first output formatting (T7) is high product value but likely follows once "
            "grounding/contracts are corrected.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    records = parse_human_review_bundle()
    if len(records) != 15:
        raise SystemExit(f"Expected 15 human review records; found {len(records)}.")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _write_taxonomy_md(records, RESULTS_DIR / "failure_taxonomy_v1.md")
    _write_counts_csv(RESULTS_DIR / "failure_taxonomy_counts_v1.csv")
    _write_remediation_md(RESULTS_DIR / "remediation_priority_v1.md")
    print(f"Wrote taxonomy artifacts to {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
