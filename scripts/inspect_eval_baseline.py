"""Display deterministic data support for Assignment 4 baseline scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.baseline_dataset import (
    inspect_scenario_data_support,
    load_baseline_scenarios,
    validate_baseline_manifest,
)


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _metric_summary(support: dict) -> str:
    metrics = support.get("metrics") or {}
    if not metrics:
        return "—"
    parts: list[str] = []
    for name, row in metrics.items():
        parts.append(
            f"{name}:{row.get('direction')}({row.get('percent_change')}%)"
        )
    return "; ".join(parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect Assignment 4 baseline scenarios against Marcus data."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full data-support payloads as JSON.",
    )
    return parser


def main() -> int:
    _configure_stdout()
    load_dotenv(PROJECT_ROOT / ".env")
    args = build_parser().parse_args()

    scenarios = load_baseline_scenarios()
    validate_baseline_manifest(scenarios)

    rows: list[dict] = []
    for scenario in scenarios:
        support = inspect_scenario_data_support(scenario)
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "family": scenario.family,
                "date": scenario.as_of_date.isoformat(),
                "key_metrics": _metric_summary(support),
                "expected_behavior": scenario.expected_high_level_behavior,
                "data_support_status": support.get("data_support_status", "unknown"),
                "null_on_date": ",".join(support.get("null_on_date") or []) or "—",
            }
        )

    if args.json:
        payload = [inspect_scenario_data_support(scenario) for scenario in scenarios]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    headers = (
        "scenario_id",
        "family",
        "date",
        "key_metrics",
        "expected_behavior",
        "data_support_status",
        "null_on_date",
    )
    print("\t".join(headers))
    for row in rows:
        print(
            "\t".join(
                [
                    row["scenario_id"],
                    row["family"],
                    row["date"],
                    row["key_metrics"],
                    row["expected_behavior"],
                    row["data_support_status"],
                    row["null_on_date"],
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
