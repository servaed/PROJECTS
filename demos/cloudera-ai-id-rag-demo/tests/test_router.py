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
    # LLM returns Indonesian words (router prompt is in Bahasa Indonesia)
    ("dokumen", "document"),
    ("DOKUMEN", "document"),          # case-insensitive
    ("gabungan", "combined"),
    ("GABUNGAN", "combined"),
    # LLM returns English words (some models may answer in English)
    ("document", "document"),
    ("combined", "combined"),
    # Data mode
    ("data", "data"),
    ("DATA", "data"),
    ("structured", "data"),
    ("sql", "data"),
])
def test_classify_known_responses(llm_reply, expected_mode):
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm(llm_reply)):
        assert classify_question("any question") == expected_mode


def test_classify_unknown_response_defaults_to_document():
    """Unknown LLM replies must fall back to 'document' — safer than SQL."""
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm("UNKNOWN_LABEL")):
        assert classify_question("what is this?") == "document"


def test_classify_empty_response_defaults_to_document():
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm("")):
        assert classify_question("what is this?") == "document"


def test_classify_llm_error_defaults_to_document():
    """Any exception during classification must default to 'document', not raise."""
    client = MagicMock()
    client.chat.side_effect = RuntimeError("connection refused")
    with patch("src.orchestration.router.get_llm_client", return_value=client):
        assert classify_question("what is this?") == "document"


# ── Sample question routing ───────────────────────────────────────────────

def test_document_question_routed(monkeypatch):
    """Questions about policies should route to 'document'."""
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm("dokumen")):
        mode = classify_question("Explain the credit restructuring conditions.")
    assert mode == "document"


def test_data_question_routed(monkeypatch):
    """Questions asking for numbers/aggregates should route to 'data'."""
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm("data")):
        mode = classify_question("What is the total MSME outstanding in Jakarta March 2026?")
    assert mode == "data"


def test_combined_question_routed(monkeypatch):
    """Questions needing both documents and data should route to 'combined'."""
    with patch("src.orchestration.router.get_llm_client", return_value=_mock_llm("gabungan")):
        mode = classify_question("Does the outstanding trend align with the MSME expansion policy?")
    assert mode == "combined"


# ── Mode map completeness ────────────────────────────────────────────────

def test_mode_map_covers_all_modes():
    """Every mode must be reachable through _MODE_MAP."""
    values = set(_MODE_MAP.values())
    assert "document" in values
    assert "data" in values
    assert "combined" in values
