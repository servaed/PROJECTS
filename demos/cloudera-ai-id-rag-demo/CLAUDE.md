# CLAUDE.md — cloudera-ai-id-rag-demo

## Project Purpose
Demo repository for Indonesian enterprise customers showing a **bilingual conversational
assistant** (Bahasa Indonesia + English) deployed as a Cloudera AI Application. The assistant
answers from enterprise documents (RAG) and structured tables (SQL), with full source traceability
for presales demos in banking, telco, and government sectors.

## System Architecture
```
User (Bahasa Indonesia or English)
  → React SPA (port 8080) — sidebar domain tabs + language toggle + mode toggles
  → FastAPI Backend (app/api.py)
       ├─ GET  /              → index.html (React SPA chat interface)
       ├─ GET  /setup         → setup.html (health dashboard)
       ├─ GET  /configure     → configure.html (env var wizard)
       ├─ POST /api/chat      → SSE streaming (mode → thinking_token → token… → done)
       ├─ POST /api/agent/chat    → Agent SSE (plan → step → synthesis → done)
       ├─ POST /api/debate/chat   → Debate SSE (researcher → critic → synthesis → done)
       ├─ GET  /api/status    → live component status (sidebar indicators)
       ├─ GET  /api/samples   → sample prompts list (domain + lang filtered)
       ├─ GET  /api/domains   → available domain list
       ├─ GET  /api/setup     → detailed health report (used by /setup page)
       ├─ GET  /api/configure → current config state, secrets masked
       ├─ POST /api/configure → validate → write data/.env.local → os.environ update
       ├─ POST /api/test/llm     → send 1-token ping to LLM, return provider/model/latency
       ├─ GET  /api/logs         → last N lines from _MemoryHandler ring buffer
       ├─ POST /api/ingest       → rebuild FAISS vector store in background
       ├─ GET  /api/ingest/status → poll ingest job
       ├─ POST /api/docs/upload  → upload document; PDFs get table extraction via pdfplumber
       └─ GET  /health           → {status, checks:{vector_store,database,llm_configured}, uptime_s}
  → Orchestration Router (classify → dokumen / data / gabungan)
       ├─ Keyword heuristics (4-tier: show-verb → gabungan → data → dokumen)
       └─ LLM fallback for ambiguous questions
  → Document RAG  (loaders → chunking → BM25 + FAISS hybrid → RRF → retriever)
       └─ docs from MinIO/Ozone S3 bucket (DOCS_STORAGE_TYPE=s3) or local filesystem
  → SQL Retrieval (schema discovery → guarded SQL gen → executor → number formatting)
       └─ DuckDB/Parquet (QUERY_ENGINE=duckdb, local dev) or Trino+Iceberg on Ozone (QUERY_ENGINE=trino, CDP CDW)
  → LLM Provider (pluggable: Cloudera AI Inference / OpenAI-compatible / Bedrock / Anthropic / local)
  → Answer Builder (prepare_answer → stream_synthesis → finalize_answer)
       └─ Bilingual synthesis + citations + query trace

Demo deployment (DuckDB + local filesystem):
  uvicorn on $CDSW_APP_PORT — FastAPI + React SPA (the CML Application endpoint)

Production CDP equivalent (swap connectors via env vars):
  Trino  (CDW)  — set QUERY_ENGINE=trino, TRINO_HOST=<cdw-endpoint>
  Ozone  (S3GW) — set DOCS_STORAGE_TYPE=s3, MINIO_ENDPOINT=http://ozone-s3gw:9878
```

**Backend: FastAPI + uvicorn.** Serves the React SPA from `app/static/` and streams
LLM tokens via Server-Sent Events on `POST /api/chat`.

**Entry points:**
- CML Application: `run_app.py` (Python launcher) → `deployment/launch_app.sh` → uvicorn
- Local dev: `make dev` or `uvicorn app.api:app --host 0.0.0.0 --port 8080 --reload`
- Streamlit fallback (`app/main.py`) retained for notebook/dev use only

