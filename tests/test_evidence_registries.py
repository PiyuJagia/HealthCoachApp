"""Tests for external evidence and claim mapping registries."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rag.claim_evidence_registry import ClaimEvidenceRegistryError, load_claim_evidence_registry
from rag.evidence_registry import EvidenceRegistryError, load_evidence_registry

EVIDENCE_HEADER = (
    "source_key,title,authors_or_organization,publication_year,source_type,doi,pmid,"
    "source_url,verification_status,notes"
)
CLAIM_HEADER = (
    "claim_id,document_id,section,claim_summary,source_key,support_type,claim_grade,"
    "causal_class,within_person_valid,product_level,evidence_measurement,"
    "product_measurement,verification_status,verified_date,notes"
)
SOURCE_HEADER = (
    "document_id,title,organization,topic,topic_category,source_url,"
    "publication_date,retrieval_date,document_type,evidence_level,"
    "local_filename,version,approved_for_ingestion,notes,curated_path"
)


def _write_temp(content: str) -> Path:
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


def _sample_source_registry() -> Path:
    return _write_temp(
        "\n".join(
            [
                SOURCE_HEADER,
                "healthcoach_correlation_modeling,Title,,topic,integrated_health,,,,curated_evidence_synthesis,curated_evidence_synthesis,healthcoach_correlation_modeling.md,L2-CR-001,FALSE,notes,",
            ]
        )
        + "\n"
    )


def _sample_evidence_registry(**overrides: str) -> Path:
    values = {
        "source_key": "Shaffer-2017",
        "title": "HRV Overview",
        "authors_or_organization": "Shaffer F",
        "publication_year": "2017",
        "source_type": "review",
        "doi": "10.3389/fpubh.2017.00258",
        "pmid": "28744322",
        "source_url": "https://example.org/shaffer",
        "verification_status": "verified",
        "notes": "Sample source.",
    }
    values.update(overrides)
    ordered = [values[column] for column in EVIDENCE_HEADER.split(",")]
    return _write_temp(f"{EVIDENCE_HEADER}\n{','.join(ordered)}\n")


def _sample_claim_registry(**overrides: str) -> Path:
    values = {
        "claim_id": "C-32",
        "document_id": "healthcoach_correlation_modeling",
        "section": "5. Relationship catalogue",
        "claim_summary": "Aerobic training frequency lowers resting heart rate over weeks.",
        "source_key": "Shaffer-2017",
        "support_type": "partial",
        "claim_grade": "B",
        "causal_class": "adaptation",
        "within_person_valid": "conditional",
        "product_level": "relationship_catalogue",
        "evidence_measurement": "clinical RHR",
        "product_measurement": "watch RHR",
        "verification_status": "verified",
        "verified_date": "2026-08-16",
        "notes": "Starter claim.",
    }
    values.update(overrides)
    ordered = [values[column] for column in CLAIM_HEADER.split(",")]
    return _write_temp(f"{CLAIM_HEADER}\n{','.join(ordered)}\n")


class EvidenceRegistryTests(unittest.TestCase):
    def test_valid_source_parses_successfully(self) -> None:
        registry_path = _sample_evidence_registry()
        self.addCleanup(registry_path.unlink)

        records = load_evidence_registry(registry_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_key, "Shaffer-2017")
        self.assertEqual(records[0].verification_status, "verified")

    def test_duplicate_source_key_is_rejected(self) -> None:
        row = ",".join(
            [
                "Shaffer-2017",
                "HRV Overview",
                "Shaffer F",
                "2017",
                "review",
                "",
                "",
                "https://example.org",
                "verified",
                "notes",
            ]
        )
        registry_path = _write_temp(f"{EVIDENCE_HEADER}\n{row}\n{row}\n")
        self.addCleanup(registry_path.unlink)

        with self.assertRaises(EvidenceRegistryError):
            load_evidence_registry(registry_path)

    def test_malformed_verification_status_is_rejected(self) -> None:
        registry_path = _sample_evidence_registry(verification_status="maybe")
        self.addCleanup(registry_path.unlink)

        with self.assertRaises(EvidenceRegistryError):
            load_evidence_registry(registry_path)


class ClaimEvidenceRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_registry_path = _sample_source_registry()
        self.evidence_registry_path = _sample_evidence_registry()
        self.addCleanup(self.source_registry_path.unlink)
        self.addCleanup(self.evidence_registry_path.unlink)

    def test_valid_claim_mapping_parses_successfully(self) -> None:
        claim_registry_path = _sample_claim_registry()
        self.addCleanup(claim_registry_path.unlink)

        records = load_claim_evidence_registry(
            claim_registry_path,
            source_registry_path=self.source_registry_path,
            evidence_registry_path=self.evidence_registry_path,
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].claim_id, "C-32")
        self.assertEqual(records[0].support_type, "partial")

    def test_unknown_document_id_is_rejected(self) -> None:
        claim_registry_path = _sample_claim_registry(document_id="missing_doc")
        self.addCleanup(claim_registry_path.unlink)

        with self.assertRaises(ClaimEvidenceRegistryError):
            load_claim_evidence_registry(
                claim_registry_path,
                source_registry_path=self.source_registry_path,
                evidence_registry_path=self.evidence_registry_path,
            )

    def test_unknown_source_key_is_rejected(self) -> None:
        claim_registry_path = _sample_claim_registry(source_key="Missing-Source")
        self.addCleanup(claim_registry_path.unlink)

        with self.assertRaises(ClaimEvidenceRegistryError):
            load_claim_evidence_registry(
                claim_registry_path,
                source_registry_path=self.source_registry_path,
                evidence_registry_path=self.evidence_registry_path,
            )

    def test_invalid_support_type_is_rejected(self) -> None:
        claim_registry_path = _sample_claim_registry(support_type="guess")
        self.addCleanup(claim_registry_path.unlink)

        with self.assertRaises(ClaimEvidenceRegistryError):
            load_claim_evidence_registry(
                claim_registry_path,
                source_registry_path=self.source_registry_path,
                evidence_registry_path=self.evidence_registry_path,
            )

    def test_invalid_within_person_valid_is_rejected(self) -> None:
        claim_registry_path = _sample_claim_registry(within_person_valid="maybe")
        self.addCleanup(claim_registry_path.unlink)

        with self.assertRaises(ClaimEvidenceRegistryError):
            load_claim_evidence_registry(
                claim_registry_path,
                source_registry_path=self.source_registry_path,
                evidence_registry_path=self.evidence_registry_path,
            )

    def test_duplicate_claim_source_mapping_is_rejected(self) -> None:
        row = ",".join(
            [
                "C-32",
                "healthcoach_correlation_modeling",
                "section",
                "summary",
                "Shaffer-2017",
                "partial",
                "B",
                "adaptation",
                "conditional",
                "relationship_catalogue",
                "clinical RHR",
                "watch RHR",
                "verified",
                "2026-08-16",
                "notes",
            ]
        )
        claim_registry_path = _write_temp(f"{CLAIM_HEADER}\n{row}\n{row}\n")
        self.addCleanup(claim_registry_path.unlink)

        with self.assertRaises(ClaimEvidenceRegistryError):
            load_claim_evidence_registry(
                claim_registry_path,
                source_registry_path=self.source_registry_path,
                evidence_registry_path=self.evidence_registry_path,
            )


if __name__ == "__main__":
    unittest.main()
