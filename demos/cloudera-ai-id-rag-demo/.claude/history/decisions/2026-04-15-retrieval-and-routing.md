# Decision Log — 2026-04-15: Retrieval, Routing, and Restart Architecture

---

## Decision 1: Hybrid BM25+FAISS with Reciprocal Rank Fusion

### Context
Pure FAISS semantic search was missing entity names (branch codes, wilayah names, service
types like "IMB") because embedding models compress semantics, not exact strings.

### Options Considered
1. **Pure FAISS** — simple, already implemented
2. **FAISS + BM25 with score averaging** — easy to implement, but FAISS L2 and BM25 scores
   are on different scales; weighting is fragile
3. **FAISS + BM25 with Reciprocal Rank Fusion** — scale-independent, well-studied in IR

### Chosen Option
**RRF with `_FAISS_WEIGHT=0.6`, `_BM25_WEIGHT=0.4`**

### Rationale
RRF combines rank positions rather than raw scores, making it robust to the L2/BM25 scale
mismatch. FAISS gets a slight edge (0.6) because semantic recall is more important than
keyword recall for the Indonesian enterprise use case. BM25 at 0.4 still significantly
improves entity recall without overpowering semantic matching.

### Impact
- `src/retrieval/retriever.py` fully rewritten
- `rank-bm25` added to `requirements.txt`
- BM25 index cached per domain with `threading.Lock` for thread safety

---

## Decision 2: _extract_data_question() for Gabungan SQL Generation

### Context
Combined (gabungan) questions like "Apakah outstanding kredit UMKM di Jakarta sudah sesuai
target ekspansi 15%?" contain policy-comparison framing that causes the SQL generator to
return `TIDAK_DAPAT_DIJAWAB` — it can't find a 15% target in the database and gives up
instead of returning the raw outstanding total.

### Options Considered
1. **Improve SQL system prompt** — tell the model to extract the measurable part itself
2. **Pre-processing LLM call** — separate extraction step before SQL generation
3. **Post-processing fallback** — retry with simplified question on TIDAK_DAPAT_DIJAWAB

### Chosen Option
**Pre-processing LLM call (`_extract_data_question()` in `answer_builder.py`)**

### Rationale
Pre-processing is cleaner than post-processing (no retry loop) and more reliable than
asking the SQL model to do two jobs at once. The extraction LLM call uses a dedicated
`SYSTEM_PROMPT_DATA_EXTRACTION` with 9 bilingual few-shot examples covering all sample
question types. The extracted question is reused for both SQL generation AND the second
retrieval pass, so the extra LLM call pays for itself.

### Impact
- One additional LLM call per gabungan question (adds ~1–2 s latency)
- `src/orchestration/answer_builder.py` updated
- `src/llm/prompts.py`: new `SYSTEM_PROMPT_DATA_EXTRACTION` and `build_data_extraction_prompt()`

---

## Decision 3: 4-Tier Heuristic Router

### Context
The original router used a single LLM call for all classification. This was:
- Slow for questions with obvious intent ("Tampilkan semua kredit..." → always data)
- Brittle with reasoning models that prepend `<think>` blocks to the output
- Missing bilingual coverage (Indonesian patterns didn't match English questions)

### Options Considered
1. **Single LLM call** — simple, handles all cases
2. **Regex-only heuristics** — fast, but misses ambiguous cases
3. **4-tier: show-verbs → gabungan patterns → keyword classify → LLM fallback**

### Chosen Option
**4-tier heuristic with LLM fallback**

### Rationale
Most questions are classifiable without an LLM call (saves ~1 s per question). The LLM
fallback handles genuine ambiguity. `_strip_thinking()` + fuzzy `_extract_mode()` make the
LLM path robust to reasoning-model output formats.

### Impact
- `src/orchestration/router.py` fully rewritten
- LLM call only fires for ambiguous questions (~20% of real queries)
- Routing smoke tests: 13/13 passing

---

## Decision 4: multilingual-e5-large Default

### Context
`multilingual-e5-base` (768-dim) was chosen originally for demo portability. After confirming
that demo machines will typically have 4–8 GB RAM, the larger model became viable.

### Options Considered
1. **Keep e5-base** — less RAM, already cached
2. **Upgrade to e5-large** — better recall, especially for short entity queries
3. **paraphrase-multilingual-mpnet-base-v2** — comparable size to base, slightly different strengths

### Chosen Option
**multilingual-e5-large**

### Rationale
The 1024-dim model meaningfully improves recall for short Bahasa Indonesia entity queries
(wilayah names, service codes, credit quality labels). Peak RAM for the full app is ~3–3.5 GB,
comfortably within a 4 GB Cloudera workspace profile.

### Impact
- `src/config/settings.py`: `embeddings_model = "intfloat/multilingual-e5-large"`
- `src/retrieval/embeddings.py`: removed `local_files_only` (model cached locally after first download)
- Vector store rebuilt; old `e5-base` index is incompatible (different dimension)

---

## Decision 5: Kill Parent PID for Restart

### Context
`POST /api/configure` triggers an app restart so new env vars take effect. The original
implementation used `os._exit(0)` on the worker, expecting the reloader to restart it with
new code. But the reloader also holds the old settings in memory and restarts the worker
with the old environment.

### Options Considered
1. **`os._exit(0)` on worker** — reloader restarts worker immediately, but env is stale
2. **Kill worker + reloader tree, spawn fresh uvicorn** — clean slate, new env
3. **Hot-reload env only, no restart** — works for some settings, not for DB connections or embeddings

### Chosen Option
**Kill parent PID (reloader) tree + spawn fresh uvicorn**

`parent_pid = os.getppid()` captured before the kill; PowerShell `taskkill /F /PID {parent_pid} /T`
kills the entire tree; `subprocess.Popen(["powershell", "-Command", f"Start-Process uvicorn ..."])`
with `CREATE_NO_WINDOW` spawns the new process.

### Rationale
Killing the reloader frees the TCP port and purges all in-memory state. `CREATE_NO_WINDOW`
is used instead of `DETACHED_PROCESS` because PowerShell is a console app and exits
immediately when fully detached.

### Impact
- `app/api.py` restart endpoint updated
- `/configure` wizard "Save & Restart" button now reliably starts a fresh process
