# CLAUDE.md — cloudera-ai-id-rag-demo

## Project Purpose
Demo repository for Indonesian enterprise customers showing a **Bahasa Indonesia conversational assistant** deployed as a Cloudera AI Application. The assistant answers from enterprise documents (RAG) and structured tables (SQL), with full traceability for presales demos in banking, telco, and government sectors.

## System Architecture
```
User (Bahasa Indonesia)
  → React SPA (port 8080)
  → FastAPI Backend (app/api.py)
       ├─ GET  /              → index.html (React SPA chat interface)
       ├─ GET  /setup         → setup.html (health dashboard)
       ├─ GET  /configure     → configure.html (env var wizard)
       ├─ POST /api/chat      → SSE streaming (mode → token… → done)
       ├─ GET  /api/status    → live component status (sidebar indicators)
       ├─ GET  /api/samples   → sample prompts list
       ├─ GET  /api/setup     → detailed health report (used by /setup page)
       ├─ GET  /api/configure → current config state, secrets masked
       └─ POST /api/configure → validate → write data/.env.local → os.environ update
  → Orchestration Router (classify → dokumen / data / gabungan)
       ├─ Document RAG  (loaders → chunking → embeddings → FAISS → retriever)
       └─ SQL Retrieval (schema discovery → guarded SQL gen → executor)
  → LLM Provider (pluggable: Cloudera AI Inference / OpenAI-compatible / local)
  → Answer Builder (prepare_answer → stream_synthesis → finalize_answer)
       └─ Bahasa Indonesia synthesis + citations + query trace
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
| `src/llm/` | LLM abstraction base (`chat` + `stream_chat`), OpenAI-compatible client, prompts |
| `src/retrieval/` | Document loaders, chunking (LangChain `RecursiveCharacterTextSplitter`), embeddings, FAISS + SHA-256 hash, retriever |
| `src/sql/` | Schema metadata, SQL guardrails (sqlparse AST walking), query generator, executor |
| `src/orchestration/` | Router, two-phase answer builder (`prepare/stream/finalize`), citations |
| `src/connectors/` | Storage adapters: HDFS, local files, database |
| `src/utils/` | Language helpers, unique ID generation |
| `data/` | Sample docs (TXT), table CSVs, manifests, `.env.local` (gitignored) |
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

# Run Streamlit fallback (local/notebook use only)
streamlit run app/main.py --server.port 8080 --server.address 0.0.0.0

# Run all tests
pytest tests/ -v
```

## Deployment Assumptions (Cloudera AI Applications)
- App **must** listen on **port 8080** — required by Cloudera AI Applications runtime
- Deploy via Git repo URL or Docker image in the Cloudera AI Applications UI
- All configuration via environment variables (see `.env.example`) **or** via `GET /configure` wizard
- Authentication handled by Cloudera AI platform (SSO / LDAP) — app does not implement its own auth
- `deployment/launch_app.sh` sources `data/.env.local` at step 0 before uvicorn starts
- Platform env vars always override `data/.env.local` values
- See `DEPLOYMENT.md` and `deployment/cloudera_ai_application.md` for full guides

## Configure Wizard (`/configure`)
- `GET /api/configure` returns current config state: value (masked for secrets) + source (`env` / `file` / `null`)
- `POST /api/configure` body: `{"env_vars": {"LLM_PROVIDER": "openai", ...}}`
  - Allowed keys: `_CONFIGURE_ALLOWED_KEYS` in `api.py`
  - Skips keys already set by platform env (warns in response)
  - Blank value = delete from override file
  - Writes `data/.env.local` and updates `os.environ` immediately
- Override file location: `_OVERRIDE_PATH = Path("data/.env.local")` in `api.py`

## Coding Standards
- Python 3.10+
- Absolute imports only (`from src.retrieval.retriever import ...`)
- **All code, comments, and documentation in English**
- **Only LLM-facing prompts and user-visible UI strings in Bahasa Indonesia**
- No hardcoded credentials, endpoints, or model names — use `src/config/settings.py`
- Module-level docstrings on every file; inline comments only where logic is non-obvious
- Small, testable modules — one responsibility per file
- Type hints on all public function signatures

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
- If no relevant document found, respond explicitly (using `ANSWER_NOT_FOUND_ID` from `prompts.py`)
- Required source metadata: `title`, `source_path`, `chunk_index`, `ingest_timestamp`
- SSE `done` event includes `full_text` (complete retrieved chunk) for source preview

## SQL Safety Rules
- Read-only queries only — SELECT statements exclusively
- Block: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, multi-statement (`;` separator)
- Default row limit: 500; hard cap: 1000
- Log every executed query with timestamp, latency, row count
- Prefer approved views or semantic layer tables over raw tables
- Never claim answer is from structured data if query failed or returned empty results
- Mark all generated SQL as system-generated in the UI trace

## Frontend Architecture (index.html)
The React SPA uses **htm tagged templates** — no build step, no JSX, no bundler.

Key patterns:
- `useReducer(reduce, [], initializer)` — initializer reads `sessionStorage` for persistence
- ASSISTANT messages store `question` field for DocCard keyword highlighting
- `handleSubmit(question, _onDone)` — `_onDone` callback enables auto-play chaining
- Auto-play uses three refs (`autoPlayRef`, `samplesRef`, `handleSubmitRef`) to avoid stale closures
- `highlightHtml(text, query)` — HTML-escapes then wraps matched words in `<mark>` tags (safe)
- Session chat persisted to `sessionStorage` key `cld-chat`; cleared on RESET dispatch

## Language Policy
| Content | Language |
|---------|----------|
| Code, docstrings, comments | English |
| Documentation (README, CLAUDE.md, deployment guides) | English |
| LLM system prompts | Bahasa Indonesia |
| LLM user prompts | Bahasa Indonesia |
| UI labels, buttons, error messages | Bahasa Indonesia |
| Schema names, table names, column names | English (technical labels) |

## History Tracking
After each meaningful work session:
1. Create `.claude/history/sessions/YYYY-MM-DD-HHMM-<topic>.md`
2. Record architecture decisions in `.claude/history/decisions/YYYY-MM-DD-<decision>.md`
3. Update `.claude/history/changelogs/YYYY-MM-DD.md` with notable changes
4. Store reusable prompts in `.claude/history/prompts/`
