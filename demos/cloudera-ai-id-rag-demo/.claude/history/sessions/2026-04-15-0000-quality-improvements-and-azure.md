# Session Log — 2026-04-15 — Quality Improvements, Azure OpenAI & Bug Fixes

## Goals
1. Fix LLM settings (base URL, API key) being lost after app restart
2. Fix combined (gabungan) queries always returning Document RAG instead of using SQL
3. Fix auto-restart not working after `/configure` changes on Windows
4. Add Azure OpenAI as a supported LLM provider
5. Test all 36 sample questions across 3 domains × 2 languages and fix all findings
6. Apply quality improvement recommendations
7. Upgrade embeddings from `multilingual-e5-base` to `multilingual-e5-large`
8. Fix SQL result numbers displaying in scientific notation (2.368e+10)
9. Fix UnicodeEncodeError on Windows from `→` in log messages

---

## Work Completed

### Bug Fix: Settings lost on restart (`src/config/settings.py`)
- Root cause: pydantic-settings reads `env_file` into typed fields only; generic keys like
  `LLM_BASE_URL` are properties (not fields), so pydantic silently ignores them from the file.
- Fix: Added `_load_override_env(path)` that reads `data/.env.local` line-by-line into
  `os.environ` **before** the `Settings()` singleton is constructed.
- Uses `setdefault` semantics: only sets keys not already in environment (platform vars win).

### Bug Fix: Gabungan queries returning wrong mode (`src/orchestration/router.py`)
- Root cause 1: `_MODE_MAP.get(raw)` exact-match failed when reasoning models return
  `<think>...thinking...</think>\ngabungan` — the thinking prefix broke the lookup.
