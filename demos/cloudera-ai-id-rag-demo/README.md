# cloudera-ai-id-rag-demo

A **bilingual enterprise conversational assistant** (Bahasa Indonesia + English) deployed
as a Cloudera AI Application.

The assistant answers questions from enterprise documents (RAG) and structured tables (SQL),
with full source traceability and streaming responses. Designed for presales demos in
Indonesian banking, telco, and government sectors.

The demo ships as a **self-contained Docker image** — MinIO (object storage), Nessie (Iceberg
catalog), and Trino (query engine) run inside the same container, making it portable across
developer laptops, CI, and Cloudera AI Workbench (CML) with zero external dependencies.

---

## Capabilities

| Feature | Description |
|---------|-------------|
| Bilingual chat | Questions and answers in Bahasa Indonesia **or** English — auto-detected |
| Domain selector | Sidebar tabs: 🏦 Banking · 📡 Telco · 🏛 Government |
| Document RAG | Answers from PDF, DOCX, TXT, HTML, Markdown with source preview |
| Structured data query | Natural language to SQL — read-only with full guardrails |
| Combined answers | Merges document context + table query results in one response |
| Conversation history | Maintains context across prior turns |
| Streaming responses | Token-by-token streaming via Server-Sent Events |
| Keyword highlighting | Matched query words highlighted in source chunk previews |
| Demo auto-play | "▶ Run Demo" walks through all sample prompts; ⏸ Pause / ▶ Resume / ⏹ Stop |
| Response latency badge | `⚡ X.Xs` displayed on every assistant message |
| Inline bar chart | SQL results with 2–12 rows rendered as a Canvas bar chart |
| Domain-aware welcome | Clickable sample prompts on the welcome screen per selected domain |
| Keyboard shortcuts | Ctrl+Shift+D (demo), Ctrl+K (clear), Ctrl+Shift+R (full reset), Escape (stop) |
| Full demo reset | ↺ Reset Demo button restores domain + language + clears history |
| Chat persistence | Chat history survives page refresh via `localStorage` |
| Configure wizard | Set LLM credentials via browser UI at `/configure`; inline Test LLM |
| Model suggestions | Provider-aware model ID dropdown suggestions in `/configure` |
| .env download | Export current (non-secret) config as a `.env` file from `/configure` |
| Health dashboard | `/setup` shows live status, startup banner, in-app log viewer, QR code, Re-ingest button |
| First-launch overlay | Setup guide shown automatically when LLM is not yet configured |
| Self-contained Docker | MinIO + Nessie + Trino embedded in the image — no Compose needed |
| One-command startup | `make dev` (local) or `docker compose up` for instant bring-up |
| CI/CD pipeline | GitHub Actions pushes to GHCR on every merge to main |

---

## Architecture

```
Browser
  └─ React SPA (port 8080)
       ├─ GET  /              Chat interface
       ├─ GET  /setup         Health dashboard
       └─ GET  /configure     Environment variable wizard

FastAPI backend (app/api.py)
  ├─ POST /api/chat           SSE streaming: mode → token… → done
  ├─ GET  /api/status         Live component status (sidebar indicators)
  ├─ GET  /api/samples        Sample prompts
  ├─ GET  /api/setup          Detailed health report (used by /setup page)
  ├─ GET  /api/configure      Current config state (secrets masked)
  └─ POST /api/configure      Write data/.env.local + update os.environ

Orchestration pipeline
  ├─ Router      classify question → dokumen / data / gabungan
  ├─ RAG         FAISS vector store → retrieved chunks → LLM synthesis
  └─ SQL         schema inspection → guarded SQL gen → executor → LLM synthesis

Data tier (Docker / CML mode — started by deployment/entrypoint.sh)
  ├─ MinIO  :9000   S3-compatible object store — documents + Iceberg warehouse
  ├─ Nessie :19120  Iceberg REST catalog (Project Nessie)
  └─ Trino  :8085   Distributed SQL — Iceberg connector → Nessie → MinIO

Data tier (local dev mode — started by deployment/launch_app.sh)
  ├─ SQLite         demo.db seeded by data/sample_tables/seed_database.py
  └─ Local FS       data/sample_docs/ read directly

LLM Provider (pluggable)
  └─ Cloudera AI Inference / OpenAI-compatible / Bedrock / Anthropic / local
```