## Key Directories
| Path | Purpose |
|------|---------|
| `app/api.py` | **FastAPI entry point (production)** — all routes |
| `app/main.py` | Streamlit entry point (local/notebook fallback) |
| `app/static/index.html` | React SPA — chat interface (htm tagged templates, no build step) |
| `app/static/setup.html` | Health dashboard — auto-refreshes every 30 s; QR popup; startup banner; log viewer |
| `app/static/configure.html` | Env-var wizard — saves to `data/.env.local`; Test LLM; .env download; model datalists |
| `app/static/vendor/` | Self-hosted JS: React, htm, DOMPurify, QRCode.js, **Leaflet 1.9.4** (map) |
| `Makefile` | Dev shortcuts: `make dev`, `make seed`, `make test`, `make reset-vs` |
| `src/config/` | Settings (pydantic-settings), logging config |
| `src/llm/` | LLM abstraction base (`chat` + `stream_chat`), OpenAI-compatible client, bilingual prompts |
| `src/retrieval/` | Document loaders, chunking, embeddings (e5-large), FAISS + BM25 hybrid retriever |
| `src/retrieval/table_extractor.py` | **PDF table extraction** via pdfplumber → DuckDB views |
| `src/sql/` | Schema metadata, SQL guardrails (sqlparse AST), query generator, executor |
| `src/orchestration/` | Router (4-tier heuristic + LLM), answer builder (prepare/stream/finalize), citations |
| `src/connectors/` | Storage adapters: Trino (CDW), Ozone/S3, DuckDB, local files |
| `src/utils/` | Language helpers, unique ID generation |
| `data/sample_docs/` | Domain-segregated TXT documents (banking/, telco/, government/) |
| `data/sample_tables/` | Parquet seeder (`seed_parquet.py`) + shared generator (`sample_data.py`) — 11 tables, 2,286 rows |
| `data/vector_store/` | FAISS index + SHA-256 integrity hash (gitignored) |
| `deployment/` | `launch_app.sh` (step 0–5 startup), env var reference, deployment guide |
| `tests/` | Pytest unit tests (86 total across 4 suites) |
| `run_app.py` | Python launcher for CML Application Script field → calls `launch_app.sh` |
| `.claude/skills/` | Reusable Claude Code project skills |
| `.claude/history/` | Session logs, decisions, changelogs, prompts |

## Development Commands
```bash
# One-command local dev (pip install + seed + uvicorn)
make dev

# Or step by step:
pip install -r requirements.txt
python data/sample_tables/seed_parquet.py
python -m src.retrieval.document_loader
uvicorn app.api:app --host 0.0.0.0 --port 8080 --reload

# Run all tests
pytest tests/ -v
make test

# Force re-ingestion (after adding new documents)
make reset-vs
```

## Chat Modes (Input Bar Toggles)
Three mutually-aware toggles in the bottom-right of the input bar:

| Toggle | Endpoint | SSE events | UI component |
|--------|----------|------------|--------------|
| **Think** | `/api/chat` with `thinking:true` | `thinking_token` | `ThinkingPanel` — collapsible CoT panel |
| **Agent** | `/api/agent/chat` | `agent_plan`, `agent_step_*`, `agent_synthesis` | `AgentResearch` — step trace |
| **Debate** | `/api/debate/chat` | `debate_researcher_done`, `debate_critic_token`, `debate_synthesis_start` | `DebatePanel` — Researcher + Critic cards |

Think can be combined with any mode. Agent and Debate are mutually exclusive.

### Reasoning Mode (Think)
- `_ThinkingFilter.feed()` returns `(visible_text, thinking_text)` tuple — thinking content captured separately
- Backend emits `thinking_token` SSE events when `ChatRequest.thinking=True`
- Works with any model emitting `<think>` tags (DeepSeek-R1, Nemotron, QwQ) or Anthropic extended thinking
- `ThinkingPanel` auto-opens while model is thinking, shows word count when done

