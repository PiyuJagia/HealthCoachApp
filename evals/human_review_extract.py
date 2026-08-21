"""Extract and verify completed human reviews from the baseline review bundle."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from evals.failure_taxonomy_analysis import HumanReviewRecord, parse_human_review_bundle_from_text

BUNDLE_PATH = Path(__file__).resolve().parent / "results" / "baseline_human_review_bundle_v1.md"
BACKUP_PATH = BUNDLE_PATH.with_suffix(".md.human_review_backup")
EXTRACT_PATH = Path(__file__).resolve().parent / "results" / "baseline_human_review_extract_v1.json"
VERIFY_REPORT_PATH = EXTRACT_PATH.with_suffix(".verification.json")

MANUAL_FIELD_HEADINGS = (
    "Human open-coding notes:",
    "What was good?",
    "What was bad / surprising?",
    "Likely originating layer:",
    "Human PASS / FAIL:",
    "Possible failure label:",
)


@dataclass(frozen=True)
class ExtractManifest:
    source_markdown_path: str
    source_markdown_sha256: str
    extracted_at_utc: str
    scenario_count: int
    pass_count: int
    fail_count: int
    filled_open_coding_count: int
    verification_status: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def preserve_markdown_backup(bundle_path: Path | None = None, backup_path: Path | None = None) -> Path:
    source = bundle_path or BUNDLE_PATH
    target = backup_path or BACKUP_PATH
    if not source.exists():
        raise FileNotFoundError(f"Missing review bundle: {source}")
    text = source.read_text(encoding="utf-8")
    target.write_text(text, encoding="utf-8")
    return target


def _record_to_dict(record: HumanReviewRecord) -> dict[str, str]:
    return {
        "scenario_id": record.scenario_id,
        "family": record.family,
        "name": record.name,
        "human_open_coding_notes": record.human_open_coding_notes,
        "what_was_good": record.what_was_good,
        "what_was_bad": record.what_was_bad,
        "likely_originating_layer": record.likely_originating_layer,
        "human_pass_fail": record.normalized_pass_fail or record.human_pass_fail.strip(),
    }


def extract_reviews_from_markdown(bundle_path: Path | None = None) -> tuple[list[HumanReviewRecord], str]:
    source = bundle_path or BUNDLE_PATH
    text = source.read_text(encoding="utf-8")
    records = parse_human_review_bundle_from_text(text)
    if len(records) != 15:
        raise ValueError(f"Expected 15 review records; found {len(records)}.")
    return records, text


def write_extract_json(
    records: list[HumanReviewRecord],
    source_text: str,
    extract_path: Path | None = None,
    source_path: Path | None = None,
) -> Path:
    out = extract_path or EXTRACT_PATH
    passes = sum(1 for record in records if record.normalized_pass_fail == "PASS")
    fails = sum(1 for record in records if record.normalized_pass_fail == "FAIL")
    filled = sum(1 for record in records if record.human_open_coding_notes.strip())
    manifest = ExtractManifest(
        source_markdown_path=str(source_path or BUNDLE_PATH),
        source_markdown_sha256=sha256_text(source_text),
        extracted_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        scenario_count=len(records),
        pass_count=passes,
        fail_count=fails,
        filled_open_coding_count=filled,
        verification_status="pending",
    )
    payload = {
        "manifest": asdict(manifest),
        "reviews": [_record_to_dict(record) for record in records],
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def _extract_manual_block(section: str) -> str:
    marker = "### MANUAL REVIEW"
    start = section.find(marker)
    if start < 0:
        return ""
    tail = section[start + len(marker) :]
    end = tail.find("\n---------------------------------------")
    if end < 0:
        return tail.strip()
    return tail[:end].strip()


def _field_from_manual(manual: str, heading: str) -> str:
    start = manual.find(heading)
    if start < 0:
        return ""
    content_start = start + len(heading)
    next_positions = [
        manual.find(next_heading, content_start)
        for next_heading in MANUAL_FIELD_HEADINGS
        if next_heading != heading and manual.find(next_heading, content_start) >= 0
    ]
    end = min(next_positions) if next_positions else len(manual)
    return manual[content_start:end].strip()


def verify_extract_against_markdown(
    extract_path: Path | None = None,
    bundle_path: Path | None = None,
) -> dict[str, object]:
    source = bundle_path or BUNDLE_PATH
    out = extract_path or EXTRACT_PATH
    bundle_text = source.read_text(encoding="utf-8")
    payload = json.loads(out.read_text(encoding="utf-8"))
    manifest = payload["manifest"]
    expected_hash = manifest["source_markdown_sha256"]
    actual_hash = sha256_text(bundle_text)
    hash_match = expected_hash == actual_hash

    parsed_records = parse_human_review_bundle_from_text(bundle_text)
    parsed_by_id = {record.scenario_id: record for record in parsed_records}
    mismatches: list[dict[str, str]] = []

    for item in payload["reviews"]:
        scenario_id = item["scenario_id"]
        parsed = parsed_by_id.get(scenario_id)
        if parsed is None:
            mismatches.append({"scenario_id": scenario_id, "field": "*", "issue": "missing in markdown parse"})
            continue
        comparisons = {
            "human_open_coding_notes": (item.get("human_open_coding_notes", ""), parsed.human_open_coding_notes),
            "what_was_good": (item.get("what_was_good", ""), parsed.what_was_good),
            "what_was_bad": (item.get("what_was_bad", ""), parsed.what_was_bad),
            "likely_originating_layer": (item.get("likely_originating_layer", ""), parsed.likely_originating_layer),
            "human_pass_fail": (item.get("human_pass_fail", ""), parsed.normalized_pass_fail),
        }
        for field, (expected, actual) in comparisons.items():
            if expected != actual:
                mismatches.append(
                    {
                        "scenario_id": scenario_id,
                        "field": field,
                        "issue": "value mismatch",
                    }
                )

    status = "verified" if hash_match and not mismatches else "failed"
    report = {
        "verification_status": status,
        "markdown_sha256_match": hash_match,
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }
    payload["manifest"]["verification_status"] = status
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    VERIFY_REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
