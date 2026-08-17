"""Relationship-aware chunking for L2-CR Section 5 active relationship blocks."""

from __future__ import annotations

import re
from copy import deepcopy

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.chunker import (
    MARKDOWN_SEPARATORS,
    _attach_supplemental_metadata,
    _build_heading_index,
    _find_chunk_positions,
    _section_heading_before,
    post_process_chunks,
    reindex_chunks,
)
from rag.relationship_policy import (
    HIGH_TRANSFER_RISK_RELATIONSHIPS,
    MODIFIER_ONLY_RELATIONSHIPS,
    NO_RECOMMENDATION_RELATIONSHIPS,
    can_generate_recommendation,
    load_relationship_policies,
)

L2CR_DOCUMENT_ID = "healthcoach_correlation_modeling"

RELATIONSHIP_HEADING_PATTERN = re.compile(r"^### (R-\d{2}) · (.+)$", re.MULTILINE)
SECTION_6_PATTERN = re.compile(r"^## 6\. DEFERRED", re.MULTILINE)
FIELD_PATTERN = re.compile(r"- \*\*([^:*]+):\*\*\s*(.+)", re.MULTILINE)
EVIDENCE_GRADE_PATTERN = re.compile(r"^([ABC])\s*([−\-–])?", re.MULTILINE)
MAX_LEVEL_PATTERN = re.compile(r"(\d+)")
TRANSFER_RISK_PATTERN = re.compile(r"\b(high|moderate|low)\b", re.IGNORECASE)


def _clean_field_value(value: str) -> str:
    return value.strip().strip("*").strip()


def _parse_evidence_strength(evidence_raw: str) -> str:
    cleaned = _clean_field_value(evidence_raw)
    evidence_match = EVIDENCE_GRADE_PATTERN.search(cleaned)
    if evidence_match:
        grade = evidence_match.group(1)
        minus = evidence_match.group(2)
        if minus:
            return f"{grade}−"
        return grade
    return cleaned.split("—")[0].split("-")[0].strip()

RELATIONSHIP_BULLET_SEPARATORS = [
    "\n\n> ",
    "\n\n> **",
    "\n\n",
    "\n- **",
    "\n",
    ". ",
    " ",
    "",
]

SAFETY_ENVELOPE_MARKER = "[L2-CR Safety Envelope |"


def uses_relationship_aware_chunking(document_id: str) -> bool:
    return document_id.strip() == L2CR_DOCUMENT_ID


def extract_relationship_blocks(text: str) -> tuple[str, dict[str, str], str]:
    """Split L2-CR body into prefix, R-01…R-09 blocks, and suffix."""
    first_relationship = RELATIONSHIP_HEADING_PATTERN.search(text)
    if first_relationship is None:
        return text, {}, ""

    prefix = text[: first_relationship.start()]
    section_six = SECTION_6_PATTERN.search(text)
    relationship_end = section_six.start() if section_six else len(text)
    relationship_region = text[first_relationship.start() : relationship_end]
    suffix = text[relationship_end:] if section_six else ""

    matches = list(RELATIONSHIP_HEADING_PATTERN.finditer(relationship_region))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        relationship_id = match.group(1)
        block_start = match.start()
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(relationship_region)
        blocks[relationship_id] = relationship_region[block_start:block_end].strip()

    return prefix, blocks, suffix


def _parse_relationship_fields(block: str) -> dict[str, str]:
    fields = {
        name.strip(): _clean_field_value(value)
        for name, value in FIELD_PATTERN.findall(block)
    }

    evidence_strength = _parse_evidence_strength(fields.get("evidence_strength", ""))

    transfer_raw = fields.get("measurement_transfer_risk", "")
    transfer_match = TRANSFER_RISK_PATTERN.search(transfer_raw)
    measurement_transfer_risk = transfer_match.group(1).lower() if transfer_match else transfer_raw.lower()

    max_level_raw = fields.get("max_product_level", "")
    max_level_match = MAX_LEVEL_PATTERN.search(max_level_raw)
    max_product_level = max_level_match.group(1) if max_level_match else max_level_raw

    status_raw = fields.get("status", "ACTIVE")
    relationship_status = "ACTIVE" if "ACTIVE" in status_raw.upper() else status_raw

    contradiction = fields.get("contradiction_conditions", "")
    primary_function = fields.get("primary function — SUPPRESSION", "")

    return {
        "evidence_strength": evidence_strength,
        "measurement_transfer_risk": measurement_transfer_risk,
        "max_product_level": max_product_level,
        "relationship_status": relationship_status,
        "contradiction_conditions": contradiction,
        "primary_function_suppression": primary_function,
    }


