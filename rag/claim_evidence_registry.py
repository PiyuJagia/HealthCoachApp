"""Parse and validate claim-level evidence mappings."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from rag.evidence_registry import EvidenceRegistryError, load_evidence_registry
from rag.registry import RegistryError, load_registry
from rag.schemas import ClaimEvidenceRecord

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CLAIM_REGISTRY_PATH = PROJECT_ROOT / "knowledge" / "registry" / "claim_evidence_registry.csv"

REQUIRED_COLUMNS = [
    "claim_id",
    "document_id",
    "section",
    "claim_summary",
    "source_key",
    "support_type",
    "claim_grade",
    "causal_class",
    "within_person_valid",
    "product_level",
    "evidence_measurement",
    "product_measurement",
    "verification_status",
    "verified_date",
    "notes",
]

CLAIM_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
ALLOWED_SUPPORT_TYPES = frozenset({"direct", "partial", "context", "contradicts", "unsupported"})
ALLOWED_WITHIN_PERSON_VALID = frozenset({"yes", "conditional", "no"})
ALLOWED_VERIFICATION_STATUSES = frozenset(
    {
        "verified",
        "needs_verification",
        "revision_required",
        "superseded",
        "revision_complete_pending_review",
    }
)


class ClaimEvidenceRegistryError(Exception):
    """Raised when the claim evidence registry cannot be loaded or validated."""


def _normalize_field(value: str | None) -> str:
    return (value or "").strip()


def _validate_claim_id(claim_id: str) -> None:
    if not claim_id:
        raise ClaimEvidenceRegistryError("claim_id must not be blank.")
    if not CLAIM_ID_PATTERN.fullmatch(claim_id):
        raise ClaimEvidenceRegistryError(
            f"Invalid claim_id '{claim_id}'. "
            "Use letters, numbers, hyphens, and underscores only."
        )


def _validate_enum(value: str, *, field_name: str, allowed: frozenset[str], claim_id: str) -> str:
    normalized = _normalize_field(value)
    if normalized not in allowed:
        raise ClaimEvidenceRegistryError(
            f"Invalid {field_name} for claim_id '{claim_id}': "
            f"'{value}'. Expected one of {sorted(allowed)}."
        )
    return normalized


def _load_reference_sets(
    *,
    source_registry_path: Path | None = None,
    evidence_registry_path: Path | None = None,
) -> tuple[set[str], set[str]]:
    document_ids = {record.document_id for record in load_registry(source_registry_path)}
    source_keys = {record.source_key for record in load_evidence_registry(evidence_registry_path)}
    return document_ids, source_keys


def _row_to_record(
    row: dict[str, str],
    *,
    document_ids: set[str],
    source_keys: set[str],
) -> ClaimEvidenceRecord:
    claim_id = _normalize_field(row.get("claim_id"))
    _validate_claim_id(claim_id)

    document_id = _normalize_field(row.get("document_id"))
    if document_id not in document_ids:
        raise ClaimEvidenceRegistryError(
            f"Unknown document_id '{document_id}' for claim_id '{claim_id}'."
        )

    source_key = _normalize_field(row.get("source_key"))
    if source_key not in source_keys:
        raise ClaimEvidenceRegistryError(
            f"Unknown source_key '{source_key}' for claim_id '{claim_id}'."
        )

    return ClaimEvidenceRecord(
        claim_id=claim_id,
        document_id=document_id,
        section=_normalize_field(row.get("section")),
        claim_summary=_normalize_field(row.get("claim_summary")),
        source_key=source_key,
        support_type=_validate_enum(
            row.get("support_type", ""),
            field_name="support_type",
            allowed=ALLOWED_SUPPORT_TYPES,
            claim_id=claim_id,
        ),
        claim_grade=_normalize_field(row.get("claim_grade")),
        causal_class=_normalize_field(row.get("causal_class")),
        within_person_valid=_validate_enum(
            row.get("within_person_valid", ""),
            field_name="within_person_valid",
            allowed=ALLOWED_WITHIN_PERSON_VALID,
            claim_id=claim_id,
        ),
        product_level=_normalize_field(row.get("product_level")),
        evidence_measurement=_normalize_field(row.get("evidence_measurement")),
        product_measurement=_normalize_field(row.get("product_measurement")),
        verification_status=_validate_enum(
            row.get("verification_status", ""),
            field_name="verification_status",
            allowed=ALLOWED_VERIFICATION_STATUSES,
            claim_id=claim_id,
        ),
        verified_date=_normalize_field(row.get("verified_date")),
        notes=_normalize_field(row.get("notes")),
    )


def _validate_header(fieldnames: list[str] | None) -> None:
    if not fieldnames:
        raise ClaimEvidenceRegistryError(
            f"Claim evidence registry file is missing a header row: {DEFAULT_CLAIM_REGISTRY_PATH}"
        )
    if fieldnames != REQUIRED_COLUMNS:
        raise ClaimEvidenceRegistryError(
            "Claim evidence registry header does not match the expected schema. "
            f"Expected: {REQUIRED_COLUMNS}. Found: {fieldnames}"
        )


def load_claim_evidence_registry(
    registry_path: Path | None = None,
    *,
    source_registry_path: Path | None = None,
    evidence_registry_path: Path | None = None,
) -> list[ClaimEvidenceRecord]:
    """Load and validate all rows from claim_evidence_registry.csv."""
    path = registry_path or DEFAULT_CLAIM_REGISTRY_PATH
    if not path.is_file():
        raise ClaimEvidenceRegistryError(f"Claim evidence registry file not found: {path}")

    document_ids, source_keys = _load_reference_sets(
        source_registry_path=source_registry_path,
        evidence_registry_path=evidence_registry_path,
    )

    records: list[ClaimEvidenceRecord] = []
    seen_mappings: set[tuple[str, str]] = set()

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_header(reader.fieldnames)

        for row_number, row in enumerate(reader, start=2):
            if row is None:
                continue

            claim_id = _normalize_field(row.get("claim_id"))
            if not claim_id:
                continue

            record = _row_to_record(row, document_ids=document_ids, source_keys=source_keys)
            mapping_key = (record.claim_id, record.source_key)
            if mapping_key in seen_mappings:
                raise ClaimEvidenceRegistryError(
                    f"Duplicate claim/source mapping '{record.claim_id}' + '{record.source_key}' "
                    f"in claim evidence registry (row {row_number})."
                )

            seen_mappings.add(mapping_key)
            records.append(record)

    return records
