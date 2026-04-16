# CLAUDE.md — cloudera-ai-id-rag-demo

## Project Purpose
Demo repository for Indonesian enterprise customers showing a **bilingual conversational
assistant** (Bahasa Indonesia + English) deployed as a Cloudera AI Application. The assistant
answers from enterprise documents (RAG) and structured tables (SQL), with full source traceability
for presales demos in banking, telco, and government sectors.

## System Architecture
```
User (Bahasa Indonesia or English)
  → React SPA (port 8080) — sidebar domain tabs + language toggle
  → FastAPI Backend (app/api.py)
       ├─ GET  /              → index.html (React SPA chat interface)
       ├─ GET  /setup         → setup.html (health dashboard)
       ├─ GET  /configure     → configure.html (env var wizard)
       ├─ POST /api/chat      → SSE streaming (mode → token… → done)
       ├─ GET  /api/status    → live component status (sidebar indicators)
       ├─ GET  /api/samples   → sample prompts list (domain + lang filtered)
       ├─ GET  /api/domains   → available domain list
       ├─ GET  /api/setup     → detailed health report (used by /setup page)
       ├─ GET  /api/configure → current config state, secrets masked
       └─ POST /api/configure → validate → write data/.env.local → os.environ update
  → Orchestration Router (classify → dokumen / data / gabungan)
       ├─ Keyword heuristics (4-tier: show-verb → gabungan → data → dokumen)
       └─ LLM fallback for ambiguous questions
  → Document RAG  (loaders → chunking → BM25 + FAISS hybrid → RRF → retriever)
  → SQL Retrieval (schema discovery → guarded SQL gen → executor → number formatting)
  → LLM Provider (pluggable: Cloudera AI Inference / OpenAI-compatible / Bedrock / Anthropic / local)
  → Answer Builder (prepare_answer → stream_synthesis → finalize_answer)
       └─ Bilingual synthesis + citations + query trace
```

**Backend: FastAPI + uvicorn.** Serves the React SPA from `app/static/` and streams
LLM tokens via Server-Sent Events on `POST /api/chat`. Launched by `deployment/launch_app.sh`.

**Streamlit fallback (`app/main.py`)** is retained for local notebook/dev use only.
Production entry point is always `app/api.py`.

## Key Directories
| Path | Purpose |
|------|---------|
| `app/api.py` | **FastAPI entry point (production)** — all routes |
| `app/main.py` | Streamlit entry point (local/notebook fallback) |
| `app/static/index.html` | React SPA — chat interface (htm tagged templates, no build step) |
| `app/static/setup.html` | Health dashboard — auto-refreshes every 30 s |
| `app/static/configure.html` | Env-var wizard — saves to `data/.env.local` |
| `src/config/` | Settings (pydantic-settings), logging config |
| `src/llm/` | LLM abstraction base (`chat` + `stream_chat`), OpenAI-compatible client, bilingual prompts |
| `src/retrieval/` | Document loaders, chunking, embeddings (e5-large), FAISS + BM25 hybrid retriever |
| `src/sql/` | Schema metadata, SQL guardrails (sqlparse AST), query generator, executor (number formatting) |
| `src/orchestration/` | Router (4-tier heuristic + LLM), answer builder (prepare/stream/finalize), citations |
| `src/connectors/` | Storage adapters: HDFS, local files, database |
| `src/utils/` | Language helpers, unique ID generation |
| `data/sample_docs/` | Domain-segregated TXT documents (banking/, telco/, government/) |
| `data/sample_tables/` | SQLite seeder (`seed_database.py`) — 9 tables, 148+ rows |
| `data/vector_store/` | FAISS index + SHA-256 integrity hash (gitignored) |
| `deployment/` | `launch_app.sh` (step 0–5 startup), env var reference, deployment guide |
| `tests/` | Pytest unit tests (66 total across 4 suites) |
| `Dockerfile` / `.dockerignore` | Container image for Docker-based deployment path |
| `.claude/skills/` | Reusable Claude Code project skills |
| `.claude/history/` | Session logs, decisions, changelogs, prompts |

## Development Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Seed demo SQLite database
python data/sample_tables/seed_database.py

# Ingest sample documents into vector store
python -m src.retrieval.document_loader

# Run app locally on port 8080 (FastAPI + React SPA — production entry point)
uvicorn app.api:app --host 0.0.0.0 --port 8080 --reload

# Configure via browser (open after starting the app)
# http://localhost:8080/configure

# Run all tests
pytest tests/ -v

