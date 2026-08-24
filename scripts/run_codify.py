"""Emit CODIFY coverage artifacts and optional F5.2 smoke grades. No Gemini."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.codify.runner import write_coverage_artifacts, write_f52_smoke


def main() -> int:
    coverage_json, coverage_csv = write_coverage_artifacts()
    smoke = write_f52_smoke()
    print(f"coverage_json={coverage_json}")
    print(f"coverage_csv={coverage_csv}")
    print(json.dumps(smoke.get("summary"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
