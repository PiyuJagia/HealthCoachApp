"""Parse and validate knowledge source_registry.csv."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from rag.schemas import SourceRecord

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "knowledge" / "registry" / "source_registry.csv"
DEFAULT_CURATED_DIR = PROJECT_ROOT / "knowledge" / "curated"

REQUIRED_COLUMNS = [
    "document_id",
    "title",
    "organization",
    "topic",
    "topic_category",
    "source_url",
    "publication_date",
    "retrieval_date",
    "document_type",
    "evidence_level",
    "local_filename",
    "version",
    "approved_for_ingestion",
    "notes",
    "curated_path",
]

DOCUMENT_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


class RegistryError(Exception):
    """Raised when the source registry cannot be loaded or validated."""


def _normalize_field(value: str | None) -> str:
    return (value or "").strip()


def _parse_approval_value(raw_value: str, *, document_id: str) -> bool:
    normalized = raw_value.strip().upper()
    if normalized == "TRUE":
        return True
    if normalized == "FALSE":
        return False
    raise RegistryError(
        f"Invalid approved_for_ingestion value for document_id '{document_id}': "
        f"'{raw_value}'. Expected TRUE or FALSE."
    )


def _validate_document_id(document_id: str) -> None:
    if not document_id:
        raise RegistryError("document_id must not be blank.")
    if not DOCUMENT_ID_PATTERN.fullmatch(document_id):
        raise RegistryError(
            f"Invalid document_id '{document_id}'. "
            "Use lowercase snake_case with letters, numbers, and underscores only."
        )


def _row_to_record(row: dict[str, str]) -> SourceRecord:
    document_id = _normalize_field(row.get("document_id"))
    _validate_document_id(document_id)

    return SourceRecord(
        document_id=document_id,
        title=_normalize_field(row.get("title")),
        organization=_normalize_field(row.get("organization")),
        topic=_normalize_field(row.get("topic")),
        topic_category=_normalize_field(row.get("topic_category")),
        source_url=_normalize_field(row.get("source_url")),
        publication_date=_normalize_field(row.get("publication_date")),
        retrieval_date=_normalize_field(row.get("retrieval_date")),
        document_type=_normalize_field(row.get("document_type")),
        evidence_level=_normalize_field(row.get("evidence_level")),
        local_filename=_normalize_field(row.get("local_filename")),
        version=_normalize_field(row.get("version")),
        approved_for_ingestion=_parse_approval_value(
            row.get("approved_for_ingestion", ""),
            document_id=document_id,
        ),
        notes=_normalize_field(row.get("notes")),
        curated_path=_normalize_field(row.get("curated_path")),
    )


def _validate_header(fieldnames: list[str] | None) -> None:
    if not fieldnames:
        raise RegistryError(
            f"Registry file is missing a header row: {DEFAULT_REGISTRY_PATH}"
        )

    if fieldnames != REQUIRED_COLUMNS:
        raise RegistryError(
            "Registry header does not match the expected schema. "
            f"Expected: {REQUIRED_COLUMNS}. Found: {fieldnames}"
        )


def load_registry(registry_path: Path | None = None) -> list[SourceRecord]:
    """Load and validate all rows from source_registry.csv."""
    path = registry_path or DEFAULT_REGISTRY_PATH

    if not path.is_file():
        raise RegistryError(f"Registry file not found: {path}")

    records: list[SourceRecord] = []
    seen_document_ids: set[str] = set()

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_header(reader.fieldnames)

        for row_number, row in enumerate(reader, start=2):
            if row is None:
                continue

            document_id = _normalize_field(row.get("document_id"))
            if not document_id:
                continue

            record = _row_to_record(row)

            if record.document_id in seen_document_ids:
                raise RegistryError(
                    f"Duplicate document_id '{record.document_id}' in registry "
                    f"(row {row_number})."
                )

            seen_document_ids.add(record.document_id)
            records.append(record)

    return records


def get_source_record(
    document_id: str,
    *,
    registry_path: Path | None = None,
) -> SourceRecord:
    """Return one registry row by document_id."""
    normalized_id = document_id.strip()
    if not normalized_id:
        raise RegistryError("document_id must not be blank.")

    for record in load_registry(registry_path):
        if record.document_id == normalized_id:
            return record

    raise RegistryError(f"No registry row found for document_id '{normalized_id}'.")


def get_approved_sources(*, registry_path: Path | None = None) -> list[SourceRecord]:
    """Return only rows approved for ingestion."""
    return [
        record
        for record in load_registry(registry_path)
        if record.approved_for_ingestion
    ]


def resolve_curated_path(
    record: SourceRecord,
    *,
    project_root: Path | None = None,
) -> Path:
    """Resolve the curated Markdown path for one registry record."""
    root = project_root or PROJECT_ROOT

    if record.curated_path:
        return root / record.curated_path

    if not record.local_filename:
        raise RegistryError(
            f"Cannot resolve curated path for document_id '{record.document_id}': "
            "local_filename is blank and curated_path is not set."
        )

    return root / "knowledge" / "curated" / record.local_filename


def validate_curated_file_exists(
    record: SourceRecord,
    *,
    project_root: Path | None = None,
) -> Path:
    """Validate that the resolved curated Markdown file exists."""
    path = resolve_curated_path(record, project_root=project_root)
    if not path.is_file():
        raise RegistryError(f"Curated file not found for '{record.document_id}': {path}")
    return path