def _compact_contradiction_policy(
    relationship_id: str,
    *,
    contradiction_conditions: str,
    primary_function_suppression: str,
) -> str:
    if primary_function_suppression:
        return primary_function_suppression
    if relationship_id == "R-03":
        return (
            "Mandatory contradiction suppression when HRV rises alongside sustained "
            "higher training load."
        )
    if relationship_id == "R-08":
        return (
            "Suppress for low reported doses; do not generate alcohol advice. "
            + contradiction_conditions[:220]
        )
    return contradiction_conditions[:280]


def build_safety_envelope(
    relationship_id: str,
    *,
    parsed_fields: dict[str, str],
    section_title: str,
) -> str:
    policies = load_relationship_policies()
    policy = policies.get(relationship_id)
    recommendation_eligible = can_generate_recommendation(relationship_id)
    modifier_only = relationship_id in MODIFIER_ONLY_RELATIONSHIPS

    contradiction = _compact_contradiction_policy(
        relationship_id,
        contradiction_conditions=parsed_fields.get("contradiction_conditions", ""),
        primary_function_suppression=parsed_fields.get("primary_function_suppression", ""),
    )

    no_recommendation_note = ""
    if relationship_id in NO_RECOMMENDATION_RELATIONSHIPS:
        if relationship_id == "R-08":
            no_recommendation_note = "No alcohol advice permitted."
        else:
            no_recommendation_note = "Must not generate recommendations."

    high_transfer_note = ""
    if relationship_id in HIGH_TRANSFER_RISK_RELATIONSHIPS:
        high_transfer_note = "High measurement-transfer risk."

    lines = [
        f"{SAFETY_ENVELOPE_MARKER} {relationship_id}]",
        f"{section_title.strip()}",
        "Association only — not causal.",
        (
            f"Evidence: {parsed_fields.get('evidence_strength', '')} | "
            f"Transfer risk: {parsed_fields.get('measurement_transfer_risk', '')} | "
            f"Max level: {parsed_fields.get('max_product_level', '')} | "
            f"Recommendations: {'yes' if recommendation_eligible else 'no'}"
        ),
    ]
    if modifier_only:
        lines.append("Modifier/suppressor only — never a standalone correlation insight.")
    if high_transfer_note:
        lines.append(high_transfer_note)
    if no_recommendation_note:
        lines.append(no_recommendation_note)
    if contradiction:
        lines.append(f"Contradiction/suppression: {contradiction}")

    return "\n".join(lines)


def build_relationship_metadata(
    relationship_id: str,
    *,
    parsed_fields: dict[str, str],
    section_title: str,
) -> dict[str, str]:
    recommendation_eligible = "yes" if can_generate_recommendation(relationship_id) else "no"
    modifier_only = "yes" if relationship_id in MODIFIER_ONLY_RELATIONSHIPS else "no"

    return {
        "relationship_id": relationship_id,
        "relationship_status": parsed_fields.get("relationship_status", "ACTIVE"),
        "relationship_section_title": section_title.strip(),
        "evidence_strength": parsed_fields.get("evidence_strength", ""),
        "measurement_transfer_risk": parsed_fields.get("measurement_transfer_risk", ""),
        "max_product_level": parsed_fields.get("max_product_level", ""),
        "recommendation_eligible": recommendation_eligible,
        "modifier_suppressor_only": modifier_only,
        "mandatory_contradiction_suppression": "yes" if relationship_id == "R-03" else "no",
    }


