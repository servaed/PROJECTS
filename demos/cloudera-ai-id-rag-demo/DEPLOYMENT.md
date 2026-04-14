# Deployment Guide — Cloudera AI Workbench

This guide covers deploying **cloudera-ai-id-rag-demo** as a
[Cloudera AI Application](https://docs.cloudera.com/machine-learning/cloud/applications/topics/ml-applications.html)
on Cloudera AI Workbench (CML).

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Prepare the Repository](#3-prepare-the-repository)
4. [Configure Your LLM Provider](#4-configure-your-llm-provider)
5. [Deploy as a Cloudera AI Application](#5-deploy-as-a-cloudera-ai-application)
6. [Set Environment Variables](#6-set-environment-variables)
7. [Resource Profiles](#7-resource-profiles)
8. [Verify the Deployment](#8-verify-the-deployment)
9. [Update the Application](#9-update-the-application)
10. [Production Checklist](#10-production-checklist)
11. [Troubleshooting](#11-troubleshooting)
12. [Environment Variable Reference](#12-environment-variable-reference)

---

## 1. Architecture Overview

```
Cloudera AI Workbench
│
├── AI Application (this app)
│   ├── FastAPI + uvicorn      port 8080  ← exposed by CML reverse proxy
│   │     ├── React SPA        GET /              chat interface
│   │     ├── Health dashboard GET /setup         component status
│   │     ├── Config wizard    GET /configure     set env vars via browser
│   │     ├── Chat stream      POST /api/chat     Server-Sent Events
│   │     ├── System status    GET /api/status    sidebar indicators
│   │     ├── Sample prompts   GET /api/samples
│   │     ├── Setup detail     GET /api/setup     detailed health report
│   │     ├── Config read      GET /api/configure masked current config
│   │     └── Config write     POST /api/configure write data/.env.local
│   ├── RAG pipeline           FAISS vector store + SHA-256 integrity hash
│   └── SQL pipeline           sqlparse AST guardrails + SQLAlchemy
│
└── AI Inference Service       (optional — set LLM_PROVIDER=cloudera)
    └── Your model endpoint    OpenAI-compatible REST API
```

The app **must listen on port 8080** — Cloudera AI Applications proxies all
traffic through its reverse proxy to that port. Authentication (SSO, LDAP)
is handled by the platform; the app itself has no auth logic.

---

## 2. Prerequisites

| Requirement | Notes |
|---|---|
| Cloudera AI Workbench workspace | Admin or Project Creator role |
| Applications feature enabled | Ask workspace admin if not visible |
| Git repository | GitHub, GitLab, Bitbucket, or internal Git — must be accessible from the workspace network |
| LLM endpoint | Cloudera AI Inference, OpenAI, Azure OpenAI, Bedrock, Anthropic, or local Ollama |
| Python 3.10+ runtime | Default CML runtimes include this |

### Check that Applications are enabled

In your workspace, go to **Site Administration → Applications**.
If the menu item is missing, contact your Cloudera platform admin.

---

## 3. Prepare the Repository

### 3a. Push code to Git

```bash
cd cloudera-ai-id-rag-demo
git add .
git commit -m "deploy: ready for Cloudera AI Application"
git push origin main
```

### 3b. Confirm the repo is accessible from the workspace

If your workspace is on-premises or behind a VPN, test that the Git URL
is reachable from within the CML network. You can do this from a CML
Session terminal:

```bash
git ls-remote https://github.com/your-org/cloudera-ai-id-rag-demo
```

---

## 4. Configure Your LLM Provider

You can set credentials in two ways (use whichever fits your workflow):

**Option A — Cloudera AI platform environment variables** (Section 6):
Set variables in the Applications UI before or after deploying.

**Option B — Browser configure wizard** (after first deploy):
Open `http://<app-url>/configure`, fill in credentials, and click **Save Configuration**.
Values are persisted to `data/.env.local` and survive restarts.

### Cloudera AI Inference (recommended for Cloudera demos)

```
LLM_PROVIDER=cloudera
LLM_BASE_URL=https://your-workspace.cloudera.site/namespaces/serving/endpoints/your-model/v1
LLM_API_KEY=<key from inference endpoint>
LLM_MODEL_ID=meta-llama-3-8b-instruct
```

### OpenAI

```
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL_ID=gpt-4o
```

### Azure OpenAI

```
LLM_PROVIDER=openai
LLM_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/gpt-4o
LLM_API_KEY=<azure key>
LLM_MODEL_ID=gpt-4o
```

### Amazon Bedrock

```
LLM_PROVIDER=bedrock
LLM_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# Use standard AWS credential env vars (not managed by the configure wizard):
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...        # or leave empty for IAM instance role
AWS_SECRET_ACCESS_KEY=...
```

Popular Bedrock model IDs:

| Model | ID |
|---|---|
| Claude 3.5 Sonnet v2 | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| Claude 3 Sonnet | `anthropic.claude-3-sonnet-20240229-v1:0` |
| Llama 3 70B | `meta.llama3-70b-instruct-v1:0` |
| Mistral Large | `mistral.mistral-large-2402-v1:0` |

### Anthropic (direct)

```
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
LLM_MODEL_ID=claude-sonnet-4-6
```

### Local (Ollama / LM Studio)

```
LLM_PROVIDER=local
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_ID=llama3.2
```

---

## 5. Deploy as a Cloudera AI Application

### Step 1 — Open Applications

In your Cloudera AI workspace, click **Applications** in the left sidebar.

> If you don't see **Applications**, your workspace admin needs to enable
> the feature under **Site Administration → Applications**.

---

### Step 2 — Create a New Application

Click **+ New Application** (top right corner).

---

### Step 3 — Fill in Application Settings

| Field | Value | Notes |
|---|---|---|
| **Name** | `Asisten Enterprise ID` | Displayed in the app list |
| **Subdomain** | `asisten-enterprise` | Becomes part of the app URL |
| **Description** | `Bahasa Indonesia RAG + SQL assistant` | Optional |
| **File** | — | Leave empty (using Git) |
| **Git Repository URL** | `https://github.com/your-org/cloudera-ai-id-rag-demo` | Must be reachable from workspace |
| **Branch** | `main` | |
| **Launch Command** | `bash deployment/launch_app.sh` | Handles all startup steps — see below |
| **Runtime** | Python 3.10 (Standard or ML Runtime) | Any CML runtime with Python 3.10+ |
| **Enable Spark** | Off | Not needed |

#### What `launch_app.sh` does on startup

```
[0/5] Load data/.env.local if it exists (written by /configure wizard)
[1/5] pip install -r requirements.txt (skipped if already done)
[2/5] Install provider-specific SDK if needed (boto3 / anthropic)
[3/5] Seed SQLite demo database (idempotent)
[4/5] Ingest documents into FAISS vector store (skipped if index exists)
[5/5] Start uvicorn on port 8080
```

---

### Step 4 — Runtime and Resource Profile

Under **Runtime / Resource Profile**:

| Setting | Recommended |
|---|---|
| **Runtime** | `Python 3.10` |
| **Edition** | Standard or Workbench |
| **vCPU** | 2 (minimum); 4 if loading local embeddings model |
| **Memory** | 4 GB (minimum); 8 GB if loading local embeddings model |
| **GPU** | None (CPU-only for demo) |
| **Replicas** | 1 (for demo); 2+ for HA production |

> **Why 4 vCPU / 8 GB for embeddings?**
> The local `multilingual-e5-base` model is ~500 MB and requires ~2 GB RAM
> to load. The first startup downloads it from HuggingFace (~2 min).
> Set `EMBEDDINGS_PROVIDER=openai` to avoid this cost.

---

### Step 5 — Authentication

| Option | When to use |
|---|---|
| **Unauthenticated** | Internal demos, no sensitive data |
| **Authenticate via SSO** | Production; uses your workspace SSO (LDAP/AD/SAML) |

---

### Step 6 — Set Environment Variables (optional at deploy time)

You can set LLM credentials here **or** use the `/configure` wizard after the app is running.

**Minimum to set before deploying (if using platform env vars):**

```
LLM_PROVIDER=cloudera
LLM_BASE_URL=https://...
LLM_API_KEY=...
LLM_MODEL_ID=meta-llama-3-8b-instruct
```

If you leave these blank, the app will start but the LLM indicator in the sidebar
will be red. Open `/configure` to set credentials via the browser.

---

### Step 7 — Deploy

Click **Deploy Application**.

First startup takes **3–10 minutes** because:
- `pip install -r requirements.txt` runs on first boot
- The HuggingFace embeddings model is downloaded (~500 MB)
- Documents are ingested into the FAISS vector store

Subsequent restarts are faster (deps cached, vector store persists).

---

## 6. Set Environment Variables

### Via the configure wizard (recommended for credentials)

After the app is running, open `http://<app-url>/configure`:

1. Select your LLM provider from the dropdown
2. Fill in the URL, API key, and model ID for that provider
3. Click **Save Configuration**
4. Restart the app from the Cloudera AI Applications UI

The wizard shows source badges next to each field:
- 🟢 **From environment** — already set via platform UI, field is locked
- 🔵 **From saved file** — set by a previous wizard save
- ⬜ **Not set** — using code default

### Via Cloudera AI platform UI

Set these in the **Environment Variables** section of the Application config.

| Variable | Example value | Notes |
|---|---|---|
| `LLM_PROVIDER` | `cloudera` | See Section 4 for all options |
| `LLM_BASE_URL` | `https://...` | Inference endpoint URL |
| `LLM_API_KEY` | `sk-...` | API key |
| `LLM_MODEL_ID` | `meta-llama-3-8b-instruct` | Model name |

### Document storage

| Variable | Default | Notes |
|---|---|---|
| `DOCS_SOURCE_PATH` | `./data/sample_docs` | Path to documents for ingestion |
| `DOCS_STORAGE_TYPE` | `local` | `local`, `hdfs`, or `s3` |
| `VECTOR_STORE_PATH` | `./data/vector_store` | FAISS index location |

### Database

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/sample_tables/demo.db` | SQLAlchemy URL |
| `SQL_APPROVED_TABLES` | `kredit_umkm,nasabah,cabang` | Allowlist of tables the LLM can query |
| `SQL_MAX_ROWS` | `500` | Hard row cap on any query result |

### Optional tuning

| Variable | Default | Notes |
|---|---|---|
| `EMBEDDINGS_PROVIDER` | `local` | `local` or `openai` |
| `EMBEDDINGS_MODEL` | `intfloat/multilingual-e5-base` | Any sentence-transformers model |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` |
| `APP_PORT` | `8080` | **Do not change** |

---

## 7. Resource Profiles

| Scenario | vCPU | RAM | Notes |
|---|---|---|---|
| Demo (local embeddings) | 4 | 8 GB | First-start model download ~500 MB |
| Demo (OpenAI embeddings) | 1 | 2 GB | No local model needed |
| Production (light load) | 2 | 4 GB | |
| Production (HA, 2 replicas) | 2×2 | 2×4 GB | Use NFS for shared vector store |

---

## 8. Verify the Deployment

After status changes to **Running**:

### 8a. Open the health dashboard

Navigate to `http://<app-url>/setup`. All five cards should be green:

- ✅ **Vector Store** — FAISS index built and integrity hash verified
- ✅ **Database** — tables found with row counts
- ✅ **LLM** — endpoint reachable and ping latency shown
- ✅ **Embeddings** — provider and model confirmed
- ✅ **Documents** — source files listed

If any card is red, a **fix hint** is shown under the status. Click **⚙ Configure**
to open the credential wizard.

### 8b. Check the sidebar status indicator

Open the main app (`/`). The sidebar **System** row should show:
> ● All systems operational

If any component is red, the sidebar shows which one failed.

### 8c. Test a document question

Type:
> *Jelaskan ketentuan restrukturisasi kredit berdasarkan dokumen kebijakan.*

Expected: streaming answer with source document cards. Expand a card and click
**▼ Show full chunk** to verify keyword highlighting works.

### 8d. Test a data question

Type:
> *Berapa total outstanding pinjaman UMKM wilayah Jakarta pada Maret 2026?*

Expected: streaming answer + SQL trace panel showing the generated query and result table.

### 8e. Test the auto-play demo

Click **▶ Run Demo** in the sidebar. All six sample prompts should run
automatically. Click **⏹ Stop Demo** to interrupt.

### 8f. Check application logs

In the Applications list, click **...** → **View Logs**. Startup should show:

```
[0/5] No override file found at data/.env.local (use /configure to create one).
[1/5] Dependencies: already installed
[2/5] Provider SDK: not required for 'cloudera'.
[3/5] Database: found (3 tables).
[4/5] Vector store: found at ./data/vector_store — skipping ingestion.
[5/5] Starting FastAPI server (React UI) on port 8080...
INFO  SPA index.html cached (NNNNN bytes)
INFO  Startup check — vector store: OK
INFO  Startup check — database: OK (3 tables)
INFO  Startup check — LLM: configured (provider=cloudera, model=meta-llama-3-8b-instruct)
```

If an override file was saved via `/configure`:
```
[0/5] Loading config overrides from data/.env.local ...
    set LLM_BASE_URL from override file
    set LLM_API_KEY from override file
[0/5] Override file loaded.
```

### 8g. Run the test suite

From a CML Session terminal (or locally before deploying):

```bash
pytest tests/ -v
```

All tests must pass before deploying to production:

| Suite | Tests | Coverage |
|-------|-------|---------|
| `test_sql_guardrails.py` | 25 | SQL injection, subquery bypass, CTE, allowlist |
| `test_router.py` | 12 | LLM classification, aliases, error fallback |
| `test_retrieval.py` | 17 | Chunking, citations, mocked vector store |
| `test_api.py` | 12 | FastAPI endpoints, SSE shape, LLM provider indicators |

---

## 9. Update the Application

### Code changes

1. Push changes to the Git branch
2. In Applications list, click **...** → **Restart**
3. The container pulls the latest commit and reruns `launch_app.sh`
4. Dependencies and vector store are re-checked (not rebuilt unless missing)

### Credential changes

1. Open `http://<app-url>/configure`
2. Update the relevant fields and click **Save Configuration**
3. Click **Restart** in the Cloudera AI Applications UI

### Forcing document re-ingestion

1. Stop the application
2. Delete the vector store directory:
   ```bash
   rm -rf data/vector_store/
   ```
3. Restart — `launch_app.sh` detects the missing index and re-ingests all documents,
   writing a fresh `index.sha256` integrity file automatically.

> **Note:** Never copy a vector store from another environment without also copying
> its `index.sha256` file. A missing or mismatched hash causes the app to refuse
> loading the index.

---

## 10. Production Checklist

### Data & storage

- [ ] Replace `DATABASE_URL` with an enterprise database (PostgreSQL, Impala, Hive)
      and use **read-only** credentials
- [ ] Move documents to persistent storage (HDFS, S3, or NFS) and set
      `DOCS_STORAGE_TYPE` and `DOCS_SOURCE_PATH` accordingly
- [ ] Mount `VECTOR_STORE_PATH` to a persistent NFS volume so the index
      survives pod restarts and is shared across replicas
- [ ] Validate `SQL_APPROVED_TABLES` lists only the tables you intend to expose

### Security

- [ ] Enable SSO authentication on the Application (never use Unauthenticated
      with real data)
- [ ] Rotate the LLM API key and set it as a platform environment variable — it
      will be locked in the configure wizard ("From environment")
- [ ] Set `LOG_LEVEL=WARNING` or `ERROR` to avoid logging sensitive query content
- [ ] Validate `SQL_APPROVED_TABLES` against the principle of least privilege
- [ ] Confirm the vector store `index.sha256` file is present after every ingestion
      run; the app refuses to load an index whose hash is missing or mismatched
- [ ] Verify outbound HTTPS from the pod is restricted to known LLM endpoints
- [ ] Restrict access to `GET /configure` and `POST /api/configure` in production
      (or remove the configure wizard entirely if all vars are managed by the platform)

### Reliability

- [ ] Set replica count ≥ 2 for high availability
- [ ] Use `GET /api/status` as the health check endpoint — it returns JSON with
      `vector_store.ok`, `database.ok`, and `llm.ok` for load balancer probes
- [ ] Pre-build the vector store and store it on a persistent volume so
      startup does not depend on the first container to build it

### Embeddings

- [ ] If using `EMBEDDINGS_PROVIDER=local`: pre-download the model during
      image build or from a shared cache so startup does not hit HuggingFace
- [ ] If using `EMBEDDINGS_PROVIDER=openai`: confirm outbound HTTPS to
      `api.openai.com` is allowed from the workspace network

---

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError` | `pip install` failed — check network access to PyPI |
| `Connection refused` on LLM URL | Wrong `LLM_BASE_URL` or endpoint not running |
| `Port already in use: 8080` | Zombie uvicorn process — restart the application |
| `integrity check FAILED` | Vector store hash mismatch — delete `data/vector_store/` and re-ingest |
| `index.sha256 not found` | Index built without hash (older run) — re-ingest to generate it |
| `SPA not found` | `app/static/index.html` missing — check repo contents and redeploy |
| LLM indicator red for Bedrock/Anthropic | These providers have no `LLM_BASE_URL` — status is correctly inferred from `LLM_PROVIDER` |
| `/configure` shows "From environment" but changes don't apply | Platform env vars take precedence; update the value in the Cloudera AI Applications UI instead |
| Config saved but not applied after restart | Check that `launch_app.sh` ran step [0/5] and sourced `data/.env.local` |

### Sidebar shows `Vector Store: Belum diingest`

The FAISS index was not built. Check:
- `DOCS_SOURCE_PATH` contains at least one `.txt`, `.pdf`, or `.docx` file
- Ingestion step succeeded in startup logs (look for `document_loader`)
- `VECTOR_STORE_PATH` is writable

### LLM shows `Tidak Tersedia`

The LLM provider is not configured. Either:
- Open `/configure` and fill in the LLM credentials, or
- Set `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_ID` in the
  Cloudera AI Application environment variables and restart

### Answers are empty or the app times out

The LLM endpoint is configured but unreachable. Check:
- The inference endpoint is running and not scaled to zero
- Network connectivity between the app pod and the inference endpoint
- The API key is valid: `curl -H "Authorization: Bearer $LLM_API_KEY" $LLM_BASE_URL/models`

---

## 12. Environment Variable Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | Yes | `cloudera` | `cloudera` / `openai` / `bedrock` / `anthropic` / `local` |
| `LLM_BASE_URL` | Most providers | — | OpenAI-compatible endpoint base URL |
| `LLM_API_KEY` | Most providers | — | API key for the LLM provider |
| `LLM_MODEL_ID` | Yes | — | Model identifier (varies by provider) |
| `EMBEDDINGS_PROVIDER` | No | `local` | `local` or `openai` |
| `EMBEDDINGS_MODEL` | No | `intfloat/multilingual-e5-base` | HuggingFace model ID |
| `VECTOR_STORE_PATH` | No | `./data/vector_store` | FAISS index directory |
| `DOCS_SOURCE_PATH` | No | `./data/sample_docs` | Document source directory |
| `DOCS_STORAGE_TYPE` | No | `local` | `local`, `hdfs`, or `s3` |
| `DATABASE_URL` | No | SQLite demo | SQLAlchemy connection URL |
| `SQL_APPROVED_TABLES` | No | `kredit_umkm,nasabah,cabang` | Allowlist of queryable tables |
| `SQL_MAX_ROWS` | No | `500` | Max rows per query (hard cap: 1000) |
| `APP_PORT` | No | `8080` | **Must stay 8080** for Cloudera AI compatibility |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

> All variables can be set via the **Cloudera AI Applications environment variables UI**
> or via the browser **`/configure` wizard** (which writes `data/.env.local`).
> Platform environment variables always take precedence over the override file.
