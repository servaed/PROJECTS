# cloudera-ai-id-rag-demo

A **Bahasa Indonesia enterprise conversational assistant** deployed as a Cloudera AI Application.

The assistant answers questions from enterprise documents (RAG) and structured tables (SQL),
with full source traceability and streaming responses. Designed for presales demos in
Indonesian banking, telco, and government sectors.

---

## Capabilities

| Feature | Description |
|---------|-------------|
| Bahasa Indonesia chat | Questions and answers in Bahasa Indonesia |
| Document RAG | Answers from PDF, DOCX, TXT, HTML, Markdown with source preview |
| Structured data query | Natural language to SQL — read-only with full guardrails |
| Combined answers | Merges document context + table query results in one response |
| Conversation history | Maintains context across prior turns |
| Streaming responses | Token-by-token streaming via Server-Sent Events |
| Keyword highlighting | Matched query words highlighted in source chunk previews |
| Demo auto-play | "▶ Run Demo" walks through all sample prompts unattended |
| Session persistence | Chat history survives page refresh via `sessionStorage` |
| Configure wizard | Set LLM credentials via browser UI at `/configure` |
| Health dashboard | `/setup` shows live status of all components with fix hints |
| Docker deployment | `Dockerfile` provided for container-based deployment path |

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

LLM Provider (pluggable)
  └─ Cloudera AI Inference / OpenAI-compatible / Bedrock / Anthropic / local
```

**Stack:**
- Backend: **FastAPI + uvicorn** — async, SSE streaming, port 8080
- Frontend: **React 18 SPA** — served from `app/static/`, no build step (htm tagged templates)
- Embeddings: local `sentence-transformers` (default, no API key) or OpenAI
- Vector store: FAISS (local) — swap to enterprise vector DB for production
- SQL safety: sqlparse AST walking + allowlist + keyword blocklist + FAISS SHA-256 hash
- Streamlit fallback: `app/main.py` retained for local notebook use only

---

## Repository Structure

```
cloudera-ai-id-rag-demo/
├─ CLAUDE.md                     # Project memory and working conventions
├─ README.md
├─ DEPLOYMENT.md                 # Full deployment guide
├─ Dockerfile                    # Container image for Docker-based deployment
├─ .dockerignore
├─ requirements.txt
├─ .env.example
├─ .gitignore
├─ app/
│  ├─ api.py                     # FastAPI entry point (production)
│  ├─ main.py                    # Streamlit entry point (local/notebook fallback)
│  ├─ ui.py                      # Streamlit UI components
│  └─ static/
│     ├─ index.html              # React SPA — chat interface
│     ├─ setup.html              # Health dashboard
│     ├─ configure.html          # Environment variable wizard
│     └─ cloudera-logo.png
├─ src/
│  ├─ config/settings.py         # All configuration via env vars
│  ├─ config/logging.py
│  ├─ llm/base.py                # Abstract LLM interface
│  ├─ llm/inference_client.py    # OpenAI-compatible client + streaming + ping
│  ├─ llm/prompts.py             # System prompts in Bahasa Indonesia
│  ├─ retrieval/                 # Document loading, chunking, embeddings, FAISS
│  ├─ sql/                       # SQL guardrails (AST), generation, execution
│  ├─ orchestration/             # Router, answer builder, citations
│  ├─ connectors/                # HDFS, file, database adapters
│  └─ utils/                     # Language helpers, ID generation
├─ data/
│  ├─ sample_docs/               # Demo documents (kebijakan kredit, OJK, KYC)
│  ├─ sample_tables/             # Demo table data (CSV + SQLite seeder)
│  ├─ manifests/
│  └─ .env.local                 # ← written by /configure wizard (gitignored)
├─ deployment/
│  ├─ launch_app.sh              # Startup script (sources data/.env.local, then uvicorn)
│  ├─ app_config.md              # Environment variable reference
│  └─ cloudera_ai_application.md # Step-by-step Cloudera AI deployment guide
└─ tests/
   ├─ test_sql_guardrails.py     # 25 tests — AST bypass, CTE, multi-JOIN
   ├─ test_router.py             # 12 tests — classification, error fallback
   ├─ test_retrieval.py          # 17 tests — chunking, citations, mocked store
   └─ test_api.py                # 12 tests — FastAPI endpoints, SSE shape
