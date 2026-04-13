"""Question router — classifies incoming questions and dispatches retrieval.

Routes to: "dokumen" | "data" | "gabungan"

Classification uses the LLM with a lightweight prompt. Falls back to
"dokumen" if classification is ambiguous to prevent accidental SQL execution.
"""

from __future__ import annotations

from typing import Literal

from src.llm.inference_client import get_llm_client
from src.llm.prompts import build_router_prompt
from src.config.logging import get_logger

logger = get_logger(__name__)

AnswerMode = Literal["dokumen", "data", "gabungan"]

_MODE_MAP: dict[str, AnswerMode] = {
    "dokumen": "dokumen",
    "data": "data",
    "gabungan": "gabungan",
    # tolerant aliases
    "document": "dokumen",
    "structured": "data",
    "combined": "gabungan",
    "sql": "data",
}


def classify_question(question: str) -> AnswerMode:
    """Classify the question into a routing mode using the LLM.

    Returns "dokumen" as safe default on any ambiguity or LLM error.
    """
    try:
        llm = get_llm_client()
        messages = build_router_prompt(question)
        response = llm.chat(messages, temperature=0.0, max_tokens=10)
        raw = response.content.strip().lower()
        mode = _MODE_MAP.get(raw, "dokumen")
        logger.info("Classified '%s...' → %s", question[:50], mode)
        return mode
    except Exception as exc:
        logger.warning("Router classification failed: %s — defaulting to 'dokumen'", exc)
        return "dokumen"
