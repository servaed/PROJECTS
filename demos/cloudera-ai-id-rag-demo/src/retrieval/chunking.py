"""Text chunking — splits raw documents into retrievable chunks.

Uses a simple recursive character splitter with overlap.
Preserves source metadata on every chunk for traceability.
"""

from __future__ import annotations

from dataclasses import dataclass
from src.retrieval.document_loader import RawDocument
from src.config.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CHUNK_SIZE = 800     # characters
DEFAULT_CHUNK_OVERLAP = 100  # characters


@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    title: str
    source_path: str
    file_type: str
    ingest_timestamp: str
    chunk_index: int
    text: str

    @property
    def metadata(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "source_path": self.source_path,
            "file_type": self.file_type,
            "ingest_timestamp": self.ingest_timestamp,
            "chunk_index": self.chunk_index,
        }


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by character count."""
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - overlap
    return chunks


def chunk_documents(
    documents: list[RawDocument],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Chunk all documents and return a flat list of DocumentChunks."""
    from src.utils.ids import new_id

    all_chunks: list[DocumentChunk] = []
    for doc in documents:
        texts = _split_text(doc.text, chunk_size, chunk_overlap)
        for i, text in enumerate(texts):
            all_chunks.append(
                DocumentChunk(
                    chunk_id=new_id(),
                    doc_id=doc.doc_id,
                    title=doc.title,
                    source_path=doc.source_path,
                    file_type=doc.file_type,
                    ingest_timestamp=doc.ingest_timestamp,
                    chunk_index=i,
                    text=text,
                )
            )
        logger.debug("Chunked '%s' into %d chunks", doc.title, len(texts))

    logger.info("Total chunks: %d from %d documents", len(all_chunks), len(documents))
    return all_chunks