### Agent Mode (Plan → Execute → Synthesize)
- `_AGENT_PLAN_SYSTEM` instructs planner to output **natural language queries** (not SQL) in `query` field
- Executor runs `retrieve()` for docs steps, `_generate_sql_with_retry()` for data steps
- `AGENT_SYNTH_SYSTEM` prompt in `_debate_sse` / `_agent_sse` synthesizes all step results
- Agent messages: `mode:'agent'`, `isAgent:true`, `agentPhase:'planning'|'executing'|'synthesizing'|'done'`

### Debate Mode (Researcher → Critic → Synthesis)
- **Researcher**: retrieves docs + SQL, produces factual briefing (non-streaming LLM call)
- **Critic**: receives Researcher's briefing, streams challenges and alternative interpretations
- **Synthesis**: final LLM call incorporating both perspectives, streamed as regular `token` events
- Debate messages: `mode:'debate'`, `isDebate:true`, `debatePhase:'researching'|'critic'|'synthesis'`

## Map Visualization
- **Leaflet 1.9.4** served locally from `/static/vendor/leaflet.js` (works offline, no CDN)
- `MapChart` component auto-activates when SQL result has `city`, `region`, `province`, `kota`, or `provinsi` column
- Row limit: ≤12 rows for bar chart; ≤50 rows for map (geo queries typically return 27 cities)
- `_CITY_COORDS` in `index.html` covers all 27 cities + 24 Indonesian province centers
- Bubble markers: radius 9–38px, color teal→orange→red encoding metric value
- CartoDB Dark Matter / Positron tiles match dark/light theme
- Legend shows Low→High gradient in bottom-right corner

## Document Intelligence (PDF Table Extraction)
- `src/retrieval/table_extractor.py` uses `pdfplumber` (graceful no-op when not installed)
- On PDF upload via `POST /api/docs/upload`: tables extracted and registered as DuckDB views with `doc_` prefix
- View naming: `doc_{stem}_{page}_{table}` (e.g. `doc_annual_report_p1_t1`)
- Upload response includes `extracted_tables: ["doc_report_p1_t1", ...]`
- Extracted tables immediately queryable in chat

## Deployment Assumptions (Cloudera AI Applications)
- **Script field runs Python only** — CML executes the Script as a Python file, not bash.
  Use `run_app.py` as the Script; it calls `deployment/launch_app.sh` via subprocess.
- **Port**: bind to `CDSW_APP_PORT` (CML injects this, defaults to 8080).
- All configuration via environment variables set in the Applications UI **or** via `/configure` wizard.
- **Application-level env vars override project-level env vars**.
- `deployment/launch_app.sh` sources `data/.env.local` at step 0 before uvicorn starts.
- **Minimum resource profile**: 4 vCPU / 8 GiB RAM (for `multilingual-e5-large` local embeddings).

## Bilingual Support
The app responds in the same language the user asks in:
- `ChatRequest.language` (`"id"` or `"en"`) is sent from the frontend
- Threaded through `_chat_sse` → `prepare_answer` → `AnswerPrep.language`
- System prompts use `{lang_rule}` placeholder → `_lang_rule(language)` in `prompts.py`
- Fallback strings localised via `get_answer_not_found(lang)` / `get_answer_sql_failed(lang)`

## Domain Selector (UI Sidebar)
- Four tabs: Banking (◈) · Telco (⬡) · Gov (⬢) · All (◉)
- `domain="all"` → `retrieval_domain=None` (skips domain filter); all 11 tables visible to SQL generator
- Cross-domain questions (economic stress index, infrastructure gap) use "All" domain

## Coding Standards
- Python 3.10+, absolute imports only
- **All code, comments, and documentation in English**
- **LLM-facing system prompts in Bahasa Indonesia** (with `{lang_rule}` placeholder)
- No hardcoded credentials, endpoints, or model names — use `src/config/settings.py`
- **Logger format strings must use ASCII only** — `→` and `≥` crash Windows cp1252 console; use `->` and `>=`

