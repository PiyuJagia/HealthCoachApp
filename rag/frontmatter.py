"""Parse YAML frontmatter from curated Markdown without mutating source files."""

from __future__ import annotations

import re
from typing import Any

import yaml

FRONTMATTER_PATTERN = re.compile(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", re.DOTALL)

# Registry identity fields are authoritative and must never be overwritten by YAML.
PROTECTED_METADATA_KEYS = frozenset(
    {
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
    }
)

# Whitelisted scalar frontmatter keys mapped to supplemental chunk metadata keys.
SCALAR_FIELD_MAP = {
    "doc_id": "corpus_doc_id",
    "layer": "layer",
    "domain": "domain",
    "evidence_grade": "evidence_grade",
    "verification_status": "verification_status",
    "last_reviewed": "last_reviewed",
}

# List fields serialized as deterministic pipe-delimited strings for Pinecone-safe metadata.
# Pinecone supports list[str] metadata, but LangChain Document metadata in this project uses
# str | int only, and pipe-delimited strings avoid client/version ambiguity.
LIST_FIELD_MAP = {
    "sources": "source_keys",
    "metrics": "metrics",
    "entities": "entities",
}


class FrontmatterError(ValueError):
    """Raised when YAML frontmatter is present but cannot be parsed safely."""


def _serialize_list(values: list[Any], *, field_name: str) -> str:
    if not values:
        return ""

    serialized: list[str] = []
    for item in values:
        if isinstance(item, (dict, list)):
            raise FrontmatterError(
                f"Frontmatter list field '{field_name}' contains nested values; "
                "only flat scalar lists are supported."
            )
        text = str(item).strip()
        if not text:
            raise FrontmatterError(f"Frontmatter list field '{field_name}' contains blank entries.")
        serialized.append(text)

    return "|".join(serialized)


def normalize_frontmatter_metadata(parsed: dict[str, Any]) -> dict[str, str]:
    """Convert whitelisted YAML frontmatter into supplemental chunk metadata."""
    supplemental: dict[str, str] = {}

    for yaml_key, metadata_key in SCALAR_FIELD_MAP.items():
        if yaml_key not in parsed:
            continue

        value = parsed[yaml_key]
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            raise FrontmatterError(
                f"Frontmatter field '{yaml_key}' must be a scalar value, got {type(value).__name__}."
            )
        supplemental[metadata_key] = str(value).strip()

    for yaml_key, metadata_key in LIST_FIELD_MAP.items():
        if yaml_key not in parsed:
            continue

        value = parsed[yaml_key]
        if value is None:
            continue
        if isinstance(value, list):
            supplemental[metadata_key] = _serialize_list(value, field_name=yaml_key)
        elif isinstance(value, str):
            supplemental[metadata_key] = value.strip()
        else:
            raise FrontmatterError(
                f"Frontmatter list field '{yaml_key}' must be a list or string, "
                f"got {type(value).__name__}."
            )

    return supplemental


def extract_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """
    Detect and parse leading YAML frontmatter.

    Returns supplemental metadata and body text with frontmatter removed from chunking input.
    When no frontmatter is present, returns ({}, original text unchanged).
    """
    if not text.lstrip().startswith("---"):
        return {}, text

    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        raise FrontmatterError(
            "Document begins with '---' but is missing a valid closing '---' frontmatter delimiter."
        )

    yaml_block = match.group(1)
    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"Malformed YAML frontmatter: {exc}") from exc

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise FrontmatterError("YAML frontmatter must be a top-level mapping.")

    body = text[match.end() :]
    if body.startswith("\r\n"):
        body = body[2:]
    elif body.startswith("\n"):
        body = body[1:]

    supplemental = normalize_frontmatter_metadata(parsed)
    return supplemental, body