def split_relationship_block(
    block: str,
    *,
    relationship_id: str,
    section_title: str,
    parsed_fields: dict[str, str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Split a relationship block on semantic boundaries when it exceeds chunk_size."""
    if len(block) <= chunk_size:
        return [block]

    envelope_preview = build_safety_envelope(
        relationship_id,
        parsed_fields=parsed_fields,
        section_title=section_title,
    )
    effective_chunk_size = max(400, chunk_size - len(envelope_preview) - 2)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=effective_chunk_size,
        chunk_overlap=min(chunk_overlap, max(0, effective_chunk_size // 5)),
        separators=RELATIONSHIP_BULLET_SEPARATORS,
        length_function=len,
    )
    return splitter.split_text(block)


def chunk_relationship_block(
    block: str,
    *,
    base_metadata: dict[str, str | int],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    heading_match = RELATIONSHIP_HEADING_PATTERN.search(block)
    if heading_match is None:
        raise ValueError("Relationship block is missing an R-XX heading.")

    relationship_id = heading_match.group(1)
    section_title = heading_match.group(0).strip()
    parsed_fields = _parse_relationship_fields(block)
    relationship_metadata = build_relationship_metadata(
        relationship_id,
        parsed_fields=parsed_fields,
        section_title=section_title,
    )
    envelope = build_safety_envelope(
        relationship_id,
        parsed_fields=parsed_fields,
        section_title=section_title,
    )

    body_parts = split_relationship_block(
        block,
        relationship_id=relationship_id,
        section_title=section_title,
        parsed_fields=parsed_fields,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    documents: list[Document] = []
    for part in body_parts:
        metadata = deepcopy(base_metadata)
        metadata.update(relationship_metadata)
        metadata["section_heading"] = section_title
        page_content = f"{envelope}\n\n{part.strip()}"
        documents.append(Document(page_content=page_content, metadata=metadata))

    return documents


def chunk_generic_segment(
    segment_text: str,
    *,
    base_metadata: dict[str, str | int],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    """Apply the standard Markdown splitter to a non-relationship segment."""
    if not segment_text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=MARKDOWN_SEPARATORS,
        length_function=len,
    )
    chunk_texts = splitter.split_text(segment_text)
    if not chunk_texts:
        return []

    headings = _build_heading_index(segment_text)
    chunk_starts = _find_chunk_positions(segment_text, chunk_texts)

    documents: list[Document] = []
    for chunk_content, chunk_start in zip(chunk_texts, chunk_starts):
        metadata = deepcopy(base_metadata)
        metadata["section_heading"] = _section_heading_before(chunk_start, headings)
        documents.append(Document(page_content=chunk_content, metadata=metadata))

    return post_process_chunks(documents, chunk_size=chunk_size)


def chunk_l2cr_markdown_text(
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
    supplemental_metadata: dict[str, str] | None = None,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> list[Document]:
    """Chunk L2-CR with relationship-aware segmentation for Section 5."""
    prefix, relationship_blocks, suffix = extract_relationship_blocks(text)

    base_metadata: dict[str, str | int] = {
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
        "section_heading": "",
    }
    base_metadata = _attach_supplemental_metadata(base_metadata, supplemental_metadata or {})

    documents: list[Document] = []
    documents.extend(
        chunk_generic_segment(
            prefix,
            base_metadata=base_metadata,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    )

    for relationship_id in sorted(relationship_blocks):
        documents.extend(
            chunk_relationship_block(
                relationship_blocks[relationship_id],
                base_metadata=base_metadata,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )

    documents.extend(
        chunk_generic_segment(
            suffix,
            base_metadata=base_metadata,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    )

    return reindex_chunks(documents)


def chunk_has_safety_envelope(page_content: str) -> bool:
    return SAFETY_ENVELOPE_MARKER in page_content


def relationship_chunks(documents: list[Document]) -> list[Document]:
    return [document for document in documents if document.metadata.get("relationship_id")]