**Stack:**
- Backend: **FastAPI + uvicorn** — async, SSE streaming, port 8080
- Frontend: **React 18 SPA** — served from `app/static/`, no build step (htm tagged templates)
- Embeddings: `intfloat/multilingual-e5-large` (local, no API key required) or OpenAI
- Retrieval: **hybrid BM25 + FAISS** (Reciprocal Rank Fusion) for better precision
- Vector store: FAISS (local) — swap to enterprise vector DB for production
- Object storage: **MinIO** (S3-compatible, stands in for Apache Ozone on CDP)
- Table format: **Apache Iceberg** (Parquet files in MinIO warehouse bucket)
- Catalog: **Project Nessie** (Iceberg REST catalog, stands in for Cloudera Unified Metastore)
- Query engine: **Trino 455** with Iceberg connector (stands in for Cloudera Data Warehouse)
- SQL safety: sqlparse AST walking + allowlist + keyword blocklist + FAISS SHA-256 hash

---

## Cloudera CDP Mapping

| Demo component | Cloudera CDP equivalent |
|---|---|
| MinIO (Docker) | **Apache Ozone** — CDP object store |
| Nessie (Docker) | **Cloudera Unified Metastore** / HMS |
| Trino (Docker) | **Cloudera Data Warehouse (CDW)** — Hive/Impala |
| Iceberg tables (Parquet) | **Apache Iceberg** on Ozone (same format) |
| FastAPI + uvicorn | **Cloudera AI Application** |
| FAISS vector store | Enterprise vector DB (Pinecone, Milvus, etc.) |

Swapping the demo's embedded services for real CDP services requires only environment
variable changes — no code changes.

---

## Repository Structure

```
cloudera-ai-id-rag-demo/
├─ CLAUDE.md                     # Project memory and working conventions
├─ README.md
├─ DEPLOYMENT.md                 # Full deployment guide
├─ Dockerfile                    # Multi-stage build: infra binaries + Python app
├─ docker-compose.yml            # One-command local startup (docker compose up)
├─ Makefile                      # Dev shortcuts: make dev / make docker / make test
├─ .github/
│  └─ workflows/
│     └─ docker-build.yml        # GitHub Actions: build & push to GHCR on main/tags
├─ .dockerignore
├─ requirements.txt
├─ .env.example
├─ .gitignore
├─ app/
│  ├─ api.py                     # FastAPI entry point (production)
│  ├─ main.py                    # Streamlit entry point (local/notebook fallback)
│  ├─ ui.py                      # Streamlit UI components
│  └─ static/
│     ├─ index.html              # React SPA — chat interface (htm, no build step)
│     ├─ setup.html              # Health dashboard — QR, logs, startup banner
│     ├─ configure.html          # Env-var wizard — Test LLM, model suggestions, .env download
│     ├─ cloudera-logo.png
│     └─ vendor/                 # Self-hosted JS (React, htm, DOMPurify, QRCode)
├─ src/
│  ├─ config/settings.py         # All configuration via env vars
│  ├─ config/logging.py
│  ├─ llm/base.py                # Abstract LLM interface
│  ├─ llm/inference_client.py    # OpenAI-compatible client + streaming + ping
│  ├─ llm/prompts.py             # System prompts in Bahasa Indonesia
│  ├─ retrieval/                 # Document loading, chunking, embeddings, FAISS
│  ├─ sql/                       # SQL guardrails (AST), generation, execution
│  ├─ orchestration/             # Router, answer builder, citations
│  ├─ connectors/
│  │  ├─ db_adapter.py           # Factory: sqlite (default) or trino
│  │  ├─ trino_adapter.py        # Trino Python client (Iceberg tables)
│  │  ├─ ozone_adapter.py        # boto3 S3 client (MinIO / Ozone S3GW)
│  │  └─ files_adapter.py        # Local filesystem adapter
│  └─ utils/                     # Language helpers, ID generation
├─ data/
│  ├─ sample_docs/
│  │  ├─ banking/                # kebijakan_kredit_umkm, prosedur_kyc, regulasi_ojk_2025
│  │  ├─ telco/                  # kebijakan_layanan_pelanggan, regulasi_spektrum_frekuensi
│  │  └─ government/             # kebijakan_pelayanan_publik, regulasi_anggaran_daerah
│  ├─ sample_tables/             # SQLite seeder + shared generator (sample_data.py) — 9 tables, 1485 rows
│  ├─ manifests/
│  └─ .env.local                 # ← written by /configure wizard (gitignored)
├─ deployment/
│  ├─ entrypoint.sh              # Docker/CML startup: MinIO→Nessie→Trino→seed→uvicorn
│  ├─ launch_app.sh              # Local dev startup: SQLite + local filesystem + uvicorn
│  ├─ seed_iceberg.py            # Creates MinIO buckets + Iceberg schema + uploads docs
│  ├─ trino/
│  │  └─ etc/catalog/
│  │     └─ iceberg.properties   # Trino Iceberg connector config (Nessie + MinIO)
│  ├─ app_config.md              # Environment variable reference
│  └─ cloudera_ai_application.md # Step-by-step Cloudera AI deployment guide
└─ tests/
   ├─ test_sql_guardrails.py     # 25 tests — AST bypass, CTE, multi-JOIN
   ├─ test_router.py             # 12 tests — classification, error fallback
   ├─ test_retrieval.py          # 17 tests — chunking, citations, mocked store
   └─ test_api.py                # 12 tests — FastAPI endpoints, SSE shape
```

