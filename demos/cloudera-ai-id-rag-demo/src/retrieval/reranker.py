"""Cross-encoder reranker — re-scores retrieved chunks against the exact question.

Uses a lightweight cross-encoder model to rerank the top-K candidates returned by
the hybrid BM25+FAISS retriever.  Cross-encoders jointly encode (query, passage)
pairs and produce a relevance score that is much more accurate than embedding
cosine similarity alone, at the cost of one forward pass per (query, chunk) pair.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2  (~90 MB, 6-layer, fast on CPU)
Controlled by env vars:
  RERANKER_ENABLED=true   (default: true)
  RERANKER_MODEL=<hf-id>  (default: cross-encoder/ms-marco-MiniLM-L-6-v2)
  RERANKER_TOP_K=5        (keep top-K after reranking, default 5)
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from src.config.logging import get_logger
from src.config.settings import settings

if TYPE_CHECKING:
    from src.retrieval.retriever import RetrievedChunk

logger = get_logger(__name__)

_reranker_lock = threading.Lock()
_reranker_model = None          # lazy-loaded CrossEncoder instance
_reranker_failed = False        # set True after first load failure to avoid retrying


def _get_reranker():
    """Return the cached cross-encoder model, loading it on first call."""
    global _reranker_model, _reranker_failed
    if not settings.reranker_enabled:
        return None
    with _reranker_lock:
        if _reranker_model is not None:
            return _reranker_model
        if _reranker_failed:
            return None
        try:
            from sentence_transformers import CrossEncoder
            model_name = settings.reranker_model
            logger.info("Loading cross-encoder reranker: %s", model_name)
            _reranker_model = CrossEncoder(model_name, max_length=512)
            logger.info("Reranker loaded: %s", model_name)
            return _reranker_model
        except Exception as exc:
            logger.warning("Reranker load failed (%s) — reranking disabled", exc)
            _reranker_failed = True
            return None


def rerank(
    question: str,
    chunks: list["RetrievedChunk"],
    top_k: int | None = None,
) -> list["RetrievedChunk"]:
    """Rerank retrieved chunks by cross-encoder relevance score.

    Returns chunks ordered by descending cross-encoder score, truncated to
    top_k (falls back to settings.reranker_top_k when None).

    Falls through unchanged if the reranker is disabled, unavailable, or the
    chunk list has 1 or fewer entries (nothing to reorder).
    """
    if not chunks or len(chunks) <= 1:
        return chunks

    model = _get_reranker()
    if model is None:
        return chunks

    k = top_k if top_k is not None else settings.reranker_top_k

    try:
        import math
        pairs = [(question, c.text[:400]) for c in chunks]
        raw_scores = model.predict(pairs)
        reranked = sorted(
            zip(chunks, raw_scores),
            key=lambda t: t[1],
            reverse=True,
        )
        # Convert cross-encoder logits to [0, 1] via sigmoid so the UI badge is meaningful.
        # ms-marco-MiniLM logits are typically in the range [-10, +10].
        result = []
        for c, logit in reranked[:k]:
            sig = 1.0 / (1.0 + math.exp(-float(logit)))
            result.append(c.__class__(
                text=c.text,
                title=c.title,
                source_path=c.source_path,
                chunk_index=c.chunk_index,
                score=round(sig, 4),
                ingest_timestamp=c.ingest_timestamp,
            ))
        logger.debug("Reranker: %d -> %d chunks for: %.60s", len(chunks), len(result), question)
        return result
    except Exception as exc:
        logger.warning("Reranking failed (%s) — returning original order", exc)
        return chunks[:k]


def invalidate_reranker_cache() -> None:
    """Unload the cached model (useful after changing RERANKER_MODEL at runtime)."""
    global _reranker_model, _reranker_failed
    with _reranker_lock:
        _reranker_model = None
        _reranker_failed = False
    logger.info("Reranker cache cleared")
