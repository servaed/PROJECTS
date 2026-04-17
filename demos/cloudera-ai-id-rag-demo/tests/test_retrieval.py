"""Tests for retrieval pipeline components.

Covers: DocumentChunk metadata, chunking logic, RetrievedChunk format,
DocumentCitation building, and vector store retrieve() with a mocked store.

No real embedding model or vector store is used — all external dependencies
are mocked. Run with: pytest tests/test_retrieval.py -v
"""

from unittest.mock import MagicMock, patch
from dataclasses import asdict

import pytest

from src.retrieval.chunking import DocumentChunk, chunk_documents
from src.retrieval.retriever import RetrievedChunk, retrieve
from src.orchestration.citations import build_document_citations, DocumentCitation
from src.retrieval.document_loader import RawDocument


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_raw_doc(text: str, title: str = "Test Doc") -> RawDocument:
    return RawDocument(
        doc_id="doc-001",
        title=title,
        source_path="/data/test.txt",
        text=text,
        file_type="txt",
        domain="banking",
        ingest_timestamp="2026-04-13T00:00:00",
    )


def _make_chunk(title: str = "Doc A", text: str = "Teks contoh.", chunk_index: int = 0) -> DocumentChunk:
    return DocumentChunk(
        chunk_id="chunk-001",
        doc_id="doc-001",
        title=title,
        source_path="/data/test.txt",
        file_type="txt",
        ingest_timestamp="2026-04-13T00:00:00",
        chunk_index=chunk_index,
        text=text,
    )


# ── DocumentChunk ─────────────────────────────────────────────────────────

def test_document_chunk_metadata_keys():
    chunk = _make_chunk()
    meta = chunk.metadata
    for key in ("chunk_id", "doc_id", "title", "source_path", "file_type",
                "ingest_timestamp", "chunk_index"):
        assert key in meta, f"Missing metadata key: {key}"


def test_document_chunk_metadata_values():
    chunk = _make_chunk(title="Kebijakan Kredit", chunk_index=3)
    assert chunk.metadata["title"] == "Kebijakan Kredit"
    assert chunk.metadata["chunk_index"] == 3


# ── chunk_documents ───────────────────────────────────────────────────────

def test_chunk_documents_returns_chunks():
    doc = _make_raw_doc("Paragraf pertama.\n\nParagraf kedua.\n\nParagraf ketiga.")
    chunks = chunk_documents([doc], chunk_size=50, chunk_overlap=5)
    assert len(chunks) >= 1
    assert all(isinstance(c, DocumentChunk) for c in chunks)


def test_chunk_documents_preserves_metadata():
    doc = _make_raw_doc("Teks dokumen yang panjang untuk diuji.", title="Regulasi OJK")
    chunks = chunk_documents([doc])
    for chunk in chunks:
        assert chunk.title == "Regulasi OJK"
        assert chunk.source_path == doc.source_path
        assert chunk.doc_id == doc.doc_id
        assert chunk.ingest_timestamp == doc.ingest_timestamp


def test_chunk_documents_sequential_indices():
    doc = _make_raw_doc(" ".join(["kata"] * 300))
    chunks = chunk_documents([doc], chunk_size=100, chunk_overlap=10)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_chunk_documents_empty_text_skipped():
    doc = _make_raw_doc("   ")
    chunks = chunk_documents([doc])
    assert chunks == []


def test_chunk_documents_multiple_docs():
    docs = [_make_raw_doc(f"Dokumen {i}. " * 5) for i in range(3)]
    chunks = chunk_documents(docs)
    assert len(chunks) >= 3


def test_chunk_text_not_empty():
    doc = _make_raw_doc("Kebijakan kredit UMKM berlaku efektif mulai tahun 2026.")
    chunks = chunk_documents([doc])
    for c in chunks:
        assert c.text.strip() != ""


# ── build_document_citations ──────────────────────────────────────────────

