"""Retrieval service — runs similarity search over the vector store.

Returns ranked document chunks with metadata for citation building.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.logging import get_logger
from src.retrieval.embeddings import get_embeddings
from src.retrieval.vector_store import load_vector_store

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    title: str
    source_path: str
    chunk_index: int
    score: float
    ingest_timestamp: str


def retrieve(question: str, top_k: int = 5) -> list[RetrievedChunk]:
    """Retrieve the top-k most relevant chunks for a question.

    Returns an empty list if the vector store has not been built yet.
    """
    embeddings = get_embeddings()
    store = load_vector_store(embeddings)

    if store is None:
        logger.warning("Vector store not available — cannot retrieve documents.")
        return []

    results = store.similarity_search_with_score(question, k=top_k)
    chunks = []
    for doc, score in results:
        meta = doc.metadata
        chunks.append(
            RetrievedChunk(
                text=doc.page_content,
                title=meta.get("title", "Dokumen Tanpa Judul"),
                source_path=meta.get("source_path", ""),
                chunk_index=meta.get("chunk_index", 0),
                score=float(score),
                ingest_timestamp=meta.get("ingest_timestamp", ""),
            )
        )
    logger.debug("Retrieved %d chunks for question: %.60s", len(chunks), question)
    return chunks
