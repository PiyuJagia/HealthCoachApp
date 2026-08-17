"""Generate OpenAI embeddings for LangChain Document objects."""

from __future__ import annotations

import os
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from openai import OpenAIError

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSION = 1536


@dataclass
class EmbeddedDocument:
    """A document chunk paired with its embedding vector."""

    page_content: str
    metadata: dict
    embedding: list[float]


def _validate_documents(documents: list[Document]) -> None:
    if not documents:
        raise ValueError("Cannot embed an empty document list.")

    for index, document in enumerate(documents, start=1):
        if not document.page_content.strip():
            raise ValueError(f"Document at position {index} has empty page_content.")


def _require_openai_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise ValueError(
            "OPENAI_API_KEY is not set. Add it to .env before generating embeddings."
        )


def embed_documents(
    documents: list[Document],
    *,
    model: str = DEFAULT_EMBEDDING_MODEL,
) -> list[EmbeddedDocument]:
    """Generate one embedding per document while preserving metadata."""
    _require_openai_api_key()
    _validate_documents(documents)

    texts = [document.page_content for document in documents]
    embedder = OpenAIEmbeddings(model=model)

    try:
        vectors = embedder.embed_documents(texts)
    except OpenAIError as error:
        raise RuntimeError(f"OpenAI embedding request failed: {error}") from error
    except Exception as error:
        raise RuntimeError(f"Embedding request failed: {error}") from error

    if len(vectors) != len(documents):
        raise RuntimeError(
            "Embedding count mismatch: "
            f"expected {len(documents)} embeddings, received {len(vectors)}."
        )

    return [
        EmbeddedDocument(
            page_content=document.page_content,
            metadata=dict(document.metadata),
            embedding=vector,
        )
        for document, vector in zip(documents, vectors)
    ]


def embed_query(
    text: str,
    *,
    model: str = DEFAULT_EMBEDDING_MODEL,
) -> list[float]:
    """Generate an embedding vector for a single query string."""
    _require_openai_api_key()

    if not text.strip():
        raise ValueError("Cannot embed an empty query string.")

    embedder = OpenAIEmbeddings(model=model)

    try:
        return embedder.embed_query(text)
    except OpenAIError as error:
        raise RuntimeError(f"OpenAI embedding request failed: {error}") from error
    except Exception as error:
        raise RuntimeError(f"Embedding request failed: {error}") from error