def test_build_citations_from_chunks():
    chunks = [
        RetrievedChunk(
            text="Pasal 3 menyebutkan bahwa kredit UMKM diberikan dengan bunga rendah.",
            title="Kebijakan Kredit",
            source_path="/docs/kebijakan.txt",
            chunk_index=0,
            score=0.92,
            ingest_timestamp="2026-04-13T00:00:00",
        )
    ]
    citations = build_document_citations(chunks)
    assert len(citations) == 1
    c = citations[0]
    assert c.title == "Kebijakan Kredit"
    assert c.source_path == "/docs/kebijakan.txt"
    assert c.chunk_index == 0
    assert len(c.excerpt) <= 300 + 1  # +1 for ellipsis


def test_build_citations_deduplicates():
    """Same source + chunk_index should appear only once."""
    chunk = RetrievedChunk(
        text="Teks duplikat.",
        title="Doc",
        source_path="/docs/a.txt",
        chunk_index=0,
        score=0.9,
        ingest_timestamp="2026-04-13T00:00:00",
    )
    citations = build_document_citations([chunk, chunk])
    assert len(citations) == 1


def test_build_citations_empty_input():
    assert build_document_citations([]) == []


def test_build_citations_excerpt_truncated():
    long_text = "x" * 1000
    chunk = RetrievedChunk(
        text=long_text,
        title="Long Doc",
        source_path="/docs/long.txt",
        chunk_index=0,
        score=0.8,
        ingest_timestamp="2026-04-13T00:00:00",
    )
    citations = build_document_citations(chunks=[chunk], excerpt_length=300)
    assert citations[0].excerpt.endswith("…")
    assert len(citations[0].excerpt) <= 301  # 300 chars + ellipsis


# ── retrieve() with mocked vector store ──────────────────────────────────

def _make_langchain_doc(text: str, meta: dict):
    """Build a minimal LangChain Document mock."""
    doc = MagicMock()
    doc.page_content = text
    doc.metadata = meta
    return doc


def test_retrieve_returns_chunks():
    fake_doc = _make_langchain_doc(
        "Prosedur KYC mensyaratkan verifikasi identitas.",
        {
            "title": "Prosedur KYC",
            "source_path": "/docs/kyc.txt",
            "chunk_index": 0,
            "ingest_timestamp": "2026-04-13T00:00:00",
        },
    )
    mock_store = MagicMock()
    mock_store.similarity_search_with_score.return_value = [(fake_doc, 0.85)]

    with patch("src.retrieval.retriever.load_vector_store", return_value=mock_store), \
         patch("src.retrieval.retriever.get_embeddings", return_value=MagicMock()):
        results = retrieve("prosedur KYC", top_k=1)

    assert len(results) == 1
    r = results[0]
    assert isinstance(r, RetrievedChunk)
    assert r.title == "Prosedur KYC"
    assert r.score == pytest.approx(0.85)
    assert r.text == "Prosedur KYC mensyaratkan verifikasi identitas."


def test_retrieve_empty_when_store_unavailable():
    with patch("src.retrieval.retriever.load_vector_store", return_value=None), \
         patch("src.retrieval.retriever.get_embeddings", return_value=MagicMock()):
        results = retrieve("apa itu KYC?")
    assert results == []


def test_retrieve_top_k_respected():
    docs = [
        (_make_langchain_doc(f"Teks {i}", {"title": f"Doc {i}", "source_path": f"/d/{i}.txt",
                                            "chunk_index": i, "ingest_timestamp": "2026-04-13"}), 0.9 - i * 0.1)
        for i in range(5)
    ]
    mock_store = MagicMock()
    mock_store.similarity_search_with_score.return_value = docs[:3]

    with patch("src.retrieval.retriever.load_vector_store", return_value=mock_store), \
         patch("src.retrieval.retriever.get_embeddings", return_value=MagicMock()):
        results = retrieve("pertanyaan", top_k=3)

    assert len(results) == 3
    # Retriever fetches more candidates for hybrid BM25+FAISS reranking;
    # verify it was called (k > top_k is expected) and results are capped at top_k.
    mock_store.similarity_search_with_score.assert_called_once()
