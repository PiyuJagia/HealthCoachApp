"""Parse completed baseline human review bundle fields for F3 taxonomy analysis."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

BUNDLE_PATH = Path(__file__).resolve().parent / "results" / "baseline_human_review_bundle_v1.md"
EXTRACT_PATH = Path(__file__).resolve().parent / "results" / "baseline_human_review_extract_v1.json"
SECTION_SPLIT = re.compile(r"^## (HC-EVAL-[A-Z0-9]+) — Family ([A-Z]): (.+)$", re.MULTILINE)

MANUAL_FIELD_HEADINGS = (
    "Human open-coding notes:",
    "What was good?",
    "What was bad / surprising?",
    "Likely originating layer:",
    "Human PASS / FAIL:",
    "Possible failure label:",
)


@dataclass(frozen=True)
class HumanReviewRecord:
    scenario_id: str
    family: str
    name: str
    human_open_coding_notes: str
    what_was_good: str
    what_was_bad: str
    likely_originating_layer: str
    human_pass_fail: str

    @property
    def normalized_pass_fail(self) -> str:
        value = self.human_pass_fail.strip().lower()
        if value.startswith("pass"):
            return "PASS"
        if value.startswith("fail"):
            return "FAIL"
        return ""


def _extract_manual_review(section: str) -> str:
    marker = "### MANUAL REVIEW"
    start = section.find(marker)
    if start < 0:
        return ""
    tail = section[start + len(marker) :]
    separator = tail.find("\n---------------------------------------")
    if separator >= 0:
        tail = tail[:separator]
    return tail.strip()


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


def _extract_layer(manual: str) -> str:
    layers = [
        "data / synthetic scenario",
        "deterministic analytics",
        "agent trajectory / tool selection",
        "retrieval",
        "evidence policy",
        "generation",
        "final guard",
        "product limitation",
        "unclear",
    ]
    selected: list[str] = []
    for layer in layers:
        if re.search(rf"\[\s*x\s*[\]>]?\s*{re.escape(layer)}", manual, re.IGNORECASE):
            selected.append(layer)
    return "; ".join(selected)


def _extract_pass_fail(manual: str) -> str:
    inline = re.search(
        r"Human PASS / FAIL:\s*(PASS|FAIL|Pass|Fail|pass|fail)\b",
        manual,
    )
    if inline:
        return inline.group(1)
    block = _field_from_manual(manual, "Human PASS / FAIL:")
    return block.splitlines()[0].strip() if block else ""


def parse_human_review_bundle_from_text(text: str) -> list[HumanReviewRecord]:
    records: list[HumanReviewRecord] = []
    matches = list(SECTION_SPLIT.finditer(text))
    for index, match in enumerate(matches):
        scenario_id, family, name = match.groups()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end]
        manual = _extract_manual_review(section)
        if not manual:
            continue
        records.append(
            HumanReviewRecord(
                scenario_id=scenario_id,
                family=family,
                name=name.strip(),
                human_open_coding_notes=_field_from_manual(manual, "Human open-coding notes:"),
                what_was_good=_field_from_manual(manual, "What was good?"),
                what_was_bad=_field_from_manual(manual, "What was bad / surprising?"),
                likely_originating_layer=_extract_layer(manual),
                human_pass_fail=_extract_pass_fail(manual),
            )
        )
    return records


def parse_human_review_bundle(path: Path | None = None) -> list[HumanReviewRecord]:
    """Parse canonical human reviews from markdown bundle."""
    bundle_path = path or BUNDLE_PATH
    text = bundle_path.read_text(encoding="utf-8")
    return parse_human_review_bundle_from_text(text)


def parse_human_review_extract(path: Path | None = None) -> list[HumanReviewRecord]:
    """Load machine-readable extract after markdown verification."""
    extract_path = path or EXTRACT_PATH
    payload = json.loads(extract_path.read_text(encoding="utf-8"))
    manifest = payload.get("manifest", {})
    if manifest.get("verification_status") != "verified":
        raise ValueError(
            "Human review extract is not verified. Run scripts/extract_human_review_extract.py first."
        )
    return [
        HumanReviewRecord(
            scenario_id=item["scenario_id"],
            family=item["family"],
            name=item["name"],
            human_open_coding_notes=item.get("human_open_coding_notes", ""),
            what_was_good=item.get("what_was_good", ""),
            what_was_bad=item.get("what_was_bad", ""),
            likely_originating_layer=item.get("likely_originating_layer", ""),
            human_pass_fail=item.get("human_pass_fail", ""),
        )
        for item in payload["reviews"]
    ]
