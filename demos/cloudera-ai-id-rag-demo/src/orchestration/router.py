"""Question router — classifies incoming questions and dispatches retrieval.

Routes to: "document" | "data" | "combined"

Classification strategy (in order):
  1. Keyword heuristics — fast, reliable for clear-cut cases
  2. LLM classification — for ambiguous questions

Falls back to "document" on any LLM error to prevent accidental SQL execution.
"""

from __future__ import annotations

import re
from typing import Literal

from src.llm.inference_client import get_llm_client
from src.llm.prompts import build_router_prompt
from src.config.logging import get_logger

logger = get_logger(__name__)

AnswerMode = Literal["document", "data", "combined"]

# Maps LLM output words (may be Indonesian or English) to internal English mode strings.
_MODE_MAP: dict[str, AnswerMode] = {
    # Indonesian words returned by the Bahasa Indonesia router prompt
    "dokumen":  "document",
    "gabungan": "combined",
    # English aliases (direct or from models that answer in English)
    "document": "document",
    "combined": "combined",
    "data":     "data",
    "structured": "data",
    "sql":      "data",
}

# Strip <think>...</think> blocks produced by reasoning models (e.g. DeepSeek, QwQ).
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# ── Keyword heuristics ──────────────────────────────────────────────────────
#
# Tier 1 — "show/display" verb at the start of the question.
# These are always pure data requests regardless of other keywords.
_SHOW_VERBS = re.compile(
    r"^\s*(tampilkan|tunjukkan|berikan\s+data|show\b|list\b|display\b|lihat\s+data)",
    re.I,
)

# Tier 2 — Gabungan: question compares live data against a policy target/standard.
# Requires BOTH a data entity AND a comparison verb/standard reference.
_GABUNGAN_PATTERNS: list[re.Pattern] = [
    # Indonesian: "apakah X sudah sesuai / memenuhi / melampaui Y"
    re.compile(r"apakah\b.{0,80}\b(sesuai|memenuhi|melampaui|mencapai|melebihi)\b", re.I),
    # Indonesian: "sudah sesuai / memenuhi target / standar / SLA / kebijakan"
    re.compile(
        r"\bsudah\s+(sesuai|memenuhi|mencapai)\b.{0,50}\b(target|standar|sla|kebijakan|syarat)\b",
        re.I,
    ),
    # Indonesian: "dibandingkan kondisi / syarat / ketentuan kebijakan"
    re.compile(r"\bdibandingkan\b.{0,50}\b(kebijakan|ketentuan|syarat|standar|sla)\b", re.I),
    # Indonesian: "memenuhi syarat program / kebijakan / regulasi"
    re.compile(r"\bmemenuhi\s+syarat\b.{0,80}\b(program|kebijakan|regulasi|aturan)\b", re.I),
    # Indonesian: "melampaui batas / threshold SLA"
    re.compile(r"\bmelampaui\b.{0,50}\b(batas|threshold|standar|sla)\b", re.I),
    # Indonesian: outstanding/utilisasi/realisasi + comparison verb + policy reference
    re.compile(
        r"\b(outstanding|utilisasi|realisasi)\b.{0,40}"
        r"\b(sesuai|melampaui|memenuhi|mencapai)\b.{0,40}"
        r"\b(target|batas|standar|sla|kebijakan|regulasi|syarat)\b",
        re.I,
    ),
    # English: "has/does/did X exceeded/met/meet/aligned with ... SLA/threshold/policy/standard"
    re.compile(
        r"\b(has|have|does|do|did)\b.{0,80}"
        r"\b(exceeded?|meets?|met|reached|aligned?|complies?|qualif)\b.{0,60}"
        r"\b(threshold|standards?|target|policy|limits?|criteria|requirements?)\b",
        re.I,
    ),
    # English: "exceed/meet/align/comply with ... SLA/threshold/standard/policy"
    re.compile(
        r"\b(exceed|meets?|align|comply|qualif)\b.{0,50}"
        r"\b(sla|standards?|target|policy|limits?|criteria)\b",
        re.I,
    ),
    # English: "compare[d] with/against ... policy/criteria/standard/condition"
    re.compile(
        r"\bcompare[ds]?\b.{0,60}\b(policy|criteria|standards?|conditions?|requirements?|sla)\b",
        re.I,
    ),
    # English: "qualify for ... program/policy/criteria"
    re.compile(r"\bqualif(y|ies|ied)\b.{0,80}\b(program|policy|criteria|standard)\b", re.I),
]