- Root cause 2: Combined/gabungan questions phrased as policy comparisons ("apakah X
  sudah sesuai target?") routed correctly but then SQL generation returned
  `TIDAK_DAPAT_DIJAWAB` because the full comparison phrasing confused the SQL model.
- Fix 1: Added `_strip_thinking()` regex + fuzzy `_extract_mode()` keyword scan in router.
- Fix 2: Added 4-tier heuristic classification system:
  - Tier 1: `_SHOW_VERBS` — "tampilkan/show/list/display" always → data
  - Tier 2: `_GABUNGAN_PATTERNS` — 10 regex patterns for Indonesian + English comparison phrases
  - Tier 3: pure data (aggregation without policy) / pure dokumen
  - Tier 4: LLM fallback with thinking-tag stripping
- Extended `_POLICY_WORDS` with `penalti|denda|apbd|sanksi|penalty|sanction|compliance`

### Bug Fix: `<think>` tags in non-streaming calls (`src/sql/query_generator.py`)
- Added `re.sub(r"<think>.*?</think>", "", raw_sql, flags=re.DOTALL)` before SQL parsing.
- Added explicit `TIDAK_DAPAT_DIJAWAB` guard to raise clean `SqlGuardrailError`.

### Bug Fix: Auto-restart after configure (`app/api.py`)
- Root cause: uvicorn `--reload` creates a parent reloader process holding the TCP socket.
  Killing only the worker caused the reloader to immediately restart the old worker.
- Fix: Capture `parent_pid = os.getppid()`, then PowerShell `taskkill /F /PID {parent_pid} /T`
  to kill the entire reloader tree before spawning a fresh uvicorn process.
- Changed from `DETACHED_PROCESS` to `CREATE_NO_WINDOW (0x08000000)` — PowerShell is a
  console app and exits immediately when detached.

### Feature: Azure OpenAI provider (`app/api.py`, `app/static/configure.html`, `src/llm/inference_client.py`)
- Added `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`,
  `AZURE_OPENAI_API_VERSION` to `_CONFIGURE_ALLOWED_KEYS` in `api.py`.
- Added Azure option to provider dropdown in `configure.html` with 4 dedicated fields.
- `inference_client.py` uses `AzureOpenAI` SDK when `LLM_PROVIDER=azure`.

### Quality: Hybrid BM25 + FAISS retrieval (`src/retrieval/retriever.py`)
- Complete rewrite with Reciprocal Rank Fusion combining FAISS semantic search + BM25 keyword search.
- Constants: `_MAX_SCORE=1.2`, `_RRF_K=60`, `_FAISS_WEIGHT=0.6`, `_BM25_WEIGHT=0.4`.
- Thread-safe BM25 index cache per domain; `invalidate_bm25_cache()` for post-ingestion reset.
- Falls back to pure FAISS if BM25 fails or query < 2 words.
- Added `rank-bm25>=0.2.2,<1.0.0` to `requirements.txt`.

### Quality: SQL schema enrichment (`src/sql/metadata.py`)
- Added `_COLUMN_DESCRIPTIONS` dict: 40+ entries mapping `table.column` → semantic descriptions
  for all 9 tables (kredit_umkm, nasabah, cabang, pelanggan, jaringan, penggunaan_data,
  anggaran_daerah, layanan_publik, penduduk).
- `build_schema_context()` now outputs enriched schema with inline SQL comments.

### Quality: Increased conversation history (`src/llm/prompts.py`)
- `MAX_HISTORY_TURNS`: 3 → 5 (keeps last 10 messages = 5 user + 5 assistant).
- Improved `SYSTEM_PROMPT_COMBINED` with explicit instructions for partial-data scenarios.
- Added `SYSTEM_PROMPT_DATA_EXTRACTION` with 9 bilingual few-shot examples.
- Added `build_data_extraction_prompt(question)` function.

### Quality: Dual-question retrieval for gabungan (`src/orchestration/answer_builder.py`)
- Added `_extract_data_question(question)` — calls LLM to rephrase combined questions
  into pure SQL queries (strips policy-comparison phrasing).
- Dual retrieval pass for gabungan: Pass 1 (original) retrieves policy chunks,
  Pass 2 (data-extracted) retrieves quantitative metric chunks; deduplicated by
  `(source_path, chunk_index)`.
- Added `synthesis_input_chars: int = 0` field to `AnswerPrep` for token usage estimation.

### Feature: Token usage display (`app/api.py`, `app/static/index.html`)
- SSE `done` event now includes `usage: {input_tokens, output_tokens, total_tokens}`.
- Estimated from character counts: `synthesis_input_chars // 4` input, `len(full_text) // 4` output.
- UI renders token count below citations: `≈ N in · M out · T total tokens` with tooltip.

### Upgrade: multilingual-e5-large embeddings (`src/config/settings.py`, `src/retrieval/embeddings.py`)
- Changed `embeddings_model` default from `intfloat/multilingual-e5-base` to
  `intfloat/multilingual-e5-large` (560M params, 1024-dim, better Bahasa Indonesia recall).
- Removed `local_files_only: True` from `HuggingFaceEmbeddings` kwargs (model now cached locally).
- Vector store rebuilt with 63 chunks at 1024-dim.

### Bug Fix: Scientific notation in SQL results (`src/sql/executor.py`)
- `to_markdown_table()` now formats numeric columns before `to_markdown()`:
  - Integer-valued floats: `f"{int(v):,}"` → `23,680,000,000`
  - True floats: `f"{v:,.2f}"` → `1,234.56`

### Bug Fix: UnicodeEncodeError on Windows (`src/orchestration/router.py`)
- Replaced `→` (U+2192) with `->` in all `logger.info/debug` calls.
- The `→` character caused `UnicodeEncodeError` on Windows cp1252 consoles, which
  was silently crashing the uvicorn worker after file-change reloads.

### UI: Paper-plane send icon direction
- `IcoSend` SVG updated so the paper-plane nose points right (was pointing upper-left).

---

## Decisions Made

1. **`_load_override_env()` pre-boot pattern** — pydantic-settings can't read generic keys
   into properties. Pre-loading into `os.environ` before `Settings()` is the cleanest fix
   without forking pydantic-settings.

2. **Kill parent PID on restart** — uvicorn `--reload` reloader holds the port. Must kill
   the reloader process tree (parent), not just the worker, to free the port for restart.

3. **Dual-question retrieval for gabungan** — single-pass retrieval misses one of the two
   semantic poles (policy vs. data). Two-pass with deduplication ensures both are covered.

4. **multilingual-e5-large over e5-base** — better recall for Bahasa Indonesia, especially
   short entity-name queries. Requires ~3 GB RAM; acceptable for 4+ GB Cloudera profiles.

5. **RRF over score averaging** — Reciprocal Rank Fusion is robust to FAISS L2 / BM25
   score-scale differences. Simple averaging would over-weight whichever scorer produces
   larger absolute values.

---

## Files Changed

### Modified
- `src/config/settings.py` — `_load_override_env()`, `multilingual-e5-large` default
- `src/retrieval/embeddings.py` — removed `local_files_only`
- `src/retrieval/retriever.py` — full rewrite: hybrid BM25+FAISS with RRF
- `src/sql/executor.py` — number formatting in `to_markdown_table()`
- `src/sql/metadata.py` — full rewrite: `_COLUMN_DESCRIPTIONS` dict
- `src/sql/query_generator.py` — `<think>` tag stripping, `TIDAK_DAPAT_DIJAWAB` guard
- `src/orchestration/router.py` — 4-tier heuristic, `_strip_thinking()`, `->` in logs
- `src/orchestration/answer_builder.py` — `_extract_data_question()`, dual retrieval, `synthesis_input_chars`
- `src/llm/prompts.py` — `MAX_HISTORY_TURNS=5`, data extraction prompt, improved combined prompt
- `src/llm/inference_client.py` — Azure OpenAI provider support
- `app/api.py` — Azure keys in allowlist, kill-parent restart, token usage in `done` event
- `app/static/configure.html` — Azure OpenAI provider fields
- `app/static/index.html` — token usage display, paper-plane icon direction
- `requirements.txt` — added `rank-bm25>=0.2.2,<1.0.0`

### New files
- `.claude/history/sessions/2026-04-15-0000-quality-improvements-and-azure.md` (this file)
- `.claude/history/changelogs/2026-04-15.md`
- `.claude/history/decisions/2026-04-15-retrieval-and-routing.md`