---

## Quick Start

### Option A — Docker Compose (easiest, one command)

```bash
# Copy and edit env file (set LLM credentials)
cp .env.example .env
# Edit .env with LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL_ID

# Start everything (builds image on first run, ~5–10 min)
docker compose up
```

Open **http://localhost:8080**. First boot seeds Iceberg tables and ingests documents
(~2–4 min). The `/setup` page shows a pulsing banner while services warm up.

### Option B — Makefile shortcuts

```bash
make dev          # pip install + seed + uvicorn (local SQLite mode)
make docker       # docker build
make docker-run   # docker run with env vars from shell
make test         # pytest tests/ -v
make help         # list all targets
```

### Option C — Docker manually (all services included)

```bash
# Build the image (~5–10 min first time — downloads MinIO, Nessie, Trino)
docker build -t cloudera-ai-id-rag-demo:latest .

# Run (MinIO + Nessie + Trino start automatically inside the container)
docker run --rm -p 8080:8080 \
  -e LLM_PROVIDER=openai \
  -e LLM_BASE_URL=https://... \
  -e LLM_API_KEY=sk-... \
  -e LLM_MODEL_ID=gpt-4o \
  cloudera-ai-id-rag-demo:latest
```

### Option D — Local Development (SQLite + local files, no Docker)

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd cloudera-ai-id-rag-demo

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. One command starts everything
make dev

# OR step by step:
pip install -r requirements.txt
python data/sample_tables/seed_database.py
python -m src.retrieval.document_loader
uvicorn app.api:app --host 0.0.0.0 --port 8080 --reload
```

Open **http://localhost:8080** for the chat interface.
Open **http://localhost:8080/setup** to check component health (QR code, log viewer).
Open **http://localhost:8080/configure** to set credentials — use **⚡ Test LLM** to verify,
then **⬛ Download .env** to save the config template.

---

## Runtime Modes

| Mode | Entry point | Storage | Query engine | When to use |
|------|-------------|---------|--------------|-------------|
| **Docker / CML** | `deployment/entrypoint.sh` | MinIO (S3) | Trino + Iceberg | Production demo, Cloudera AI Workbench |
| **Local dev** | `deployment/launch_app.sh` | Local filesystem | SQLite | Laptop development, quick iteration |

Environment variables that differ between modes:

| Variable | Docker/CML default | Local dev default |
|---|---|---|
| `QUERY_ENGINE` | `trino` | `sqlite` |
| `DOCS_STORAGE_TYPE` | `s3` | `local` |

The Dockerfile sets `QUERY_ENGINE=trino` and `DOCS_STORAGE_TYPE=s3` so the image always
uses the full Cloudera-mirroring stack. Local dev uses SQLite and local filesystem by default.

---

## Configure Wizard (`/configure`)

The configure wizard lets you set environment variables through the browser — no
shell access required. This is especially useful on a fresh Cloudera AI Application
deployment before the LLM credentials have been configured.

**Flow:**
1. Open `http://<app-url>/configure`
2. Select your LLM provider (Cloudera / OpenAI / Azure / Bedrock / Anthropic / Local)
3. Fill in credentials — model ID field shows provider-specific suggestions via `<datalist>`
4. Click **⚡ Test LLM** — sends a test ping and shows provider, model, and latency inline
5. Click **Save Configuration** — values are written to `data/.env.local`
   and applied to the running process immediately
