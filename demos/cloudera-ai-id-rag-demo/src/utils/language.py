"""Language utilities — language detection helpers."""

from __future__ import annotations

# Common Indonesian question indicators (not exhaustive — for simple heuristics only)
_BAHASA_INDICATORS = {
    "apa", "siapa", "bagaimana", "berapa", "kapan", "dimana", "mengapa",
    "jelaskan", "tunjukkan", "tampilkan", "cari", "coba", "tolong",
    "dan", "atau", "yang", "dengan", "dari", "ke", "di", "adalah",
}


def is_likely_bahasa(text: str) -> bool:
    """Heuristic check: does the text contain common Bahasa Indonesia words?"""
    words = set(text.lower().split())
    overlap = words & _BAHASA_INDICATORS
    return len(overlap) >= 1


def mode_label(mode: str) -> str:
    """Return a display label for an answer mode."""
    labels = {
        "document": "Documents",
        "data":     "Structured Data",
        "combined": "Combined",
    }
    return labels.get(mode, mode.capitalize())


def mode_badge_color(mode: str) -> str:
    """Return a Streamlit-friendly color string for the mode badge."""
    colors = {
        "document": "blue",
        "data":     "green",
        "combined": "orange",
    }
    return colors.get(mode, "gray")
