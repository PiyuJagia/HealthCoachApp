"""Tests for knowledge source registry parsing and validation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rag.registry import (
    RegistryError,
    get_approved_sources,
    get_source_record,
    load_registry,
    resolve_curated_path,
    validate_all_curated_files,
    validate_curated_file_exists,
)
from rag.schemas import SourceRecord

HEADER = (
    "document_id,title,organization,topic,topic_category,source_url,"
    "publication_date,retrieval_date,document_type,evidence_level,"
    "local_filename,version,approved_for_ingestion,notes,curated_path"
)


def _write_registry(content: str) -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".csv",
        delete=False,
        newline="",
    )
    with handle:
        handle.write(content)
    return Path(handle.name)


def _sample_row(**overrides: str) -> str:
    values = {
        "document_id": "hhs_physical_activity_guidelines_2e",
        "title": "Physical Activity Guidelines for Americans",
        "organization": "HHS",
        "topic": "physical_activity",
        "topic_category": "exercise",
        "source_url": "https://example.org/guidelines",
        "publication_date": "2018",
        "retrieval_date": "2026-08-01",
        "document_type": "guideline",
        "evidence_level": "authoritative_guideline",
        "local_filename": "hhs_physical_activity_guidelines_2e.md",
        "version": "2e",
        "approved_for_ingestion": "TRUE",
        "notes": "Curated from official guidelines.",
        "curated_path": "",
    }
    values.update(overrides)
    ordered = [values[column] for column in HEADER.split(",")]
    return ",".join(ordered)


class RegistryTests(unittest.TestCase):
    def test_valid_registry_row_parses_successfully(self) -> None:
        registry_path = _write_registry(f"{HEADER}\n{_sample_row()}\n")
        self.addCleanup(registry_path.unlink)

        records = load_registry(registry_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].document_id, "hhs_physical_activity_guidelines_2e")
        self.assertEqual(records[0].title, "Physical Activity Guidelines for Americans")

    def test_true_approval_becomes_python_true(self) -> None:
        registry_path = _write_registry(f"{HEADER}\n{_sample_row(approved_for_ingestion='TRUE')}\n")
        self.addCleanup(registry_path.unlink)

        record = load_registry(registry_path)[0]
        self.assertIs(record.approved_for_ingestion, True)

    def test_false_approval_becomes_python_false(self) -> None:
        registry_path = _write_registry(f"{HEADER}\n{_sample_row(approved_for_ingestion='FALSE')}\n")
        self.addCleanup(registry_path.unlink)

        record = load_registry(registry_path)[0]
        self.assertIs(record.approved_for_ingestion, False)

    def test_duplicate_document_id_is_rejected(self) -> None:
        registry_path = _write_registry(
            f"{HEADER}\n{_sample_row()}\n{_sample_row(document_id='hhs_physical_activity_guidelines_2e')}\n"
        )
        self.addCleanup(registry_path.unlink)

        with self.assertRaises(RegistryError):
            load_registry(registry_path)

    def test_invalid_document_id_format_is_rejected(self) -> None:
        registry_path = _write_registry(f"{HEADER}\n{_sample_row(document_id='Invalid-ID')}\n")
        self.addCleanup(registry_path.unlink)

        with self.assertRaises(RegistryError):
            load_registry(registry_path)

    def test_invalid_approval_value_is_rejected(self) -> None:
        registry_path = _write_registry(
            f"{HEADER}\n{_sample_row(approved_for_ingestion='MAYBE')}\n"
        )
        self.addCleanup(registry_path.unlink)

        with self.assertRaises(RegistryError):
            load_registry(registry_path)

    def test_get_approved_sources_returns_only_approved_rows(self) -> None:
        registry_path = _write_registry(
            "\n".join(
                [
                    HEADER,
                    _sample_row(
                        document_id="approved_doc",
                        approved_for_ingestion="TRUE",
                    ),
                    _sample_row(
                        document_id="pending_doc",
                        approved_for_ingestion="FALSE",
                        local_filename="pending_doc.md",
                    ),
                ]
            )
            + "\n"
        )
        self.addCleanup(registry_path.unlink)

        approved = get_approved_sources(registry_path=registry_path)
        self.assertEqual([record.document_id for record in approved], ["approved_doc"])

    def test_curated_path_defaults_when_blank(self) -> None:
        record = SourceRecord(
            document_id="sample_doc",
            title="Sample",
            organization="Org",
            topic="topic",
            topic_category="exercise",
            source_url="",
            publication_date="",
            retrieval_date="",
            document_type="guideline",
            evidence_level="authoritative_guideline",
            local_filename="sample_doc.md",
            version="1",
            approved_for_ingestion=True,
            notes="",
            curated_path="",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolved = resolve_curated_path(record, project_root=root)
            self.assertEqual(resolved, root / "knowledge" / "curated" / "sample_doc.md")

    def test_explicit_curated_path_overrides_default(self) -> None:
        record = SourceRecord(
            document_id="sample_doc",
            title="Sample",
            organization="Org",
            topic="topic",
            topic_category="exercise",
            source_url="",
            publication_date="",
            retrieval_date="",
            document_type="guideline",
            evidence_level="authoritative_guideline",
            local_filename="sample_doc.md",
            version="1",
            approved_for_ingestion=True,
            notes="",
            curated_path="knowledge/curated/custom_location.md",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolved = resolve_curated_path(record, project_root=root)
            self.assertEqual(resolved, root / "knowledge" / "curated" / "custom_location.md")

    def test_validate_curated_file_exists_reports_missing_file(self) -> None:
        record = SourceRecord(
            document_id="missing_doc",
            title="Missing",
            organization="Org",
            topic="topic",
            topic_category="exercise",
            source_url="",
            publication_date="",
            retrieval_date="",
            document_type="guideline",
            evidence_level="authoritative_guideline",
            local_filename="missing_doc.md",
            version="1",
            approved_for_ingestion=True,
            notes="",
            curated_path="",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(RegistryError):
                validate_curated_file_exists(record, project_root=Path(temp_dir))

    def test_get_source_record_returns_matching_row(self) -> None:
        registry_path = _write_registry(f"{HEADER}\n{_sample_row()}\n")
        self.addCleanup(registry_path.unlink)

        record = get_source_record(
            "hhs_physical_activity_guidelines_2e",
            registry_path=registry_path,
        )
        self.assertEqual(record.organization, "HHS")

    def test_validate_all_curated_files_resolves_project_registry(self) -> None:
        paths = validate_all_curated_files()
        self.assertEqual(len(paths), 4)
        self.assertTrue(all(path.is_file() for path in paths))

    def test_project_registry_has_three_approved_sources(self) -> None:
        approved = get_approved_sources()
        self.assertEqual(len(approved), 3)
        approved_ids = {record.document_id for record in approved}
        self.assertEqual(
            approved_ids,
            {
                "hhs_physical_activity_guidelines_2e",
                "healthcoach_trend_detection",
                "healthcoach_safety_scope_escalation",
            },
        )
        self.assertFalse(
            any(record.document_id == "healthcoach_correlation_modeling" for record in approved)
        )


if __name__ == "__main__":
    unittest.main()
