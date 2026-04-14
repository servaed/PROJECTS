"""Vector store abstraction — FAISS for demo, swappable for enterprise.

Persists index to disk so ingestion only needs to run once.

Security: FAISS uses pickle serialization internally. To mitigate the risk of
loading a tampered index, we write a SHA-256 hash of the index files after
building and verify it before loading. If the hash is missing or does not match,
loading is refused and a new ingestion run is required.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from src.config.settings import settings
from src.config.logging import get_logger
from src.retrieval.chunking import DocumentChunk

logger = get_logger(__name__)

_store = None
_HASH_FILENAME = "index.sha256"


# ── Integrity helpers ──────────────────────────────────────────────────────


def _compute_hash(store_path: Path) -> str:
    """Compute a SHA-256 digest over the FAISS index binary files."""
    combined = b""
    for filename in ("index.faiss", "index.pkl"):
        f = store_path / filename
        if f.exists():
            combined += f.read_bytes()
    return hashlib.sha256(combined).hexdigest()


def _write_integrity_hash(store_path: Path) -> None:
    """Persist the SHA-256 hash of the current index files."""
    digest = _compute_hash(store_path)
    (store_path / _HASH_FILENAME).write_text(digest)
    logger.debug("Wrote vector store integrity hash: %s", digest[:16])


def _verify_integrity(store_path: Path) -> bool:
    """Return True if the index files match their stored hash, False otherwise."""
    hash_file = store_path / _HASH_FILENAME
    if not hash_file.exists():
        logger.warning(
            "Vector store integrity hash not found at %s — index may be from an older "
            "ingestion run. Delete the vector store directory and re-ingest to refresh.",
            store_path,
        )
        return False
    expected = hash_file.read_text().strip()
    actual = _compute_hash(store_path)
    if actual != expected:
        logger.error(
            "Vector store integrity check FAILED — expected %s, got %s. "
            "Delete %s and re-run document ingestion.",
            expected[:16],
            actual[:16],
            store_path,
        )
        return False
    return True


# ── Public API ─────────────────────────────────────────────────────────────


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

    # Write integrity hash immediately after saving so loads can be verified
    _write_integrity_hash(Path(path))
    logger.info("Vector store saved to %s", path)

    global _store
    _store = store


def load_vector_store(embeddings) -> object:
    """Load FAISS index from disk. Returns None if not found or integrity check fails."""
    global _store
    if _store is not None:
        return _store

    path = settings.vector_store_path
    store_path = Path(path)
    index_file = store_path / "index.faiss"
    if not index_file.exists():
        logger.warning("No vector store found at %s — run document ingestion first.", path)
        return None

    if not _verify_integrity(store_path):
        logger.error(
            "Refusing to load vector store at %s — integrity check failed. "
            "Re-run document ingestion to rebuild a trusted index.",
            path,
        )
        return None

    from langchain_community.vectorstores import FAISS

    # allow_dangerous_deserialization is required by LangChain for FAISS (uses pickle).
    # We mitigate the risk with the SHA-256 integrity check above.
    _store = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
    logger.info("Vector store loaded from %s (integrity verified)", path)
    return _store
