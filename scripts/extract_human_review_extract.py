#!/usr/bin/env python3
"""Preserve markdown bundle, extract verified JSON human-review record."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.human_review_extract import (
    BUNDLE_PATH,
    EXTRACT_PATH,
    VERIFY_REPORT_PATH,
    extract_reviews_from_markdown,
    preserve_markdown_backup,
    verify_extract_against_markdown,
    write_extract_json,
)


def main() -> int:
    if not BUNDLE_PATH.exists():
        print(f"ERROR: Missing bundle at {BUNDLE_PATH}", file=sys.stderr)
        return 1

    backup = preserve_markdown_backup()
    print(f"Preserved markdown backup: {backup}")

    records, source_text = extract_reviews_from_markdown()
    filled = sum(1 for record in records if record.human_open_coding_notes.strip())
    passes = sum(1 for record in records if record.normalized_pass_fail == "PASS")
    fails = sum(1 for record in records if record.normalized_pass_fail == "FAIL")

    if filled == 0:
        print(
            "ERROR: No human open-coding notes found in markdown. "
            "Save baseline_human_review_bundle_v1.md before extracting.",
            file=sys.stderr,
        )
        return 1

    write_extract_json(records, source_text)
    report = verify_extract_against_markdown()

    print(f"Wrote extract: {EXTRACT_PATH}")
    print(f"Wrote verification report: {VERIFY_REPORT_PATH}")
    print(f"Scenarios: {len(records)} | filled notes: {filled} | PASS: {passes} | FAIL: {fails}")
    print(f"Verification: {report['verification_status']}")

    if report["verification_status"] != "verified":
        print("ERROR: JSON extract failed verification against markdown.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
