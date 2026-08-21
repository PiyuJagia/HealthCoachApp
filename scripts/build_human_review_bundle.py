"""Generate Assignment 4 human trace review bundle artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.human_review_bundle import build_review_bundle, build_review_progress_csv


def main() -> int:
    bundle_path = build_review_bundle()
    progress_path = build_review_progress_csv()
    print(f"Review bundle: {bundle_path}")
    print(f"Review progress: {progress_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
