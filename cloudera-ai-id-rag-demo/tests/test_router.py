"""Tests for the question router and mode classification."""

import pytest
from unittest.mock import MagicMock, patch
from src.orchestration.router import classify_question, _MODE_MAP


def test_mode_map_covers_all_modes():
    modes = set(_MODE_MAP.values())
    assert "dokumen" in modes
    assert "data" in modes
    assert "gabungan" in modes


@pytest.mark.parametrize("raw,expected", [
    ("dokumen", "dokumen"),
    ("data", "data"),
    ("gabungan", "gabungan"),
    ("document", "dokumen"),
    ("structured", "data"),
    ("combined", "gabungan"),
    ("sql", "data"),
    ("unknown_gibberish", "dokumen"),  # fallback
])
def test_mode_map_resolution(raw, expected):
    result = _MODE_MAP.get(raw, "dokumen")
    assert result == expected


@patch("src.orchestration.router.get_llm_client")
def test_classify_returns_dokumen_on_llm_failure(mock_llm_factory):
    mock_client = MagicMock()
    mock_client.chat.side_effect = RuntimeError("LLM unavailable")
    mock_llm_factory.return_value = mock_client

    result = classify_question("Apa kebijakan restrukturisasi kredit?")
    assert result == "dokumen"


@patch("src.orchestration.router.get_llm_client")
def test_classify_dokumen_question(mock_llm_factory):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "dokumen"
    mock_client.chat.return_value = mock_response
    mock_llm_factory.return_value = mock_client

    result = classify_question("Jelaskan ketentuan restrukturisasi kredit.")
    assert result == "dokumen"


@patch("src.orchestration.router.get_llm_client")
def test_classify_data_question(mock_llm_factory):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "data"
    mock_client.chat.return_value = mock_response
    mock_llm_factory.return_value = mock_client

    result = classify_question("Berapa total outstanding UMKM Jakarta?")
    assert result == "data"


@patch("src.orchestration.router.get_llm_client")
def test_classify_gabungan_question(mock_llm_factory):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "gabungan"
    mock_client.chat.return_value = mock_response
    mock_llm_factory.return_value = mock_client

    result = classify_question("Apakah tren outstanding sesuai kebijakan ekspansi?")
    assert result == "gabungan"