# Tier 3 — Pure data: aggregation/listing keywords
_DATA_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"\b(total|jumlah|berapa|ranking|top\s*\d|tertinggi|terendah|rata-rata|average)\b",
        re.I,
    ),
    re.compile(
        r"\b(per\s+(bulan|tahun|wilayah|kota|provinsi|maret|april|januari|februari|region|month|year))\b",
        re.I,
    ),
    re.compile(
        r"\b(churn\s+risk|utilisasi\s+jaringan|outstanding\s+kredit|realisasi\s+anggaran"
        r"|network\s+utilization|budget\s+reali[sz]ation|credit\s+exposure)\b",
        re.I,
    ),
    # English data aggregation starters
    re.compile(
        r"\b(how\s+many|how\s+much|what\s+is\s+the\s+(total|number|count|average)"
        r"|which\s+.{0,30}\s+(highest|lowest|most|least|top|bottom))\b",
        re.I,
    ),
]

# Policy-only words — presence shifts ambiguous questions toward dokumen
_POLICY_WORDS = re.compile(
    r"\b(kebijakan|regulasi|prosedur|sla|standar|ketentuan|syarat|peraturan"
    r"|penalti|denda|apbd|sanksi"
    r"|policy|regulation|procedure|standard|requirement|provision|rule"
    r"|penalty|sanction|compliance)\b",
    re.I,
)


def _keyword_classify(question: str) -> AnswerMode | None:
    """Fast keyword-based pre-classifier.

    Returns None when the question is ambiguous and needs LLM classification.
    """
    # Tier 1 — show/display verbs always mean "data"
    if _SHOW_VERBS.match(question):
        logger.debug("Show-verb match -> data: %s", question[:60])
        return "data"

    # Tier 2 — combined comparison patterns
    for pat in _GABUNGAN_PATTERNS:
        if pat.search(question):
            return "combined"

    policy_words = bool(_POLICY_WORDS.search(question))
    data_match   = any(pat.search(question) for pat in _DATA_PATTERNS)

    # Tier 3 — pure data (aggregation without any policy reference)
    if data_match and not policy_words:
        return "data"

    # Tier 4 — pure document (policy/procedure without data aggregation)
    if policy_words and not data_match:
        return "document"

    return None  # ambiguous — let LLM decide


def _strip_thinking(text: str) -> str:
    """Remove reasoning-model <think> blocks so only the final answer remains."""
    return _THINK_RE.sub("", text).strip()


def _extract_mode(text: str) -> AnswerMode:
    """Extract routing mode from LLM response text.

    Tries exact lookup first, then scans for any known keyword in the text.
    Precedence: gabungan > data > dokumen (most -> least specific).
    Falls back to "document" if nothing matches.
    """
    cleaned = _strip_thinking(text).lower().strip()

    # Exact match (ideal case — model returned only one word)
    exact = _MODE_MAP.get(cleaned)
    if exact:
        return exact

    # Keyword scan — model added punctuation, explanation, or extra text.
    # Check Indonesian words first (router prompt is in Bahasa Indonesia).
    for keyword in ("gabungan", "combined", "data", "structured", "sql", "dokumen", "document"):
        if keyword in cleaned:
            return _MODE_MAP[keyword]

    return "document"


def classify_question(question: str, history: list[dict] | None = None) -> AnswerMode:
    """Classify the question into a routing mode using the LLM.

    Keyword heuristics run first; LLM is called only for ambiguous questions.
    history — last N conversation turns, used to resolve follow-up questions that
              are ambiguous without context (e.g. "how about for telco?").
    Returns "document" as safe default on any ambiguity or LLM error.
    """
    # Fast path — no LLM call needed
    heuristic = _keyword_classify(question)
    if heuristic is not None:
        logger.info("Classified '%s...' -> %s (heuristic)", question[:50], heuristic)
        return heuristic

    # Slow path — LLM classification for ambiguous questions
    try:
        llm = get_llm_client()
        messages = build_router_prompt(question, history=history)
        response = llm.chat(messages, temperature=0.0, max_tokens=10)
        mode = _extract_mode(response.content)
        logger.info(
            "Classified '%s...' -> %s (llm, raw=%r)",
            question[:50], mode, response.content[:80],
        )
        return mode
    except Exception as exc:
        logger.warning("Router classification failed: %s -- defaulting to 'document'", exc)
        return "document"
