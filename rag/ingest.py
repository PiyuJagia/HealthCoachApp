"""Registry-driven document ingestion into Pinecone."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rag.chunker import chunk_markdown_document
from rag.embedder import embed_documents
from rag.registry import (
    RegistryError,
    get_approved_sources,
    get_source_record,
    validate_curated_file_exists,
)
from rag.vector_store import (
    delete_document_vectors,
    get_index_name,
    get_namespace,
    upsert_embedded_documents,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class IngestResult:
    document_id: str
    chunks_created: int
    vectors_upserted: int
    index_name: str
    namespace: str


def ingest_document_record(
    document_id: str,
    *,
    project_root: Path = PROJECT_ROOT,
) -> IngestResult:
    """Chunk, embed, replace, and upsert one approved registry document."""
    record = get_source_record(document_id)
    if not record.approved_for_ingestion:
        raise RegistryError(
            f"Document '{document_id}' is not approved for ingestion "
            "(approved_for_ingestion=FALSE)."
        )

    source_path = validate_curated_file_exists(record, project_root=project_root)
    documents = chunk_markdown_document(
        source_path,
        source_record=record,
        project_root=project_root,
    )
    embedded_documents = embed_documents(documents)
    delete_document_vectors(record.document_id)
    vectors_upserted = upsert_embedded_documents(embedded_documents)

    return IngestResult(
        document_id=record.document_id,
        chunks_created=len(documents),
        vectors_upserted=vectors_upserted,
        index_name=get_index_name(),
        namespace=get_namespace(),
    )


def ingest_all_approved(*, project_root: Path = PROJECT_ROOT) -> list[IngestResult]:
    """Ingest every registry row with approved_for_ingestion=TRUE."""
    approved = get_approved_sources()
    if not approved:
        raise RegistryError("No approved documents found in the source registry.")

    return [
        ingest_document_record(record.document_id, project_root=project_root)
        for record in approved
    ]
