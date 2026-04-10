"""Tests for document loading and chunking."""

import pytest
from src.retrieval.chunking import _split_text, chunk_documents
from src.retrieval.document_loader import RawDocument


def test_split_text_basic():
    text = "A" * 2000
    chunks = _split_text(text, chunk_size=800, overlap=100)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 800


def test_split_text_short_text():
    text = "Halo dunia."
    chunks = _split_text(text, chunk_size=800, overlap=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_text_empty():
    chunks = _split_text("", chunk_size=800, overlap=100)
    assert chunks == []


def test_split_text_whitespace_only():
    chunks = _split_text("   \n\n  ", chunk_size=800, overlap=100)
    assert chunks == []


def test_chunk_documents_preserves_metadata():
    doc = RawDocument(
        doc_id="test-001",
        title="Kebijakan Kredit",
        source_path="/data/docs/kebijakan.pdf",
        text="Teks dokumen " * 200,
        file_type="pdf",
        ingest_timestamp="2026-04-10T00:00:00+00:00",
    )
    chunks = chunk_documents([doc])
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.doc_id == "test-001"
        assert chunk.title == "Kebijakan Kredit"
        assert chunk.source_path == "/data/docs/kebijakan.pdf"
        assert chunk.file_type == "pdf"
        assert chunk.ingest_timestamp == "2026-04-10T00:00:00+00:00"


def test_chunk_documents_unique_ids():
    doc = RawDocument(
        doc_id="test-002",
        title="Dokumen Strategi",
        source_path="/data/docs/strategi.docx",
        text="Isi strategi perusahaan " * 100,
        file_type="docx",
        ingest_timestamp="2026-04-10T00:00:00+00:00",
    )
    chunks = chunk_documents([doc])
    chunk_ids = [c.chunk_id for c in chunks]
    assert len(chunk_ids) == len(set(chunk_ids)), "Chunk IDs must be unique"


def test_chunk_documents_chunk_index_sequential():
    doc = RawDocument(
        doc_id="test-003",
        title="Regulasi",
        source_path="/data/regulasi.txt",
        text="Pasal " * 500,
        file_type="txt",
        ingest_timestamp="2026-04-10T00:00:00+00:00",
    )
    chunks = chunk_documents([doc])
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))
