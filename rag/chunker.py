"""Split curated Markdown into LangChain Document chunks."""

from __future__ import annotations

import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.schemas import SourceRecord

MARKDOWN_SEPARATORS = [
    "\n# ",
    "\n## ",
    "\n### ",
    "\n#### ",
    "\n\n",
    "\n",
    ". ",
    " ",
    "",
]

HEADING_PATTERN = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

REQUIRED_METADATA_KEYS = (
    "document_id",
    "source_title",
    "organization",
    "topic",
    "topic_category",
    "source_file",
    "document_type",
    "evidence_level",
    "version",
    "chunk_index",
    "total_chunks",
    "section_heading",
)


def _build_heading_index(text: str) -> list[tuple[int, str]]:
    """Return heading start positions and their visible titles."""
    return [(match.start(), match.group(2).strip()) for match in HEADING_PATTERN.finditer(text)]


def _section_heading_before(position: int, headings: list[tuple[int, str]]) -> str:
    """Return the nearest preceding Markdown heading, or an empty string."""
    section_heading = ""

    for heading_pos, heading_text in headings:
        if heading_pos <= position:
            section_heading = heading_text
        else:
            break

    return section_heading


def _find_chunk_positions(text: str, chunks: list[str]) -> list[int]:
    """Find each chunk's start position in the original text."""
    positions: list[int] = []
    search_start = 0

    for chunk in chunks:
        start = text.find(chunk, search_start)
        if start == -1:
            raise ValueError(
                "Could not locate a chunk in the source document. "
                "The splitter output may not match the original text."
            )

        positions.append(start)
        search_start = start + 1

    return positions


def _portable_source_path(path: Path, project_root: Path | None = None) -> str:
    """Return a forward-slash path relative to project_root or the current working directory."""
    if not path.is_absolute():
        return path.as_posix()

    resolved = path.resolve()
    bases: list[Path] = []

    if project_root is not None:
        bases.append(project_root.resolve())
    bases.append(Path.cwd().resolve())

    for base in bases:
        try:
            return resolved.relative_to(base).as_posix()
        except ValueError:
            continue

    raise ValueError(
        f"Could not derive a portable relative source path for: {path}. "
        "Pass a relative file_path or provide project_root."
    )


def chunk_markdown_text(
    text: str,
    *,
    document_id: str,
    source_title: str = "",
    organization: str = "",
    topic: str = "",
    topic_category: str = "",
    source_file: str = "",
    document_type: str = "",
    evidence_level: str = "",
    version: str = "",
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> list[Document]:
    """
    Split curated Markdown into LangChain Document objects.

    Chunk text is preserved exactly. Metadata includes document identity fields,
    registry metadata, and 1-based chunk_index values.
    """
    if not text.strip():
        raise ValueError("Text must not be blank.")

    if not document_id.strip():
        raise ValueError("document_id must not be blank.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=MARKDOWN_SEPARATORS,
        length_function=len,
    )

    chunk_texts = splitter.split_text(text)
    if not chunk_texts:
        raise ValueError("No chunks were produced from the provided text.")

    headings = _build_heading_index(text)
    chunk_starts = _find_chunk_positions(text, chunk_texts)
    total_chunks = len(chunk_texts)

    documents: list[Document] = []

    for index, (chunk_content, chunk_start) in enumerate(zip(chunk_texts, chunk_starts)):
        chunk_index = index + 1

        metadata: dict[str, str | int] = {
            "document_id": document_id,
            "source_title": source_title,
            "organization": organization,
            "topic": topic,
            "topic_category": topic_category,
            "source_file": source_file,
            "document_type": document_type,
            "evidence_level": evidence_level,
            "version": version,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "section_heading": _section_heading_before(chunk_start, headings),
        }

        documents.append(Document(page_content=chunk_content, metadata=metadata))

    return documents


def chunk_markdown_document(
    file_path: str | Path,
    *,
    source_record: SourceRecord,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    project_root: Path | None = None,
) -> list[Document]:
    """Read a curated Markdown file and delegate to chunk_markdown_text()."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Markdown file not found: {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"Markdown file is empty: {path}")

    return chunk_markdown_text(
        text,
        document_id=source_record.document_id,
        source_title=source_record.title,
        organization=source_record.organization,
        topic=source_record.topic,
        topic_category=source_record.topic_category,
        source_file=_portable_source_path(path, project_root),
        document_type=source_record.document_type,
        evidence_level=source_record.evidence_level,
        version=source_record.version,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
