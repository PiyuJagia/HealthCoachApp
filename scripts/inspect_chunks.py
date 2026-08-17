"""Inspect Markdown chunking for registry-backed curated documents."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.documents import Document

from rag.chunker import TINY_CHUNK_THRESHOLD, chunk_markdown_document, is_heading_only_chunk
from rag.registry import (
    get_source_record,
    list_registered_sources,
    resolve_curated_path,
)
from rag.schemas import SourceRecord

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PREVIEW_LENGTH = 400
SEPARATOR = "=" * 72

PHASE_C2_BASELINE = {
    "hhs_physical_activity_guidelines_2e": {
        "total_chunks": 304,
        "min_chunk_length": 26,
        "avg_chunk_length": 769.4,
        "tiny_chunks": 19,
        "heading_only_chunks": 13,
        "missing_headings": 0,
        "yaml_only_chunks": 0,
    },
    "healthcoach_trend_detection": {
        "total_chunks": 16,
        "min_chunk_length": 102,
        "avg_chunk_length": 780.1,
        "tiny_chunks": 1,
        "heading_only_chunks": 0,
        "missing_headings": 1,
        "yaml_only_chunks": 1,
    },
    "healthcoach_correlation_modeling": {
        "total_chunks": 18,
        "min_chunk_length": 26,
        "avg_chunk_length": 789.1,
        "tiny_chunks": 1,
        "heading_only_chunks": 1,
        "missing_headings": 1,
        "yaml_only_chunks": 1,
    },
    "healthcoach_safety_scope_escalation": {
        "total_chunks": 15,
        "min_chunk_length": 74,
        "avg_chunk_length": 738.7,
        "tiny_chunks": 1,
        "heading_only_chunks": 1,
        "missing_headings": 1,
        "yaml_only_chunks": 1,
    },
}


@dataclass
class QualityFlag:
    category: str
    severity: str
    detail: str


@dataclass
class FrontmatterReport:
    present: bool
    first_chunk_index: int | None
    first_chunk_length: int | None
    combined_with_body: bool
    standalone_yaml_chunk: bool
    tiny_frontmatter_chunk: bool
    likely_retrieval_risk: bool
    severity: str
    detail: str


@dataclass
class DocumentInspection:
    record: SourceRecord
    source_path: Path
    character_count: int
    word_count: int
    documents: list[Document]
    tiny_chunks: int
    missing_headings: int
    suspicious_tiny_chunks: int
    frontmatter: FrontmatterReport | None
    quality_flags: list[QualityFlag] = field(default_factory=list)
    quality_status: str = "good"


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def has_yaml_frontmatter(text: str) -> bool:
    return text.lstrip().startswith("---\n")


def count_yaml_only_chunks(documents: list[Document]) -> int:
    count = 0
    for document in documents:
        text = document.page_content.strip()
        if text.startswith("---") and "doc_id:" in text:
            count += 1
    return count


def analyze_frontmatter(text: str, documents: list[Document]) -> FrontmatterReport | None:
    if not has_yaml_frontmatter(text) or not documents:
        return None

    yaml_only_chunks = count_yaml_only_chunks(documents)
    supplemental_present = any(document.metadata.get("corpus_doc_id") for document in documents)
    first = documents[0]
    first_text = first.page_content
    standalone = yaml_only_chunks > 0
    combined = not standalone and supplemental_present
    tiny = standalone and len(first_text) < TINY_CHUNK_THRESHOLD

    if standalone:
        severity = "likely retrieval risk"
        detail = "YAML frontmatter still appears in chunk page_content."
    elif supplemental_present:
        severity = "cosmetic"
        detail = "YAML frontmatter parsed into supplemental metadata and excluded from page_content."
    else:
        severity = "worth reviewing"
        detail = "YAML frontmatter detected in source but supplemental metadata was not attached."

    return FrontmatterReport(
        present=True,
        first_chunk_index=1 if standalone else None,
        first_chunk_length=len(first_text) if standalone else None,
        combined_with_body=combined,
        standalone_yaml_chunk=standalone,
        tiny_frontmatter_chunk=tiny,
        likely_retrieval_risk=standalone,
        severity=severity,
        detail=detail,
    )


def count_heading_only_chunks(documents: list[Document]) -> int:
    return sum(1 for document in documents if is_heading_only_chunk(document.page_content))


def inspect_documents(text: str, documents: list[Document]) -> tuple[int, int, int]:
    tiny_chunks = 0
    missing_headings = 0
    suspicious_tiny = 0

    for index, document in enumerate(documents):
        length = len(document.page_content)
        heading = str(document.metadata.get("section_heading", "")).strip()

        if length < TINY_CHUNK_THRESHOLD:
            tiny_chunks += 1

        if not heading:
            missing_headings += 1

        if is_heading_only_chunk(document.page_content):
            suspicious_tiny += 1

        if index > 0:
            previous = documents[index - 1].page_content
            current = document.page_content
            overlap = _shared_boundary(previous, current)
            if overlap and overlap == previous[-len(overlap) :]:
                if len(overlap) > 300:
                    continue

    return tiny_chunks, missing_headings, suspicious_tiny


def _shared_boundary(first: str, second: str, min_len: int = 20) -> str | None:
    for size in range(min(len(first), len(second), 120), min_len - 1, -1):
        candidate = first[-size:]
        if candidate and candidate in second:
            return candidate
    return None


def collect_quality_flags(
    record: SourceRecord,
    text: str,
    documents: list[Document],
    frontmatter: FrontmatterReport | None,
) -> list[QualityFlag]:
    flags: list[QualityFlag] = []

    if frontmatter and frontmatter.present:
        flags.append(
            QualityFlag(
                category="yaml_frontmatter",
                severity=frontmatter.severity,
                detail=frontmatter.detail,
            )
        )

    if "verification_status=needs_verification" in record.notes:
        flags.append(
            QualityFlag(
                category="registry_verification",
                severity="worth reviewing",
                detail="Registry notes mark verification_status=needs_verification.",
            )
        )

    tiny_chunks, missing_headings, suspicious_tiny = inspect_documents(text, documents)

    if tiny_chunks:
        flags.append(
            QualityFlag(
                category="tiny_chunks",
                severity="worth reviewing" if tiny_chunks <= 3 else "likely retrieval risk",
                detail=f"{tiny_chunks} chunk(s) under {TINY_CHUNK_THRESHOLD} characters.",
            )
        )

    if suspicious_tiny:
        flags.append(
            QualityFlag(
                category="heading_only_chunks",
                severity="worth reviewing",
                detail=f"{suspicious_tiny} heading-only or suspiciously tiny chunk(s) detected.",
            )
        )

    if missing_headings > len(documents) * 0.4:
        flags.append(
            QualityFlag(
                category="missing_headings",
                severity="worth reviewing",
                detail=f"{missing_headings} chunk(s) without section_heading.",
            )
        )

    if "| --- |" in text:
        flags.append(
            QualityFlag(
                category="markdown_tables",
                severity="cosmetic",
                detail="Markdown tables present; verify table rows split cleanly.",
            )
        )

    if "```" in text:
        flags.append(
            QualityFlag(
                category="fenced_code",
                severity="worth reviewing",
                detail="Fenced code blocks present; may split across chunks.",
            )
        )

    max_length = max(len(document.page_content) for document in documents)
    if max_length > 1150:
        flags.append(
            QualityFlag(
                category="large_chunks",
                severity="cosmetic",
                detail=f"Maximum chunk length is {max_length}; near chunk_size limit.",
            )
        )

    if record.document_id.startswith("hhs_"):
        if "Figure " in text or "| --- |" in text:
            flags.append(
                QualityFlag(
                    category="pdf_curation_artifacts",
                    severity="worth reviewing",
                    detail="HHS curated document contains figure references and/or tables from PDF curation.",
                )
            )

    return flags


def determine_quality_status(flags: list[QualityFlag]) -> str:
    severities = {flag.severity for flag in flags}
    if "likely retrieval risk" in severities:
        return "review recommended"
    if "worth reviewing" in severities:
        return "review recommended"
    return "good"


def sample_chunk_indices(total_chunks: int) -> list[int]:
    if total_chunks <= 9:
        return list(range(1, total_chunks + 1))

    middle = total_chunks // 2
    candidates = [1, 2, 3, middle - 1, middle, middle + 1, total_chunks - 2, total_chunks - 1, total_chunks]
    unique = []
    for index in candidates:
        bounded = max(1, min(total_chunks, index))
        if bounded not in unique:
            unique.append(bounded)
    return unique


def inspect_record(record: SourceRecord, *, project_root: Path = PROJECT_ROOT) -> DocumentInspection:
    source_path = resolve_curated_path(record, project_root=project_root)
    text = source_path.read_text(encoding="utf-8")
    documents = chunk_markdown_document(
        source_path,
        source_record=record,
        project_root=project_root,
    )

    tiny_chunks, missing_headings, suspicious_tiny = inspect_documents(text, documents)
    frontmatter = analyze_frontmatter(text, documents)
    quality_flags = collect_quality_flags(record, text, documents, frontmatter)
    quality_status = determine_quality_status(quality_flags)

    return DocumentInspection(
        record=record,
        source_path=source_path,
        character_count=len(text),
        word_count=count_words(text),
        documents=documents,
        tiny_chunks=tiny_chunks,
        missing_headings=missing_headings,
        suspicious_tiny_chunks=suspicious_tiny,
        frontmatter=frontmatter,
        quality_flags=quality_flags,
        quality_status=quality_status,
    )


def inspect_document_id(document_id: str, *, project_root: Path = PROJECT_ROOT) -> DocumentInspection:
    record = get_source_record(document_id)
    return inspect_record(record, project_root=project_root)


def inspect_all_registered(*, project_root: Path = PROJECT_ROOT) -> list[DocumentInspection]:
    return [
        inspect_record(record, project_root=project_root)
        for record in list_registered_sources()
    ]


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _preview(text: str) -> str:
    if len(text) <= PREVIEW_LENGTH:
        return text
    return f"{text[:PREVIEW_LENGTH]}..."


def print_document_summary(result: DocumentInspection) -> None:
    lengths = [len(document.page_content) for document in result.documents]
    total_chunks = len(result.documents)

    print(SEPARATOR)
    print(f"document_id: {result.record.document_id}")
    print(f"filename: {result.source_path.name}")
    print(f"character count: {result.character_count}")
    print(f"word count: {result.word_count}")
    print(f"total chunks: {total_chunks}")
    print(f"minimum chunk length: {min(lengths)}")
    print(f"maximum chunk length: {max(lengths)}")
    print(f"average chunk length: {round(sum(lengths) / total_chunks, 1)}")
    print(f"chunks below {TINY_CHUNK_THRESHOLD} characters: {result.tiny_chunks}")
    print(f"chunks without section_heading: {result.missing_headings}")
    print(f"suspicious heading-only/tiny chunks: {result.suspicious_tiny_chunks}")
    print(f"quality_status: {result.quality_status}")

    if result.frontmatter:
        print("yaml frontmatter:")
        print(f"  present: {result.frontmatter.present}")
        print(f"  first_chunk_index: {result.frontmatter.first_chunk_index}")
        print(f"  first_chunk_length: {result.frontmatter.first_chunk_length}")
        print(f"  combined_with_body: {result.frontmatter.combined_with_body}")
        print(f"  standalone_yaml_chunk: {result.frontmatter.standalone_yaml_chunk}")
        print(f"  severity: {result.frontmatter.severity}")
        print(f"  detail: {result.frontmatter.detail}")

    if result.quality_flags:
        print("quality flags:")
        for flag in result.quality_flags:
            print(f"  - [{flag.severity}] {flag.category}: {flag.detail}")

    sample_indices = sample_chunk_indices(total_chunks)
    print(f"representative chunk indices: {sample_indices}")

    for index in sample_indices:
        document = result.documents[index - 1]
        metadata = document.metadata
        print("-" * 72)
        print(f"chunk_index: {metadata['chunk_index']}")
        print(f"total_chunks: {metadata['total_chunks']}")
        print(f"section_heading: {metadata['section_heading']}")
        print(f"character length: {len(document.page_content)}")
        print("metadata:")
        for key, value in metadata.items():
            print(f"  {key}: {value}")
        print("text preview:")
        print(_preview(document.page_content))
        print()


def print_before_after_comparison(results: list[DocumentInspection]) -> None:
    print(SEPARATOR)
    print("Phase C2 baseline vs Phase C3 after metrics")
    print(SEPARATOR)
    print(
        "document_id | metric | before | after | delta | direction"
    )
    for result in results:
        document_id = result.record.document_id
        baseline = PHASE_C2_BASELINE.get(document_id)
        if baseline is None:
            continue

        lengths = [len(document.page_content) for document in result.documents]
        after = {
            "total_chunks": len(result.documents),
            "min_chunk_length": min(lengths),
            "avg_chunk_length": round(sum(lengths) / len(lengths), 1),
            "tiny_chunks": result.tiny_chunks,
            "heading_only_chunks": count_heading_only_chunks(result.documents),
            "missing_headings": result.missing_headings,
            "yaml_only_chunks": count_yaml_only_chunks(result.documents),
        }

        for metric, before_value in baseline.items():
            after_value = after[metric]
            delta = after_value - before_value
            if metric in {"total_chunks", "tiny_chunks", "heading_only_chunks", "missing_headings", "yaml_only_chunks"}:
                direction = "improved" if delta < 0 else ("worse" if delta > 0 else "unchanged")
            elif metric == "min_chunk_length":
                direction = "improved" if delta > 0 else ("worse" if delta < 0 else "unchanged")
            elif metric == "avg_chunk_length":
                direction = "improved" if after_value >= before_value else "worse"
            else:
                direction = "unchanged"
            print(
                f"{document_id} | {metric} | {before_value} | {after_value} | {delta:+} | {direction}"
            )


def print_cross_document_summary(results: list[DocumentInspection]) -> None:
    print(SEPARATOR)
    print("Cross-document summary")
    print(SEPARATOR)
    print(
        "document_id | word_count | chunk_count | avg_chunk_length | tiny_chunks | "
        "missing_headings | frontmatter_issue | quality_status"
    )
    for result in results:
        frontmatter_issue = "none"
        if result.frontmatter and result.frontmatter.present:
            frontmatter_issue = result.frontmatter.severity
        lengths = [len(document.page_content) for document in result.documents]
        avg_length = round(sum(lengths) / len(lengths), 1)
        print(
            f"{result.record.document_id} | {result.word_count} | {len(result.documents)} | "
            f"{avg_length} | {result.tiny_chunks} | {result.missing_headings} | "
            f"{frontmatter_issue} | {result.quality_status}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect curated Markdown chunking.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--document-id", help="Inspect one registry document_id.")
    group.add_argument("--all", action="store_true", help="Inspect all registered documents.")
    parser.set_defaults(all=False)
    return parser


def main() -> None:
    _configure_stdout()
    parser = build_parser()
    args = parser.parse_args()

    if args.document_id:
        results = [inspect_document_id(args.document_id)]
    elif args.all:
        results = inspect_all_registered()
    else:
        parser.error("Specify --document-id <document_id> or --all.")

    for result in results:
        print_document_summary(result)

    if len(results) > 1:
        print_cross_document_summary(results)
        print_before_after_comparison(results)


if __name__ == "__main__":
    main()
