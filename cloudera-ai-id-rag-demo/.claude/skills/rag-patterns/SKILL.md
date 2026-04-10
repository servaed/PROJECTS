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

## Retrieval

`src/retrieval/retriever.py` runs similarity search and returns `RetrievedChunk` objects.
Each chunk carries: `text`, `title`, `source_path`, `chunk_index`, `score`, `ingest_timestamp`.

## Citation Rules

- **Never invent citations.** Only emit `DocumentCitation` objects built from actual retrieved chunks.
- Always show: title, source path, chunk index, excerpt, and ingestion timestamp.
- Excerpt is max 300 characters. Truncate with `…` if longer.
- Deduplication: if the same `source_path:chunk_index` appears multiple times, show it once.

## Answer Grounding

For document-mode answers, pass all retrieved chunks as context to the LLM via `build_document_prompt()`.
If no chunks are retrieved, return `ANSWER_NOT_FOUND_ID` — do not call the LLM with empty context.

## Embeddings Model

Default: `intfloat/multilingual-e5-base` — supports Bahasa Indonesia and English.
Override with `EMBEDDINGS_MODEL` env var. For OpenAI embeddings: set `EMBEDDINGS_PROVIDER=openai`.

## Adding New Document Types

1. Add a loader function in `document_loader.py` following the `(bytes, Path) -> str` signature.
2. Register it in `_LOADERS` dict with the file extension key.
3. Add the extension to `SUPPORTED_EXTENSIONS` in `files_adapter.py`.