```

---

## Quick Start (Local Development)

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd cloudera-ai-id-rag-demo

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4a. Configure via browser wizard (recommended)
uvicorn app.api:app --host 0.0.0.0 --port 8080
# Open http://localhost:8080/configure → fill in LLM credentials → Save

# 4b. OR configure via .env file
cp .env.example .env
# Edit .env with your LLM endpoint and API key

# 5. Seed the demo SQLite database
python data/sample_tables/seed_database.py

# 6. Ingest sample documents into the vector store
python -m src.retrieval.document_loader

# 7. Run the application (or restart if already running from step 4a)
uvicorn app.api:app --host 0.0.0.0 --port 8080 --reload
```

Open **http://localhost:8080** for the chat interface.
Open **http://localhost:8080/setup** to check component health.
Open **http://localhost:8080/configure** to set or update environment variables.

**Streamlit fallback** (local development only):
```bash
streamlit run app/main.py --server.port 8080
```

---

## Configure Wizard (`/configure`)

The configure wizard lets you set environment variables through the browser — no
shell access required. This is especially useful on a fresh Cloudera AI Application
deployment before the LLM credentials have been configured.

**Flow:**
1. Open `http://<app-url>/configure`
2. Select your LLM provider (Cloudera / OpenAI / Bedrock / Anthropic / Local)
3. Fill in credentials — fields show which are already set and from where
4. Click **Save Configuration** — values are written to `data/.env.local`
   and applied to the running process immediately
5. Click **Restart** in the Cloudera AI Applications UI for full effect

**Source badges** show where each value comes from:
- 🟢 **From environment** — set via Cloudera AI platform UI, takes precedence, field locked
- 🔵 **From saved file** — stored in `data/.env.local` by this wizard
- ⬜ **Not set** — will use code default

---

## Demo Features

### ▶ Run Demo (auto-play)
Click **▶ Run Demo** in the sidebar to walk through all six sample prompts
automatically, with a 1.8 s pause between answers. Click **⏹ Stop Demo** at
any time. The input bar is disabled during auto-play to prevent concurrent
SSE streams.

### Source document preview
Expand any source citation card with **▼ Show full chunk** to read the complete
retrieved text chunk, with query keywords highlighted in orange.

### Copy & reset
- **Copy** button on each assistant message — one-click copy of the full answer
- **Trash** icon in the topbar — clears the conversation and resets auto-play
- Chat history persists across page refreshes via `sessionStorage`

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

**Quick summary:**
1. Push repo to Git
2. **Applications → New Application** in Cloudera AI
3. Source: Git repo URL + branch; Launch Command: `bash deployment/launch_app.sh`
4. Set `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_ID`
   — or set them after deployment via **http://\<app-url\>/configure**
5. Deploy → wait for **Running** (3–10 min first boot)
6. Verify at `/setup` — all five status cards should be green

**Docker alternative:**
```bash
docker build -t cloudera-ai-id-rag-demo:latest .
docker run --rm -p 8080:8080 \
  -e LLM_PROVIDER=openai \
  -e LLM_BASE_URL=https://... \
  -e LLM_API_KEY=sk-... \
  -e LLM_MODEL_ID=meta/llama-3.1-70b-instruct \
  cloudera-ai-id-rag-demo:latest
```

---

## Presales Demo Script

1. **Open the app** — React chat interface loads with sample prompts in the sidebar
2. Click **▶ Run Demo** for a fully automatic walkthrough — no typing required
3. Or ask manually:
   - *Document*: *"Jelaskan ketentuan restrukturisasi kredit"* → streaming answer + source panel
   - *Data*: *"Berapa outstanding UMKM Jakarta Maret 2026?"* → answer + SQL trace + result table
   - *Combined*: *"Apakah tren sesuai kebijakan ekspansi?"* → merges both sources
4. Expand a citation card → **▼ Show full chunk** to show source transparency
5. Open **/setup** to show the live health dashboard and system status
6. Open **/configure** to show how credentials are set without shell access

---

## License

Internal demo — Cloudera presales use only.
