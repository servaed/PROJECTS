---
name: rag-patterns
description: Document ingestion, chunking, retrieval, answer grounding, and citation patterns for the RAG pipeline.
---

# Skill: RAG Patterns

## Ingestion Pipeline

1. **Load** — `src/retrieval/document_loader.py` reads files via the storage adapter
2. **Chunk** — `src/retrieval/chunking.py` splits text with overlap (default: 800 chars, 100 overlap)
3. **Embed** — `src/retrieval/embeddings.py` encodes chunks via pluggable embeddings provider
4. **Index** — `src/retrieval/vector_store.py` saves FAISS index to disk

Run ingestion:
```bash
python -m src.retrieval.document_loader
```

## Retrieval — 3-Stage Pipeline

`src/retrieval/retriever.py` runs a **3-stage retrieval** pipeline:

**Stage 1 — Semantic search**: FAISS cosine similarity using `multilingual-e5-large` (1024-dim). Returns top-40 candidates.

**Stage 2 — Keyword re-ranking**: BM25 (`rank-bm25`) runs in parallel; results fused with FAISS via Reciprocal Rank Fusion (RRF). Produces a fused top-20.

**Stage 3 — Cross-encoder reranking**: `cross-encoder/ms-marco-MiniLM-L-6-v2` (~90 MB, lazy-loaded, thread-safe singleton) scores fused candidates and returns top-K. Controlled by:
- `RERANKER_ENABLED` (default: `true`) — set `false` to skip stage 3
- `RERANKER_MODEL` — override the cross-encoder checkpoint
- `RERANKER_TOP_K` — number of final chunks passed to LLM

Each `RetrievedChunk` carries: `text`, `title`, `source_path`, `chunk_index`, `score`, `ingest_timestamp`, `domain`, `language`.

Retriever always filters by `domain` (pass `domain=None` for All-Domains mode) and optionally by `language` so each UI language only sees chunks from its own knowledge base (`_en.txt` files → `language="en"`).

## Citation Rules

- **Never invent citations.** Only emit `DocumentCitation` objects built from actual retrieved chunks.
- Always show: title, source path, chunk index, excerpt, and ingestion timestamp.
- Excerpt is max 300 characters. Truncate with `…` if longer.
- Deduplication: if the same `source_path:chunk_index` appears multiple times, show it once.

## Answer Grounding

For document-mode answers, pass all retrieved chunks as context to the LLM via `build_document_prompt()`.
If no chunks are retrieved, return `get_answer_not_found(language)` — do not call the LLM with empty context.
The fallback string is localised: Bahasa Indonesia for `language="id"`, English for `language="en"`.

## Embeddings Model

Default: `intfloat/multilingual-e5-large` (560M params, 1024-dim) — supports Bahasa Indonesia and English.
Override with `EMBEDDINGS_MODEL` env var. For OpenAI embeddings: set `EMBEDDINGS_PROVIDER=openai`.
Requires ~3 GB RAM; use OpenAI embeddings to reduce to ~2 GB total.

## Adding New Documents (via Upload UI)

Upload via the browser: `http://<app-url>/upload`
- Select domain (banking / telco / government) and language (ID or EN)
- File is saved to `data/sample_docs/{domain}/{filename}`
- English files must end in `_en` (e.g. `my_policy_en.txt`) — auto-appended if missing
- Optional: enable "Re-ingest after upload" to rebuild the vector store immediately

## All-Domains Mode

Set `domain="all"` in `/api/chat` → `retrieval_domain=None` → retriever skips the domain filter.
All 14 documents and all 9 SQL tables are visible. The "◉ All" tab in the sidebar triggers this.

## Agentic SQL Retry

In `combined` mode and `data` mode, if `validate_sql()` raises `SqlGuardrailError` or returns `TIDAK_DAPAT_DIJAWAB`, the orchestrator auto-rephrases the question once and retries SQL generation before falling back to `get_answer_sql_failed(language)`.

## MLflow Tracking

`src/utils/metrics.py` maintains an in-memory ring buffer of inference runs (always on). If `MLFLOW_TRACKING_URI` is set, runs are also logged to MLflow asynchronously (non-blocking). Tracked: latency_ms, tokens_used, provider, model, mode, domain, language.

## Adding New Document Types

1. Add a loader function in `document_loader.py` following the `(bytes, Path) -> str` signature.
2. Register it in `_LOADERS` dict with the file extension key.
3. Add the extension to `SUPPORTED_EXTENSIONS` in `files_adapter.py`.
