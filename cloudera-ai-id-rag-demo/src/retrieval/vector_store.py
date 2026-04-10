"""Vector store abstraction — FAISS for demo, swappable for enterprise.

Persists index to disk so ingestion only needs to run once.
"""

from __future__ import annotations

import os
from pathlib import Path

from src.config.settings import settings
from src.config.logging import get_logger
from src.retrieval.chunking import DocumentChunk

logger = get_logger(__name__)

_store = None


def build_vector_store(chunks: list[DocumentChunk], embeddings) -> None:
    """Build and persist FAISS index from document chunks."""
    from langchain_community.vectorstores import FAISS

    texts = [c.text for c in chunks]
    metadatas = [c.metadata for c in chunks]

    logger.info("Building FAISS index from %d chunks...", len(chunks))
    store = FAISS.from_texts(texts, embeddings, metadatas=metadatas)

    path = settings.vector_store_path
    Path(path).mkdir(parents=True, exist_ok=True)
    store.save_local(path)
    logger.info("Vector store saved to %s", path)

    global _store
    _store = store


def load_vector_store(embeddings) -> object:
    """Load FAISS index from disk. Returns None if not found."""
    global _store
    if _store is not None:
        return _store

    path = settings.vector_store_path
    index_file = Path(path) / "index.faiss"
    if not index_file.exists():
        logger.warning("No vector store found at %s — run document ingestion first.", path)
        return None

    from langchain_community.vectorstores import FAISS

    _store = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
    logger.info("Vector store loaded from %s", path)
    return _store
