"""Split curated Markdown into LangChain Document chunks."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.frontmatter import PROTECTED_METADATA_KEYS, extract_frontmatter
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
HEADING_LINE_PATTERN = re.compile(r"^#{1,4}\s+\S")

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

TINY_CHUNK_THRESHOLD = 150
MERGE_SIZE_TOLERANCE = 50
SEPARATOR_LINES = frozenset({"---", "***", "___"})


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


def is_heading_only_chunk(text: str) -> bool:
    """
    Detect chunks that contain only Markdown heading line(s) plus trivial separators.

    Examples:
      # Chapter 4. Active Adults
      ### Recovery and autonomic
    """
    stripped = text.strip()
    if not stripped:
        return False

    non_separator_lines = [
        line.strip()
        for line in stripped.splitlines()
        if line.strip() and line.strip() not in SEPARATOR_LINES
    ]
    if not non_separator_lines:
        return False

    heading_lines = sum(1 for line in non_separator_lines if HEADING_LINE_PATTERN.match(line))
    return heading_lines >= len(non_separator_lines)


def is_meaningful_short_standalone(text: str) -> bool:
    """
    Detect short chunks that intentionally stand alone and should not be auto-merged.

    Example retained chunk:
      ## 6. Test cases for CI

      Every build runs these. A failure blocks release.
    """
    stripped = text.strip()
    if len(stripped) >= TINY_CHUNK_THRESHOLD:
        return False

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    heading_lines = [line for line in lines if HEADING_LINE_PATTERN.match(line)]
    body_lines = [line for line in lines if line not in heading_lines and line not in SEPARATOR_LINES]

    if not body_lines:
        return False

    body_text = " ".join(body_lines).strip()
    return body_text.endswith((".", "!", "?", '"', "'"))


def _heading_from_chunk_text(text: str) -> str:
    for line in text.splitlines():
        match = HEADING_PATTERN.match(line.strip())
        if match:
            return match.group(2).strip()
    return ""


def _find_suffix_prefix_overlap(first: str, second: str, *, max_overlap: int = 200) -> int:
    limit = min(len(first), len(second), max_overlap)
    for size in range(limit, 0, -1):
        if first[-size:] == second[:size]:
            return size
    return 0


def _join_chunk_text(first: str, second: str) -> str:
    """Join adjacent chunks while deduplicating splitter overlap at the boundary."""
    overlap_len = _find_suffix_prefix_overlap(first, second)
    if overlap_len > 0:
        return first + second[overlap_len:]

    if first.endswith(("\n", "\r\n")) or second.startswith(("\n", "\r\n")):
        return first.rstrip("\r\n") + "\n\n" + second.lstrip("\r\n")
    return first + "\n\n" + second


def _can_merge(first: Document, second: Document, *, chunk_size: int) -> bool:
    joined = _join_chunk_text(first.page_content, second.page_content)
    return len(joined) <= chunk_size + MERGE_SIZE_TOLERANCE


def _merge_chunks(first: Document, second: Document, *, heading_source: str) -> Document:
    merged_content = _join_chunk_text(first.page_content, second.page_content)
    metadata = deepcopy(first.metadata)

    if heading_source == "first":
        section_heading = _heading_from_chunk_text(first.page_content) or str(
            first.metadata.get("section_heading", "")
        )
    else:
        section_heading = str(second.metadata.get("section_heading", "")) or _heading_from_chunk_text(
            second.page_content
        ) or _heading_from_chunk_text(first.page_content) or str(first.metadata.get("section_heading", ""))

    metadata["section_heading"] = section_heading
    return Document(page_content=merged_content, metadata=metadata)


def _should_merge_tiny_forward(current: Document, following: Document) -> bool:
    text = current.page_content.strip()
    if len(text) >= TINY_CHUNK_THRESHOLD:
        return False
    if is_heading_only_chunk(text) or is_meaningful_short_standalone(text):
        return False

    current_heading = str(current.metadata.get("section_heading", "")).strip()
    next_heading = str(following.metadata.get("section_heading", "")).strip()

    if HEADING_LINE_PATTERN.match(text.splitlines()[0].strip() if text.splitlines() else ""):
        return True
    if current_heading and current_heading == next_heading:
        return True
    if not text.endswith((".", "!", "?", ":", '"', "'")):
        return True
    return False


def _should_merge_tiny_backward(previous: Document, current: Document) -> bool:
    text = current.page_content.strip()
    if len(text) >= TINY_CHUNK_THRESHOLD:
        return False
    if is_heading_only_chunk(text) or is_meaningful_short_standalone(text):
        return False

    previous_heading = str(previous.metadata.get("section_heading", "")).strip()
    current_heading = str(current.metadata.get("section_heading", "")).strip()

    if previous_heading and previous_heading == current_heading:
        return True
    if not text.endswith((".", "!", "?", ":", '"', "'")):
        return True
    return False


def post_process_chunks(
    documents: list[Document],
    *,
    chunk_size: int,
) -> list[Document]:
    """
    Merge heading-only and safe tiny chunks, then recompute chunk indexes.

    Merge rules:
    1. Heading-only chunk + following chunk when combined length <= chunk_size + tolerance.
    2. Tiny fragment (<150 chars) + following chunk when forward merge is semantically cleaner.
    3. Previous chunk + tiny fragment when backward merge is cleaner and forward did not apply.
    4. Never merge meaningful short standalone sections merely to increase chunk size.
    """
    docs = [Document(page_content=document.page_content, metadata=dict(document.metadata)) for document in documents]

    changed = True
    while changed:
        changed = False
        index = 0
        merged_pass: list[Document] = []

        while index < len(docs):
            current = docs[index]

            if index + 1 < len(docs):
                following = docs[index + 1]

                if is_heading_only_chunk(current.page_content) and _can_merge(current, following, chunk_size=chunk_size):
                    merged_pass.append(_merge_chunks(current, following, heading_source="first"))
                    index += 2
                    changed = True
                    continue

                if _should_merge_tiny_forward(current, following) and _can_merge(
                    current, following, chunk_size=chunk_size
                ):
                    merged_pass.append(_merge_chunks(current, following, heading_source="second"))
                    index += 2
                    changed = True
                    continue

            if merged_pass and _should_merge_tiny_backward(merged_pass[-1], current) and _can_merge(
                merged_pass[-1], current, chunk_size=chunk_size
            ):
                merged_pass[-1] = _merge_chunks(merged_pass[-1], current, heading_source="first")
                index += 1
                changed = True
                continue

            merged_pass.append(current)
            index += 1

        docs = merged_pass

    return reindex_chunks(docs)


def reindex_chunks(documents: list[Document]) -> list[Document]:
    """Recompute chunk_index and total_chunks after post-processing merges."""
    total_chunks = len(documents)
    reindexed: list[Document] = []

    for index, document in enumerate(documents, start=1):
        metadata = dict(document.metadata)
        metadata["chunk_index"] = index
        metadata["total_chunks"] = total_chunks
        reindexed.append(Document(page_content=document.page_content, metadata=metadata))

    return reindexed


def _attach_supplemental_metadata(
    metadata: dict[str, str | int],
    supplemental: dict[str, str],
) -> dict[str, str | int]:
    for key, value in supplemental.items():
        if key in PROTECTED_METADATA_KEYS:
            continue
        if key in metadata:
            continue
        metadata[key] = value
    return metadata


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

    YAML frontmatter is parsed and excluded from page_content. Whitelisted YAML fields
    are attached as supplemental metadata. Heading-only and safe tiny chunks are merged
    after splitting. Registry metadata remains authoritative.
    """
    if not text.strip():
        raise ValueError("Text must not be blank.")

    if not document_id.strip():
        raise ValueError("document_id must not be blank.")

    supplemental_metadata, chunking_text = extract_frontmatter(text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=MARKDOWN_SEPARATORS,
        length_function=len,
    )

    chunk_texts = splitter.split_text(chunking_text)
    if not chunk_texts:
        raise ValueError("No chunks were produced from the provided text.")

    headings = _build_heading_index(chunking_text)
    chunk_starts = _find_chunk_positions(chunking_text, chunk_texts)

    documents: list[Document] = []

    for chunk_content, chunk_start in zip(chunk_texts, chunk_starts):
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
            "chunk_index": 0,
            "total_chunks": 0,
            "section_heading": _section_heading_before(chunk_start, headings),
        }
        metadata = _attach_supplemental_metadata(metadata, supplemental_metadata)

        documents.append(Document(page_content=chunk_content, metadata=metadata))

    documents = post_process_chunks(documents, chunk_size=chunk_size)
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
