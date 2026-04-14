"""Tests for the question router (classify_question).

Uses unittest.mock to patch the LLM so no real API calls are made.
Run with: pytest tests/test_router.py -v
"""

from unittest.mock import MagicMock, patch

import pytest

from src.orchestration.router import classify_question, _MODE_MAP
from src.llm.base import LLMResponse


def _mock_llm(content: str) -> MagicMock:
    """Return a mock LLM client that replies with the given string."""
    client = MagicMock()
    client.chat.return_value = LLMResponse(
        content=content, model="mock", input_tokens=0, output_tokens=0
    )
    return client


# ── Classification correctness ────────────────────────────────────────────

@pytest.mark.parametrize("llm_reply,expected_mode", [
    ("dokumen", "dokumen"),
    ("DOKUMEN", "dokumen"),          # case-insensitive
    ("data", "data"),
    ("DATA", "data"),
    ("gabungan", "gabungan"),
    ("GABUNGAN", "gabungan"),
    # Tolerant aliases
    ("document", "dokumen"),
    ("structured", "data"),
    ("combined", "gabungan"),
    ("sql", "data"),
])
def test_classify_known_responses(llm_reply, expected_mode):
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm(llm_reply)):
        assert classify_question("pertanyaan apapun") == expected_mode


def test_classify_unknown_response_defaults_to_dokumen():
    """Unknown LLM replies must fall back to 'dokumen' — safer than SQL."""
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm("UNKNOWN_LABEL")):
        assert classify_question("apa itu?") == "dokumen"


def test_classify_empty_response_defaults_to_dokumen():
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm("")):
        assert classify_question("apa itu?") == "dokumen"


def test_classify_llm_error_defaults_to_dokumen():
    """Any exception during classification must default to 'dokumen', not raise."""
    client = MagicMock()
    client.chat.side_effect = RuntimeError("connection refused")
    with patch("src.orchestration.router.get_llm_client", return_value=client):
        assert classify_question("apa itu?") == "dokumen"


# ── Sample question routing ───────────────────────────────────────────────

def test_document_question_routed(monkeypatch):
    """Questions about policies should route to 'dokumen'."""
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm("dokumen")):
        mode = classify_question("Jelaskan ketentuan restrukturisasi kredit.")
    assert mode == "dokumen"


def test_data_question_routed(monkeypatch):
    """Questions asking for numbers/aggregates should route to 'data'."""
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm("data")):
        mode = classify_question("Berapa total outstanding UMKM Jakarta Maret 2026?")
    assert mode == "data"


def test_combined_question_routed(monkeypatch):
    """Questions needing both documents and data should route to 'gabungan'."""
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm("gabungan")):
        mode = classify_question("Apakah tren outstanding sesuai kebijakan ekspansi UMKM?")
    assert mode == "gabungan"


# ── Mode map completeness ────────────────────────────────────────────────

def test_mode_map_covers_all_modes():
    """Every mode must be reachable through _MODE_MAP."""
    values = set(_MODE_MAP.values())
    assert "dokumen" in values
    assert "data" in values
    assert "gabungan" in values
