"""Run live Health Coach ADK scenarios for Marcus Chen."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.display import format_activity_lines, policy_summary, summarize_trend_signals
from agent.runner import run_health_review
from agent.scenarios import SCENARIOS, resolve_demo_user_id
from app.agent_tools import get_trend_signals


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Health Coach ADK demo scenarios.")
    parser.add_argument(
        "--scenario",
        action="append",
        choices=sorted(SCENARIOS.keys()),
        help="Scenario id: day30, day60, day75, day90",
    )
    parser.add_argument("--all", action="store_true", help="Run all Marcus demo scenarios.")
    return parser


def _print_scenario_report(scenario_id: str, user_id: int) -> int:
    scenario = SCENARIOS[scenario_id]
    print("=" * 72)
    print(f"SCENARIO: {scenario.scenario_id} — {scenario.label}")
    print(f"Purpose: {scenario.purpose}")
    print(f"as_of_date: {scenario.as_of_date.isoformat()}")

    trends = get_trend_signals(user_id, as_of_date=scenario.as_of_date)
    print("\nTREND SIGNAL SUMMARY")
    for row in summarize_trend_signals(trends):
        print(
            f"  - {row['metric']}: direction={row['direction']} "
            f"sufficient={row['data_sufficient']} change={row['percent_change']}"
        )

    result = run_health_review(
        scenario_id=scenario.scenario_id,
        user_id=user_id,
        as_of_date=scenario.as_of_date,
    )

    print("\nADK ACTIVITY")
    for line in format_activity_lines(result.activity_log):
        print(f"  {line}")

    print("\nPOLICY")
    policy = policy_summary(result.structured)
    print(f"  verdict={policy['policy_verdict']}")
    print(f"  recommendation_authorized={policy['recommendation_authorized']}")
    print(f"  source_refs={policy['source_refs']}")

    print("\nFINAL GUARD")
    print(f"  passed={result.guard_passed}")
    if result.guard_violations:
        print(f"  violations={result.guard_violations}")

    print("\nFINAL RESULT")
    print(json.dumps(result.structured, indent=2, sort_keys=True))
    print(f"\nlatency_ms={result.latency_ms}")
    print(f"TRACE FILE: {result.trace_path}")
    return 0


def main() -> int:
    _configure_stdout()
    load_dotenv(PROJECT_ROOT / ".env")
    args = build_parser().parse_args()
    selected = sorted(SCENARIOS.keys()) if args.all else (args.scenario or [])
    if not selected:
        print("Provide --scenario day30|day60|day75|day90 or --all", file=sys.stderr)
        return 2

    user_id = resolve_demo_user_id()
    exit_code = 0
    for scenario_id in selected:
        try:
            _print_scenario_report(scenario_id, user_id)
        except Exception as exc:  # noqa: BLE001 — scenario runner should surface live failures
            print(f"FAIL: scenario={scenario_id} error={exc!r}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