## Security Notes
- SQL guardrails use **sqlparse AST walking** — handles subqueries, CTEs, aliases
- FAISS vector store: SHA-256 integrity hash verified before load
- XSS: all LLM markdown sanitised with DOMPurify before `dangerouslySetInnerHTML`
- `POST /api/configure` validates keys against allowlist

## RAG Safety Rules
- Never fabricate citations, page numbers, or source metadata
- If no relevant document found, respond with `get_answer_not_found(language)`
- SSE `done` event includes `full_text` for source preview

## SQL Safety Rules
- Read-only queries only — SELECT exclusively
- Block: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, multi-statement
- Default row limit: 500; hard cap: 1000
- **Number formatting**: `executor.py` pre-formats numeric columns before `to_markdown()` — integers with `,` separator, floats as `f"{v:,.2f}"`

## Sample Data (11 tables, 2,286 rows)

Data generated by `data/sample_tables/sample_data.py` (fixed `random.Random(42)` seed).

**NPL tiers** baked into data:
- **Low** (Java metro + Bali): 3–6% NPL — Jakarta, Surabaya, Bandung, Denpasar, etc.
- **Mid** (Sumatra + Kalimantan): 7–12% NPL — Medan, Palembang, Balikpapan, etc.
- **High** (Outer islands): 13–22% NPL — Jayapura, Kupang, Kendari, Ambon, etc.

| Domain | Tables | Details |
|--------|--------|---------|
| Banking | `msme_credit` (972) | 27 cities × 3 segments × 12 months, province column, NPL-tiered pools |
| Banking | `customer` (80) | industry, annual_revenue, debt_service_ratio, internal_rating |
| Banking | `branch` (25) | npl_amount, deposit_balance, roi_pct, lat/lon |
| Banking | `loan_application` (600) | 25 branches × 3 types × 8 months; approval_rate_pct, avg_processing_days |
| Telco | `subscriber` (80) | tenure_months, monthly_complaints (correlated with churn_risk_score) |
| Telco | `data_usage` (480) | 80 subscribers × 6 months |
| Telco | `network` (27) | avg_latency_ms, packet_loss_pct (correlated with utilization/status), lat/lon |
| Telco | `network_incident` (162) | 27 cities × 6 months; sla_breach_count, mttr_hrs |
| Government | `resident` (40) | district/city/province population |
| Government | `regional_budget` (88) | 11 programs × 4 quarters × 2 years |
| Government | `public_service` (132) | pending_count, complaint_count added; 11 services × 12 months |

## DOMAIN_CONFIG (approved SQL tables per domain)
```python
"banking":    ["msme_credit", "customer", "branch", "loan_application"]
"telco":      ["subscriber", "data_usage", "network", "network_incident"]
"government": ["resident", "regional_budget", "public_service"]
"all":        all 11 tables
```

## Frontend Architecture (index.html)
The React SPA uses **htm tagged templates** — no build step, no JSX, no bundler.

Key components:
- `ThinkingPanel` — collapsible chain-of-thought panel; auto-opens during thinking, shows word count
- `DebatePanel` — Researcher card (teal) + Critic card (orange) + Synthesis indicator (indigo)
- `AgentResearch` — collapsible step trace with type badge, query, result summary, latency
- `MapChart` — Leaflet bubble map; auto-detected from geo column; city+province coordinate lookup
- `DataChart` — Canvas bar chart (≤12 rows) or Leaflet map (≤50 rows with geo column); Map/Bar/Table switcher
- `PipelineTrace` — Router→Retrieval→Synthesis stage timing for regular chat
- `DocCitationList` — source cards with relevance bar and full-chunk preview
- `SqlPanel` — generated SQL + results table + DataChart (collapsed by default)