# Run full 36-question evaluation against running app
python eval_all.py
```

## Deployment Assumptions (Cloudera AI Applications)
- App **must** listen on **port 8080** — required by Cloudera AI Applications runtime
- Deploy via Git repo URL or Docker image in the Cloudera AI Applications UI
- All configuration via environment variables (see `.env.example`) **or** via `GET /configure` wizard
- Authentication handled by Cloudera AI platform (SSO / LDAP) — app does not implement its own auth
- `deployment/launch_app.sh` sources `data/.env.local` at step 0 before uvicorn starts
- Platform env vars always override `data/.env.local` values
- See `DEPLOYMENT.md` and `deployment/cloudera_ai_application.md` for full guides
- **Minimum resource profile**: 4 vCPU / 8 GB RAM (for `multilingual-e5-large` local embeddings)

## Configure Wizard (`/configure`)
- `GET /api/configure` returns current config state: value (masked for secrets) + source (`env` / `file` / `null`)
- `POST /api/configure` body: `{"env_vars": {"LLM_PROVIDER": "openai", ...}}`
  - Allowed keys: `_CONFIGURE_ALLOWED_KEYS` in `api.py`
  - Skips keys already set by platform env (warns in response)
  - Blank value = delete from override file
  - Writes `data/.env.local` and updates `os.environ` immediately
- Override file location: `_OVERRIDE_PATH = Path("data/.env.local")` in `api.py`

## Bilingual Support
The app responds in the same language the user asks in:
- `ChatRequest.language` (`"id"` or `"en"`) is sent from the frontend
- Threaded through `_chat_sse` → `prepare_answer` → `AnswerPrep.language`
- `_build_messages` passes `language` to all prompt builders
- System prompts use `{lang_rule}` placeholder → `_lang_rule(language)` in `prompts.py`
- Fallback strings (`not_found`, `sql_failed`) also localised via `get_answer_not_found(lang)` / `get_answer_sql_failed(lang)`
- SQL generation prompt is always Indonesian (internal directive only, not user-facing)

## Domain Selector (UI Sidebar)
- Three clickable icon tabs in the sidebar: 🏦 Banking · 📡 Telco · 🏛 Gov
- Language toggle below: Bahasa Indonesia / English
- `Sidebar` receives `domains`, `domain`, `language`, `onDomainChange`, `onLanguageChange` from `App`
- Domain/language controls removed from topbar to reduce clutter
- Switching domain resets auto-play and re-fetches sample prompts

## Coding Standards
- Python 3.10+
- Absolute imports only (`from src.retrieval.retriever import ...`)
- **All code, comments, and documentation in English**
- **LLM-facing system prompts in Bahasa Indonesia** (with `{lang_rule}` placeholder for bilingual)
- **User-visible UI strings in Bahasa Indonesia** (fallback messages, labels)
- No hardcoded credentials, endpoints, or model names — use `src/config/settings.py`
- Module-level docstrings on every file; inline comments only where logic is non-obvious
- Small, testable modules — one responsibility per file
- Type hints on all public function signatures
- **Logger format strings must use ASCII only** — `→` and `≥` crash Windows cp1252 console; use `->` and `>=`

## Security Notes
- SQL guardrails use **sqlparse AST walking** (not regex) — handles subqueries, CTEs, aliases
- FAISS vector store: SHA-256 integrity hash written after build, verified before load
- XSS: all LLM markdown output sanitised with DOMPurify before `dangerouslySetInnerHTML`
- `POST /api/configure` validates keys against allowlist; skips platform env vars
- `db_adapter.execute_read_query`: belt-and-suspenders SELECT guard at execution boundary
- LLM ping uses `ThreadPoolExecutor` + 5 s timeout to prevent uvicorn thread exhaustion
- SSE producer thread: `thread.join(timeout=60)` with alive-check log

## RAG Safety Rules
- Never fabricate citations, page numbers, or source metadata
- Always return source document metadata alongside retrieved chunks
- If no relevant document found, respond with `get_answer_not_found(language)` from `prompts.py`
- Required source metadata: `title`, `source_path`, `chunk_index`, `ingest_timestamp`
- SSE `done` event includes `full_text` (complete retrieved chunk) for source preview

## SQL Safety Rules
- Read-only queries only — SELECT statements exclusively
- Block: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, multi-statement (`;` separator)
- Default row limit: 500; hard cap: 1000
- Log every executed query with timestamp, latency, row count
- Never claim answer is from structured data if query failed or returned empty results
- Mark all generated SQL as system-generated in the UI trace
- **Number formatting**: `executor.py` pre-formats all numeric columns before `to_markdown()` — integers with `,` thousands separator, floats as `f"{v:,.2f}"` — prevents scientific notation like `2.368e+10`

## Retrieval Architecture
- **Embeddings model**: `intfloat/multilingual-e5-large` (560M params, 1024-dim) — supports ID + EN
- **Hybrid retrieval**: BM25 (`rank-bm25`) + FAISS cosine similarity fused via Reciprocal Rank Fusion (RRF)
- **Domain filtering**: each chunk tagged with domain at ingest time; retriever filters by `domain` param
- **Gabungan two-pass**: original question retrieves policy chunks; extracted data question retrieves metric chunks; deduplicated by `(source_path, chunk_index)`

## Router Architecture (4-tier heuristics)
1. **Tier 1 — Show verbs**: `tampilkan|tunjukkan|show|list|display` → always `data`
2. **Tier 2 — Gabungan patterns**: comparison + policy reference patterns (ID + EN, plural-aware)
3. **Tier 3 — Data keywords**: aggregation/listing + no policy words → `data`
4. **Tier 4 — Policy keywords**: policy/regulation + no data keywords → `dokumen`
5. **LLM fallback**: only for genuinely ambiguous questions; defaults to `dokumen` on error
- All logger strings use `->` (not `→`) to avoid Windows cp1252 crashes

## Sample Data (9 tables, 148+ rows)
| Domain | Tables | Details |
|--------|--------|---------|
| Banking | `kredit_umkm` (45), `nasabah` (15), `cabang` (14) | 4-month time series, NPL quality tiers, regional credit targets |
| Telco | `pelanggan` (20), `penggunaan_data` (30), `jaringan` (15) | Churn risk score, ARPU, utilisasi per region (Bali 90.1% kritis) |
| Government | `penduduk` (15), `anggaran_daerah` (26), `layanan_publik` (23) | TW1–TW3 budget absorption, IKM per service type, processing days |

## Documents (10 files, 90 chunks)
| Domain | File | Key content |
|--------|------|-------------|
| Banking | `kebijakan_kredit_umkm.txt` | 15% YoY targets, NPL thresholds, restructuring conditions |
| Banking | `prosedur_kyc_nasabah.txt` | Risk tiers (SDD/CDD/EDD), PPATK thresholds |
| Banking | `regulasi_ojk_2025.txt` | POJK references, CAR/LCR ratios, KUR 2026 allocation |
| Telco | `kebijakan_layanan_pelanggan.txt` | SLA tiers (P1–P4), churn risk tiers, retention eligibility (score ≥70) |
| Telco | `regulasi_spektrum_frekuensi.txt` | Spectrum allocation, utilisation thresholds (70/85/95%) |
| Government | `kebijakan_pelayanan_publik.txt` | Processing times (KTP 3d, IMB 14d), IKM target 82.0 |
| Government | `regulasi_anggaran_daerah.txt` | APBD structure, TW3 target 70%, penalty for <75% end-year |

## Frontend Architecture (index.html)
The React SPA uses **htm tagged templates** — no build step, no JSX, no bundler.

Key patterns:
- `useReducer(reduce, [], initializer)` — initializer reads `sessionStorage` for persistence
- ASSISTANT messages store `question` field for DocCard keyword highlighting
- `handleSubmit(question, _onDone)` — `_onDone` callback enables auto-play chaining
- Auto-play uses three refs (`autoPlayRef`, `samplesRef`, `handleSubmitRef`) to avoid stale closures
- `highlightHtml(text, query)` — HTML-escapes then wraps matched words in `<mark>` tags (safe)
- Session chat persisted to `sessionStorage` key `cld-chat`; cleared on RESET dispatch
- Domain tabs and language toggle are in the **sidebar** (not topbar)
- SSE token events use `{"text": "..."}` key (not `"token"`)

## Language Policy
| Content | Language |
|---------|----------|
| Code, docstrings, comments | English |
| Documentation (README, CLAUDE.md, deployment guides) | English |
| LLM system prompts | Bahasa Indonesia (with `{lang_rule}` placeholder) |
| LLM user prompts | Bahasa Indonesia (internal framing only) |
| UI labels, buttons, error messages | Bahasa Indonesia |
| LLM responses to user | Same language as user's question (ID or EN) |
| Schema names, table names, column names | English (technical labels) |

## History Tracking
After each meaningful work session:
1. Create `.claude/history/sessions/YYYY-MM-DD-HHMM-<topic>.md`
2. Record architecture decisions in `.claude/history/decisions/YYYY-MM-DD-<decision>.md`
3. Update `.claude/history/changelogs/YYYY-MM-DD.md` with notable changes
4. Store reusable prompts in `.claude/history/prompts/`