6. Click **⬛ Download .env** to export the current (non-secret) config as a `.env` file
7. Click **Restart** in the Cloudera AI Applications UI for full effect

**Source badges** show where each value comes from:
- 🟢 **From environment** — set via Cloudera AI platform UI, takes precedence, field locked
- 🔵 **From saved file** — stored in `data/.env.local` by this wizard
- ⬜ **Not set** — will use code default

If LLM is not configured on first load, a **setup overlay** appears with step-by-step
instructions linking directly to `/configure`.

---

## Demo Features

### Domain & language selector (sidebar)
- Click **🏦 Banking**, **📡 Telco**, or **🏛 Gov** tabs in the sidebar to switch the
  active domain — sample prompts and retrieval scope update immediately
- Toggle **Bahasa Indonesia / English** to switch the response language — the LLM
  replies in whichever language is selected

### ▶ Run Demo (auto-play)
Click **▶ Run Demo** in the sidebar to walk through all sample prompts automatically,
with a 1.8 s pause between answers.
- **⏸ Pause** — suspends at the current prompt; **▶ Resume** picks up exactly where paused
- **⏹ Stop** — exits auto-play immediately
- **↺ Reset Demo** (sidebar footer) — restores domain, language, and clears all history
- Keyboard: **Ctrl+Shift+D** start/stop · **Escape** stop · **Ctrl+Shift+R** full reset · **Ctrl+K** clear

The input bar is disabled during auto-play to prevent concurrent SSE streams.

### Domain-aware welcome screen
When the conversation is empty, the welcome screen shows the active domain's icon, name,
description, and top 3 clickable sample prompts. Clicking a prompt fires it immediately.

### Response latency & bar charts
- Every assistant response shows a `⚡ X.Xs` latency badge (total round-trip time)
- SQL results with 2–12 rows are rendered as an inline Canvas bar chart below the table

### Source document preview
Expand any source citation card with **▼ Show full chunk** to read the complete
retrieved text chunk, with query keywords highlighted in orange.

### Copy & reset
- **Copy** button on each assistant message — one-click copy of the full answer text
- **+ Sources** button (appears when citations exist) — copies answer + all source titles and SQL
- **Trash** icon in the topbar — clears the conversation and resets auto-play
- Chat history persists across page refreshes via `localStorage`

### Citation relevance scores
Each source document card shows a **relevance badge** (high / med / low) based on the
Reciprocal Rank Fusion score from the hybrid BM25 + FAISS retrieval — a quick visual
indicator of how strongly each chunk matched the question.

---

## SQL Safety & Guardrails

The assistant only executes **read-only SELECT queries** against an approved table list.
Multiple layers prevent data modification or unauthorized access:

