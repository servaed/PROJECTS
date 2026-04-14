"""FastAPI endpoint tests for app/api.py.

Covers:
  - GET /            → 404 when SPA not present, 200 with HTML otherwise
  - GET /api/status  → shape of response; LLM indicator correct for all providers
  - GET /api/samples → returns a non-empty list of strings
  - POST /api/chat   → SSE stream emits mode, token, done events

All external dependencies (DB, vector store, LLM) are mocked so no
live infrastructure is required.  Run with: pytest tests/test_api.py -v
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_sse(raw: str) -> list[dict]:
    """Parse raw SSE text into a list of {'event': str, 'data': dict}."""
    events = []
    for block in raw.strip().split("\n\n"):
        if not block.strip():
            continue
        event, data = "message", None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[7:].strip()
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if data is not None:
            events.append({"event": event, "data": data})
    return events


def _make_app_client(index_html: str = "<html/>"):
    """Import the FastAPI app with a patched static directory and return a TestClient.

    The lifespan is intentionally bypassed (lifespan=False on TestClient) to
    avoid needing real filesystem resources during unit tests.
    """
    from app import api as api_module

    # Inject fake SPA HTML so GET / returns 200
    api_module._INDEX_HTML = index_html
    return TestClient(api_module.app, raise_server_exceptions=True)


# ── GET / ──────────────────────────────────────────────────────────────────

def test_index_returns_404_when_no_spa():
    from app import api as api_module
    original = api_module._INDEX_HTML
    try:
        api_module._INDEX_HTML = ""
        client = TestClient(api_module.app)
        resp = client.get("/")
        assert resp.status_code == 404
    finally:
        api_module._INDEX_HTML = original


def test_index_returns_html_when_spa_cached():
    client = _make_app_client("<html><body>SPA</body></html>")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "SPA" in resp.text


# ── GET /api/samples ───────────────────────────────────────────────────────

def test_samples_returns_list():
    client = _make_app_client()
    resp = client.get("/api/samples")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert all(isinstance(s, str) for s in data)


# ── GET /api/status ────────────────────────────────────────────────────────

def _status_with_mocks(llm_base_url: str = "", llm_provider: str = "openai",
                       llm_model_id: str = "gpt-4", vs_exists: bool = False,
                       db_tables: list | None = None):
    """Call /api/status under controlled settings."""
    from app import api as api_module

    fake_settings = MagicMock()
    fake_settings.llm_base_url = llm_base_url
    fake_settings.llm_provider = llm_provider
    fake_settings.llm_model_id = llm_model_id
    fake_settings.vector_store_path = "/fake/vs"

    with patch.object(api_module, "settings", fake_settings), \
         patch("app.api.Path") as MockPath, \
         patch("app.api.get_table_names", return_value=db_tables or ["t1", "t2"], create=True):

        # Make the FAISS file appear present/absent
        mock_faiss = MagicMock()
        mock_faiss.exists.return_value = vs_exists
        MockPath.return_value.__truediv__.return_value = mock_faiss

        client = _make_app_client()
        return client.get("/api/status").json()


def test_status_has_required_keys():
    from app import api as api_module
    client = _make_app_client()

    with patch.object(api_module, "settings", MagicMock(
        llm_base_url="http://llm", llm_provider="openai",
        llm_model_id="gpt-4", vector_store_path="/vs"
    )), patch("app.api.Path") as MockPath, \
       patch("app.api.get_table_names", return_value=[], create=True):
        mock_f = MagicMock(); mock_f.exists.return_value = True
        MockPath.return_value.__truediv__.return_value = mock_f
        resp = client.get("/api/status")

    assert resp.status_code == 200
    data = resp.json()
    assert "vector_store" in data
    assert "database" in data
    assert "llm" in data


def test_status_llm_ok_with_base_url():
    """LLM indicator must be ok=True when llm_base_url is set."""
    from app import api as api_module
    client = _make_app_client()

    fake = MagicMock()
    fake.llm_base_url = "http://my-llm"
    fake.llm_provider = "openai"
    fake.llm_model_id = "meta/llama-3"
    fake.vector_store_path = "/vs"

    with patch.object(api_module, "settings", fake), \
         patch("app.api.Path") as MP, \
         patch("app.api.get_table_names", return_value=[], create=True):
        mf = MagicMock(); mf.exists.return_value = False
        MP.return_value.__truediv__.return_value = mf
        data = client.get("/api/status").json()

    assert data["llm"]["ok"] is True


def test_status_llm_ok_for_bedrock_provider():
    """Bedrock provider has no base_url — indicator must still be ok=True."""
    from app import api as api_module
    client = _make_app_client()

    fake = MagicMock()
    fake.llm_base_url = ""
    fake.llm_provider = "bedrock"
    fake.llm_model_id = "anthropic.claude-3-sonnet"
    fake.vector_store_path = "/vs"

    with patch.object(api_module, "settings", fake), \
         patch("app.api.Path") as MP, \
         patch("app.api.get_table_names", return_value=[], create=True):
        mf = MagicMock(); mf.exists.return_value = False
        MP.return_value.__truediv__.return_value = mf
        data = client.get("/api/status").json()

    assert data["llm"]["ok"] is True


def test_status_llm_ok_for_anthropic_provider():
    """Anthropic provider has no base_url — indicator must still be ok=True."""
    from app import api as api_module
    client = _make_app_client()

    fake = MagicMock()
    fake.llm_base_url = ""
    fake.llm_provider = "anthropic"
    fake.llm_model_id = "claude-sonnet-4-6"
    fake.vector_store_path = "/vs"

    with patch.object(api_module, "settings", fake), \
         patch("app.api.Path") as MP, \
         patch("app.api.get_table_names", return_value=[], create=True):
        mf = MagicMock(); mf.exists.return_value = False
        MP.return_value.__truediv__.return_value = mf
        data = client.get("/api/status").json()

    assert data["llm"]["ok"] is True


def test_status_llm_not_ok_when_unconfigured():
    """No base_url and non-cloud provider → ok=False."""
    from app import api as api_module
    client = _make_app_client()

    fake = MagicMock()
    fake.llm_base_url = ""
    fake.llm_provider = "openai"
    fake.llm_model_id = "gpt-4"
    fake.vector_store_path = "/vs"

    with patch.object(api_module, "settings", fake), \
         patch("app.api.Path") as MP, \
         patch("app.api.get_table_names", return_value=[], create=True):
        mf = MagicMock(); mf.exists.return_value = False
        MP.return_value.__truediv__.return_value = mf
        data = client.get("/api/status").json()

    assert data["llm"]["ok"] is False


# ── POST /api/chat ─────────────────────────────────────────────────────────

def _make_prep(mode: str = "dokumen"):
    """Build a minimal AnswerPrep-like object for mocking."""
    prep = MagicMock()
    prep.mode = mode
    prep.doc_chunks = []
    return prep


def _make_result():
    result = MagicMock()
    result.doc_citations = []
    result.sql_citation = None
    return result


def test_chat_sse_emits_mode_token_done():
    """A successful /api/chat request must emit mode → token(s) → done."""
    from app import api as api_module

    prep  = _make_prep("dokumen")
    result = _make_result()

    with patch("app.api.prepare_answer", return_value=prep), \
         patch("app.api.stream_synthesis", return_value=iter(["Hello", " world"])), \
         patch("app.api.finalize_answer", return_value=result):

        client = _make_app_client()
        resp = client.post(
            "/api/chat",
            json={"question": "Apa itu kredit?", "history": []},
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    event_types = [e["event"] for e in events]

    assert "mode"  in event_types
    assert "token" in event_types
    assert "done"  in event_types
    # mode must arrive before first token
    assert event_types.index("mode") < event_types.index("token")
    # done must be last
    assert event_types[-1] == "done"


def test_chat_sse_mode_value():
    from app import api as api_module

    prep   = _make_prep("data")
    result = _make_result()

    with patch("app.api.prepare_answer", return_value=prep), \
         patch("app.api.stream_synthesis", return_value=iter(["ok"])), \
         patch("app.api.finalize_answer", return_value=result):

        client = _make_app_client()
        resp = client.post("/api/chat", json={"question": "jumlah UMKM?", "history": []})

    events = _parse_sse(resp.text)
    mode_evt = next(e for e in events if e["event"] == "mode")
    assert mode_evt["data"]["mode"] == "data"


def test_chat_sse_emits_error_on_pipeline_failure():
    """If prepare_answer raises, the SSE stream must emit an error event."""
    from app import api as api_module

    with patch("app.api.prepare_answer", side_effect=RuntimeError("backend down")):
        client = _make_app_client()
        resp = client.post("/api/chat", json={"question": "apa?", "history": []})

    events = _parse_sse(resp.text)
    assert any(e["event"] == "error" for e in events)
    err = next(e for e in events if e["event"] == "error")
    assert "backend down" in err["data"]["message"]
