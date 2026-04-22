"""Retrieval service — runs hybrid BM25 + FAISS similarity search over the vector store.

Hybrid strategy:
  1. FAISS cosine similarity — semantic / embedding-based match
  2. BM25 keyword search    — exact term / entity match
  3. Reciprocal Rank Fusion — combines both ranked lists into a single ranking

BM25 catches entity names, branch codes, and numeric IDs that embedding models
often miss.  FAISS captures semantic similarity for paraphrased or translated
queries.  Together they improve recall significantly over either alone.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from src.config.logging import get_logger
from src.retrieval.embeddings import get_embeddings
from src.retrieval.vector_store import load_vector_store

logger = get_logger(__name__)

# ── Tuning constants ───────────────────────────────────────────────────────

# FAISS returns L2 distance scores (lower = more similar).
# Chunks above this threshold are considered irrelevant noise.
# multilingual-e5-base: relevant ≈ 0.0–0.8, noise > 1.2
_MAX_SCORE = 1.2

# RRF constant — higher values reduce the impact of rank differences at the top
_RRF_K = 60

# Blend weight: 0.0 = pure BM25, 1.0 = pure FAISS, 0.5 = equal weight
# 0.6 gives semantic search a slight edge while preserving BM25 entity recall
_FAISS_WEIGHT = 0.6
_BM25_WEIGHT = 1.0 - _FAISS_WEIGHT

# ── BM25 index cache ───────────────────────────────────────────────────────

_bm25_lock = threading.Lock()
_bm25_cache: dict[str, tuple] = {}   # domain_key → (BM25Okapi, [Document])


def _build_bm25_index(store, domain: str | None, language: str | None) -> tuple:
    """Build a BM25 index over the documents in the FAISS store.

    Documents are filtered to the requested domain and language before indexing.
    Results are cached per (domain, language); call _invalidate_bm25_cache() after
    re-ingestion to force a rebuild.
    """
    from rank_bm25 import BM25Okapi

    # LangChain FAISS uses InMemoryDocstore — access via private _dict.
    all_docs = list(store.docstore._dict.values())

    docs = all_docs
    if domain:
        docs = [d for d in docs if d.metadata.get("domain") == domain]
    if language:
        docs = [d for d in docs if d.metadata.get("language", "id") == language]

    if not docs:
        logger.warning("BM25: no documents found for domain=%s language=%s", domain, language)
        return None, []

    # Simple whitespace tokenisation works well for both Indonesian and English.
    corpus = [d.page_content.lower().split() for d in docs]
    bm25   = BM25Okapi(corpus)
    logger.debug(
        "BM25 index built: %d docs (domain=%s, language=%s)",
        len(docs), domain or "all", language or "any",
    )
    return bm25, docs


def _get_bm25(store, domain: str | None, language: str | None) -> tuple:
    """Return cached BM25 index, building it on first call per (domain, language)."""
    key = f"{domain or '__all__'}:{language or '__any__'}"
    with _bm25_lock:
        if key not in _bm25_cache:
            _bm25_cache[key] = _build_bm25_index(store, domain, language)
        return _bm25_cache[key]


def invalidate_bm25_cache() -> None:
    """Clear the BM25 index cache.  Call after re-ingesting documents."""
    with _bm25_lock:
        _bm25_cache.clear()
    logger.info("BM25 cache invalidated")


# ── Main retriever ─────────────────────────────────────────────────────────


@dataclass
class RetrievedChunk:
    text: str
    title: str
    source_path: str
    chunk_index: int
    score: float
    ingest_timestamp: str


def _rrf_fuse(
    faiss_results: list[tuple],   # (Document, float_score) sorted by score asc
    bm25_docs: list,              # all docs in BM25 index (same order as corpus)
    bm25_scores: list[float],     # BM25 score per doc in bm25_docs
    domain: str | None,
    max_score: float,
    language: str | None = None,
) -> list[tuple]:
    """Combine FAISS and BM25 results with Reciprocal Rank Fusion.

    Returns a list of (Document, rrf_score) sorted by rrf_score descending.
    """
    # Build FAISS rank map — only keep chunks below the score threshold
    faiss_rank: dict[str, int] = {}
    faiss_doc_map: dict[str, object] = {}
    rank = 0
    for doc, score in faiss_results:
        if score > max_score:
            continue
        if domain and doc.metadata.get("domain") != domain:
            continue
        if language and doc.metadata.get("language", "id") != language:
            continue
        key = doc.page_content[:120]   # stable identity key
        faiss_rank[key] = rank
        faiss_doc_map[key] = doc
        rank += 1

    # Build BM25 rank map — sort indices by descending BM25 score
    bm25_order = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
    bm25_rank: dict[str, int] = {}
    bm25_doc_map: dict[str, object] = {}
    for rank, idx in enumerate(bm25_order):
        key = bm25_docs[idx].page_content[:120]
        bm25_rank[key] = rank
        bm25_doc_map[key] = bm25_docs[idx]

    # Collect all candidate keys
    all_keys = set(faiss_rank) | set(bm25_rank)

    fused: list[tuple] = []
    for key in all_keys:
        fr = faiss_rank.get(key, len(faiss_rank) + 100)
        br = bm25_rank.get(key,  len(bm25_rank)  + 100)
        rrf = (
            _FAISS_WEIGHT * (1.0 / (_RRF_K + fr)) +
            _BM25_WEIGHT  * (1.0 / (_RRF_K + br))
        )
        doc = faiss_doc_map.get(key) or bm25_doc_map.get(key)
        fused.append((doc, rrf))

    fused.sort(key=lambda t: t[1], reverse=True)
    return fused


def retrieve(
    question: str,
    top_k: int = 5,
    domain: str | None = None,
    language: str | None = None,
    max_score: float = _MAX_SCORE,
    use_hybrid: bool = True,
) -> list[RetrievedChunk]:
    """Retrieve the top-k most relevant chunks using hybrid BM25 + FAISS search.

    When use_hybrid=False, falls back to pure FAISS (e.g. for very short queries
    where BM25 tokenisation is unreliable).

    domain     — restricts results to chunks tagged with that domain.
    language   — restricts results to "id" (Bahasa Indonesia) or "en" (English).
    max_score  — L2 distance ceiling for FAISS results; set to float('inf') to
                 disable filtering.
    use_hybrid — enable BM25 keyword re-ranking alongside FAISS (default True).

    Returns an empty list if the vector store has not been built yet.
    """
    embeddings = get_embeddings()
    store = load_vector_store(embeddings)

    if store is None:
        logger.warning("Vector store not available — cannot retrieve documents.")
        return []

    # Fetch more candidates so filtering + fusion have enough material to work with
    fetch_k = max(top_k * 6, 30) if (domain or language) else max(top_k * 3, 15)
    faiss_results = store.similarity_search_with_score(question, k=fetch_k)

    if use_hybrid and len(question.split()) >= 2:
        try:
            bm25, bm25_docs = _get_bm25(store, domain, language)
            if bm25 is not None:
                bm25_scores = bm25.get_scores(question.lower().split())
                fused = _rrf_fuse(
                    faiss_results, bm25_docs, bm25_scores, domain, max_score, language
                )
                # fused is sorted by rrf_score desc; extract Document objects
                chunks = []
                for doc, _rrf_score in fused:
                    meta = doc.metadata
                    chunks.append(
                        RetrievedChunk(
                            text=doc.page_content,
                            title=meta.get("title", "Untitled Document"),
                            source_path=meta.get("source_path", ""),
                            chunk_index=meta.get("chunk_index", 0),
                            score=_rrf_score,
                            ingest_timestamp=meta.get("ingest_timestamp", ""),
                        )
                    )
                    if len(chunks) >= top_k:
                        break
                logger.debug(
                    "Hybrid retrieved %d chunks (domain=%s, language=%s) for: %.60s",
                    len(chunks), domain or "any", language or "any", question,
                )
                return chunks
        except Exception as exc:
            logger.warning("BM25 hybrid search failed (%s) — falling back to FAISS only", exc)

    # Pure FAISS fallback
    chunks = []
    for doc, score in faiss_results:
        if score > max_score:
            continue
        meta = doc.metadata
        if domain and meta.get("domain") != domain:
            continue
        if language and meta.get("language", "id") != language:
            continue
        chunks.append(
            RetrievedChunk(
                text=doc.page_content,
                title=meta.get("title", "Untitled Document"),
                source_path=meta.get("source_path", ""),
                chunk_index=meta.get("chunk_index", 0),
                score=float(score),
                ingest_timestamp=meta.get("ingest_timestamp", ""),
            )
        )
        if len(chunks) >= top_k:
            break

    logger.debug(
        "FAISS retrieved %d chunks (domain=%s, language=%s, max_score=%.2f) for: %.60s",
        len(chunks), domain or "any", language or "any", max_score, question,
    )
    return chunks