| Layer | What it does |
|-------|-------------|
| Keyword blocklist | Rejects `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `CREATE`, `EXEC`, etc. |
| AST table check | Parses query with `sqlparse` to extract all tables (including subqueries and CTEs), rejects any not in the domain allowlist |
| Multi-statement block | Detects `;`-separated statements — SQL comments stripped first to prevent bypass |
| LIMIT enforcement | Strips any existing `LIMIT ... OFFSET ...` clause and re-applies a hard cap (default 500 rows) |
| SELECT-only gate | Query must start with `SELECT` after comment stripping |
| Rate limiting | `/api/chat` accepts at most 30 requests per minute per IP |

**Supported SQL patterns:**
```sql
SELECT column, COUNT(*), SUM(amount) FROM approved_table WHERE ...
SELECT * FROM approved_table LIMIT 10
SELECT a.col FROM table_a a JOIN table_b b ON a.id = b.id   -- cross-table joins OK
WITH cte AS (SELECT ...) SELECT * FROM cte                   -- CTEs OK
```

**Blocked patterns (raise `SqlGuardrailError` with Bahasa Indonesia message):**
```sql
DROP TABLE kredit_umkm                    -- destructive keyword
SELECT * FROM kredit_umkm; DROP TABLE ... -- multi-statement
SELECT * FROM secret_table                -- not in approved table list
/* DROP TABLE x */ SELECT 1               -- comment-wrapped bypass attempt
SELECT * FROM kredit_umkm LIMIT 10 OFFSET 9999999  -- OFFSET bypass → stripped
```

---

## Running Tests

```bash
pytest tests/ -v
```

| Suite | Coverage |
|-------|---------|
| `test_sql_guardrails.py` | SQL injection, subquery bypass, CTE, table allowlist |
| `test_router.py` | LLM classification modes, aliases, error fallback |
| `test_retrieval.py` | Chunking, citation building, mocked vector store |
| `test_api.py` | FastAPI endpoints, SSE stream shape, LLM provider indicators |

---

## Deploying to Cloudera AI Applications

See the full guide in [`DEPLOYMENT.md`](DEPLOYMENT.md).

**Deploying to Cloudera AI Workbench (CML Applications):**
1. Clone or sync this repo into a CML project via Git (HTTPS recommended)
2. **Applications → New Application**

   | Field | Value |
   |---|---|
   | Script | `demos/cloudera-ai-id-rag-demo/run_app.py` |
   | Editor | Workbench |
   | Kernel | Python 3.10 |
   | Edition | Standard |
   | vCPU / Memory | 4 vCPU / 8 GiB |

3. Add env vars: `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL_ID`
   — or configure after deploy via **http://\<app-url\>/configure**
4. Click **Create Application** → wait ~3–5 min for first boot
5. Verify at `/setup` — all status cards green

> **Note:** CML Applications execute the Script field as Python. `run_app.py` is a
> Python launcher that calls `deployment/launch_app.sh` via subprocess.
> Uses SQLite + local filesystem — no Trino/MinIO/Nessie required.

---

## Sample Data

The demo ships with realistic data across 9 tables (**1485 rows**), generated
deterministically from `data/sample_tables/sample_data.py` (fixed seed 42):

| Domain | Tables | Highlights |
|--------|--------|-----------|
| Banking | `kredit_umkm` (540), `nasabah` (80), `cabang` (25) | 15 cities × 3 segments × 12 months, NPL tiers, 25 branches nationwide |
| Telco | `pelanggan` (80), `penggunaan_data` (480), `jaringan` (20) | Churn risk scores, ARPU, 80 customers × 6 months usage, 20 stations |
| Government | `penduduk` (40), `anggaran_daerah` (88), `layanan_publik` (132) | 40 districts, 11 programs × 4 quarters × 2 years, 11 service types × 12 months |

Documents per domain:

| Domain | Files |
|--------|-------|
| Banking | `kebijakan_kredit_umkm.txt` · `prosedur_kyc_nasabah.txt` · `regulasi_ojk_2025.txt` |
| Telco | `kebijakan_layanan_pelanggan.txt` · `regulasi_spektrum_frekuensi.txt` |
| Government | `kebijakan_pelayanan_publik.txt` · `regulasi_anggaran_daerah.txt` |

---

## Presales Demo Script

1. **Open the app** — if LLM is not configured a setup overlay appears with instructions
2. Select a domain (🏦 Banking, 📡 Telco, or 🏛 Gov) and language (ID / EN) from the sidebar
3. **Welcome screen** shows the domain's top 3 sample prompts — click any to fire immediately
4. Click **▶ Run Demo** for a fully automatic walkthrough — no typing required
   - Use **⏸ Pause / ▶ Resume** to pause between prompts for Q&A
   - Use **↺ Reset Demo** to restart from scratch
5. Or ask manually (examples in English mode):
   - *Document*: *"What is the credit restructuring procedure?"* → streaming answer + source panel
   - *Data*: *"Show the top 5 customers by credit exposure"* → answer + SQL trace + bar chart
   - *Combined*: *"Has network utilization in Bali exceeded the SLA threshold?"* → merges both
6. Note the `⚡ X.Xs` latency badge on each response
7. Expand a citation card → **▼ Show full chunk** to show source transparency
8. Open **/setup** to show the live health dashboard, log viewer, and QR code for mobile access
9. Open **/configure** to show how credentials are set without shell access — click **⚡ Test LLM**

---

## License

Internal demo — Cloudera presales use only.