Key patterns:
- `useReducer(reduce, [], initializer)` — initializer reads `localStorage` (`_SS_VER=3`)
- Stale closure prevention: `agentModeRef`, `thinkModeRef`, `debateModeRef`, `answerStyleRef`, `domainRef` — all synced via `useEffect`
- `handleSubmit` routes to `/api/chat`, `/api/agent/chat`, or `/api/debate/chat` based on active toggle
- Chat body includes `thinking: thinkModeRef.current` for reasoning mode
- **Nav links** (topbar): plain text only — Chat / Data Explorer / Upload / Metrics / Slides / Status / Settings
- **Domain icons**: ◈ Banking · ⬡ Telco · ⬢ Gov · ◉ All

## Personas
| Persona | Company | Domain | Lang |
|---------|---------|--------|------|
| Rina | Credit Officer · **Bank Indonesia** | banking | id |
| David | Network Ops · **Indosat** | telco | en |
| Budi | Budget Controller · DKI Jakarta | government | id |

## SSE Event Reference
| Event | Source | Payload |
|-------|--------|---------|
| `mode` | `/api/chat` | `{mode: "dokumen"|"data"|"gabungan"}` |
| `token` | all | `{text: "..."}` |
| `thinking` | `/api/chat` | `{active: bool}` |
| `thinking_token` | `/api/chat` (think=true) | `{text: "..."}` |
| `done` | all | `{doc_citations, sql_citation, usage, latency_ms}` |
| `agent_plan` | `/api/agent/chat` | `{steps: [{type,query,label}]}` |
| `agent_step_start` | `/api/agent/chat` | `{index, type, query, label}` |
| `agent_step_done` | `/api/agent/chat` | `{index, summary, latency_ms}` |
| `agent_synthesis` | `/api/agent/chat` | `{}` |
| `debate_researcher_done` | `/api/debate/chat` | `{text: "..."}` |
| `debate_critic_start` | `/api/debate/chat` | `{}` |
| `debate_critic_token` | `/api/debate/chat` | `{text: "..."}` |
| `debate_synthesis_start` | `/api/debate/chat` | `{}` |
| `error` | all | `{message: "..."}` |

## Icon Design System (all pages)
All HTML pages use stroke-SVG icons (Feather style, 1.5px stroke, 24×24 viewBox). Zero emoji in UI chrome.

Cloudera logo: orange in light mode (`--logo-filter` CSS filter); white in dark mode.

## Pages (FastAPI routes)
- `GET /` → `index.html` — React SPA chat
- `GET /setup` → `setup.html` — health dashboard
- `GET /configure` → `configure.html` — env-var wizard
- `GET /explorer` → `explorer.html` — SQL editor + Docs browser + LLM Compare + Iceberg Time Travel
- `GET /upload` → `upload.html` — bulk upload, URL scrape, CSV table import, doc management
- `GET /metrics` → `metrics.html` — inference dashboard
- `GET /presentation` → `presentation.html` — presales slide deck (14 slides, audience toggle)

## /health vs /api/status
- `/health` → `{status, checks:{vector_store, database, llm_configured}, uptime_s}` — used by setup overlay
- `/api/status` → `{vector_store:{ok,...}, database:{ok,...}, llm:{ok,...}}` — used by sidebar indicators

## Language Policy
| Content | Language |
|---------|----------|
| Code, docstrings, comments | English |
| LLM system prompts | Bahasa Indonesia (with `{lang_rule}` placeholder) |
| UI labels, buttons, error messages | English |
| LLM responses to user | Same as user's question (ID or EN) |
| Schema / table / column names | English |
| OJK credit quality codes | Indonesian (Lancar, DPK, Kurang Lancar, Macet) |
| Government agency names | Indonesian (official names) |

## History Tracking
After each meaningful work session:
1. Create `.claude/history/sessions/YYYY-MM-DD-HHMM-<topic>.md`
2. Record architecture decisions in `.claude/history/decisions/`
3. Update `.claude/history/changelogs/YYYY-MM-DD.md`
