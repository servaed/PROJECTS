# CLAUDE.md — cloudera-ai-id-rag-demo

## Project Purpose
Demo repository for Indonesian enterprise customers showing a **Bahasa Indonesia conversational assistant** deployed as a Cloudera AI Application. The assistant answers from enterprise documents (RAG) and structured tables (SQL), with full traceability for presales demos in banking, telco, and government sectors.

## System Architecture
```
User (Bahasa Indonesia)
  → React SPA (port 8080)
  → FastAPI Backend (app/api.py)
       ├─ POST /api/chat  — SSE streaming (mode → token… → done)
       ├─ GET  /api/status — live system status
       └─ GET  /api/samples — sample prompts
  → Orchestration Router (two-phase pipeline)
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
| `app/api.py` | **FastAPI entry point (production)** — SSE chat, status, samples |
| `app/main.py` | Streamlit entry point (local/notebook fallback) |
| `app/ui.py` | Streamlit UI components with Cloudera brand theme |
| `app/static/` | React SPA build — `index.html` + JS/CSS/assets |
| `src/config/` | Settings (pydantic-settings), logging config |
| `src/llm/` | LLM abstraction base (`chat` + `stream_chat`), Cloudera/OpenAI client, prompts |
| `src/retrieval/` | Document loaders, chunking, embeddings, vector store, retriever |
| `src/sql/` | Schema metadata, SQL guardrails, query generator, executor |
| `src/orchestration/` | Router, two-phase answer builder (`prepare/stream/finalize`), citations |
| `src/connectors/` | Storage adapters: HDFS, local files, database |
| `src/utils/` | Language helpers, unique ID generation |
| `data/` | Sample docs (TXT — kebijakan kredit, OJK, KYC), table CSVs, manifests |
| `deployment/` | `launch_app.sh` (uvicorn), env var reference, deployment guide |
| `tests/` | Pytest unit and integration tests |
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

# Run Streamlit fallback (local/notebook use only)
streamlit run app/main.py --server.port 8080 --server.address 0.0.0.0

# Run all tests
pytest tests/ -v

# Run specific test suite
pytest tests/test_sql_guardrails.py -v
```

## Deployment Assumptions (Cloudera AI Applications)
- App **must** listen on **port 8080** — required by Cloudera AI Applications runtime
- Deploy via Git repo URL or Docker image in the Cloudera AI Applications UI
- All configuration via environment variables (see `.env.example`)
- Authentication handled by Cloudera AI platform (SSO / LDAP) — app does not implement its own auth
- See `deployment/cloudera_ai_application.md` for the complete deployment guide

## Coding Standards
- Python 3.10+
- Absolute imports only (`from src.retrieval.retriever import ...`)
- **All code, comments, and documentation in English**
- **Only LLM-facing prompts and user-visible UI strings in Bahasa Indonesia**
- No hardcoded credentials, endpoints, or model names — use `src/config/settings.py`
- Module-level docstrings on every file; inline comments only where logic is non-obvious
- Small, testable modules — one responsibility per file
- Type hints on all public function signatures

## RAG Safety Rules
- Never fabricate citations, page numbers, or source metadata
- Always return source document metadata alongside retrieved chunks
- If no relevant document found, respond explicitly (using `ANSWER_NOT_FOUND_ID` from `prompts.py`)
- Required source metadata: `title`, `source_path`, `chunk_index`, `ingest_timestamp`

## SQL Safety Rules
- Read-only queries only — SELECT statements exclusively
- Block: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, multi-statement (`;` separator)
- Default row limit: 500; hard cap: 1000
- Log every executed query with timestamp, latency, row count
- Prefer approved views or semantic layer tables over raw tables
- Never claim answer is from structured data if query failed or returned empty results
- Mark all generated SQL as system-generated in the UI trace

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
