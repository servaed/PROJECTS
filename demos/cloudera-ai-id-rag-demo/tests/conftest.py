"""Shared pytest fixtures for the test suite.

Provides mock LLM client, mock vector store, and fast settings overrides so
tests don't load the real embedding model (~500 MB) on every run.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_llm_client(monkeypatch):
    """Mock LLM client that returns a preset response without hitting a real endpoint."""
    client = MagicMock()
    client.chat.return_value = MagicMock(content="Test response dari LLM.")
    client.stream_chat.return_value = iter(["Test ", "response ", "dari LLM."])
    client.is_available.return_value = True

    import src.llm.inference_client as ic_module
    monkeypatch.setattr(ic_module, "get_llm_client", lambda: client)
    return client


@pytest.fixture
def mock_vector_store(monkeypatch):
    """Mock FAISS vector store that returns an empty result set by default."""
    store = MagicMock()
    store.similarity_search_with_score.return_value = []

    import src.retrieval.retriever as ret_module
    monkeypatch.setattr(ret_module, "load_vector_store", lambda: store)
    monkeypatch.setattr(ret_module, "get_embeddings", lambda: MagicMock())
    return store


@pytest.fixture
def mock_vector_store_with_doc(monkeypatch):
    """Mock vector store that returns one sample banking document chunk."""
    fake_doc = MagicMock()
    fake_doc.page_content = "Kebijakan kredit UMKM mensyaratkan NPL di bawah 5%."
    fake_doc.metadata = {
        "title": "Kebijakan Kredit UMKM",
        "source_path": "/data/banking/kebijakan_kredit.txt",
        "chunk_index": 0,
        "ingest_timestamp": "2026-04-17T00:00:00",
        "domain": "banking",
    }

    store = MagicMock()
    store.similarity_search_with_score.return_value = [(fake_doc, 0.88)]

    import src.retrieval.retriever as ret_module
    monkeypatch.setattr(ret_module, "load_vector_store", lambda: store)
    monkeypatch.setattr(ret_module, "get_embeddings", lambda: MagicMock())
    return store


@pytest.fixture
def mock_db(monkeypatch):
    """Mock database adapter that returns an empty table list."""
    import src.connectors.db_adapter as db_module
    monkeypatch.setattr(db_module, "get_table_names", lambda: ["msme_credit", "customer"])
    return ["msme_credit", "customer"]


@pytest.fixture
def fast_settings(monkeypatch):
    """Override settings with safe, fast-loading values for unit tests."""
    from src.config import settings as settings_module
    mock_settings = MagicMock()
    mock_settings.vector_store_path = "/tmp/test_vs"
    mock_settings.llm_base_url = "http://fake-llm"
    mock_settings._live_provider = "openai"
    mock_settings.llm_model_id = "gpt-4"
    mock_settings.embeddings_provider = "local"
    mock_settings.embeddings_model = "intfloat/multilingual-e5-large"
    mock_settings.docs_source_path = "/tmp/test_docs"
    mock_settings.sql_max_rows = 500
    mock_settings.approved_tables = ["msme_credit", "customer", "branch"]
    monkeypatch.setattr(settings_module, "settings", mock_settings)
    return mock_settings
