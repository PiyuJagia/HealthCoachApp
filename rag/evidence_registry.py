"""Parse and validate knowledge evidence_registry.csv."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from rag.schemas import EvidenceSourceRecord

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE_REGISTRY_PATH = PROJECT_ROOT / "knowledge" / "registry" / "evidence_registry.csv"

REQUIRED_COLUMNS = [
    "source_key",
    "title",
    "authors_or_organization",
    "publication_year",
    "source_type",
    "doi",
    "pmid",
    "source_url",
    "verification_status",
    "notes",
]

SOURCE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
ALLOWED_VERIFICATION_STATUSES = frozenset(
    {
        "verified",
        "needs_verification",
        "revision_required",
        "superseded",
        "incomplete_metadata",
        "page_verification_required",
    }
)


class EvidenceRegistryError(Exception):
    """Raised when the evidence registry cannot be loaded or validated."""


def _normalize_field(value: str | None) -> str:
    return (value or "").strip()


def _validate_source_key(source_key: str) -> None:
    if not source_key:
        raise EvidenceRegistryError("source_key must not be blank.")
    if not SOURCE_KEY_PATTERN.fullmatch(source_key):
        raise EvidenceRegistryError(
            f"Invalid source_key '{source_key}'. "
            "Use letters, numbers, hyphens, and underscores only."
        )


def _validate_verification_status(value: str, *, source_key: str) -> str:
    normalized = _normalize_field(value)
    if normalized not in ALLOWED_VERIFICATION_STATUSES:
        raise EvidenceRegistryError(
            f"Invalid verification_status for source_key '{source_key}': "
            f"'{value}'. Expected one of {sorted(ALLOWED_VERIFICATION_STATUSES)}."
        )
    return normalized


def _row_to_record(row: dict[str, str]) -> EvidenceSourceRecord:
    source_key = _normalize_field(row.get("source_key"))
    _validate_source_key(source_key)

    return EvidenceSourceRecord(
        source_key=source_key,
        title=_normalize_field(row.get("title")),
        authors_or_organization=_normalize_field(row.get("authors_or_organization")),
        publication_year=_normalize_field(row.get("publication_year")),
        source_type=_normalize_field(row.get("source_type")),
        doi=_normalize_field(row.get("doi")),
        pmid=_normalize_field(row.get("pmid")),
        source_url=_normalize_field(row.get("source_url")),
        verification_status=_validate_verification_status(
            row.get("verification_status", ""),
            source_key=source_key,
        ),
        notes=_normalize_field(row.get("notes")),
    )


def _validate_header(fieldnames: list[str] | None) -> None:
    if not fieldnames:
        raise EvidenceRegistryError(
            f"Evidence registry file is missing a header row: {DEFAULT_EVIDENCE_REGISTRY_PATH}"
        )
    if fieldnames != REQUIRED_COLUMNS:
        raise EvidenceRegistryError(
            "Evidence registry header does not match the expected schema. "
            f"Expected: {REQUIRED_COLUMNS}. Found: {fieldnames}"
        )


def load_evidence_registry(
    registry_path: Path | None = None,
) -> list[EvidenceSourceRecord]:
    """Load and validate all rows from evidence_registry.csv."""
    path = registry_path or DEFAULT_EVIDENCE_REGISTRY_PATH
    if not path.is_file():
        raise EvidenceRegistryError(f"Evidence registry file not found: {path}")

    records: list[EvidenceSourceRecord] = []
    seen_source_keys: set[str] = set()

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_header(reader.fieldnames)

        for row_number, row in enumerate(reader, start=2):
            if row is None:
                continue

            source_key = _normalize_field(row.get("source_key"))
            if not source_key:
                continue

            record = _row_to_record(row)
            if record.source_key in seen_source_keys:
                raise EvidenceRegistryError(
                    f"Duplicate source_key '{record.source_key}' in evidence registry "
                    f"(row {row_number})."
                )

            seen_source_keys.add(record.source_key)
            records.append(record)

    return records


def get_evidence_source(
    source_key: str,
    *,
    registry_path: Path | None = None,
) -> EvidenceSourceRecord:
    normalized_key = source_key.strip()
    if not normalized_key:
        raise EvidenceRegistryError("source_key must not be blank.")

    for record in load_evidence_registry(registry_path):
        if record.source_key == normalized_key:
            return record

    raise EvidenceRegistryError(f"No evidence registry row found for source_key '{normalized_key}'.")
