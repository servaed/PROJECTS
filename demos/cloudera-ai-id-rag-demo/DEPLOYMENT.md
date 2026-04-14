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
│   │     ├── React SPA        GET /          (served from app/static/)
│   │     ├── Chat stream      POST /api/chat (Server-Sent Events)
│   │     ├── System status    GET /api/status
│   │     └── Sample prompts   GET /api/samples
│   ├── RAG pipeline           FAISS vector store on pod filesystem (or NFS)
│   └── SQL pipeline           SQLite demo DB (or external JDBC)
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

Set `LLM_PROVIDER` to one of the supported values and fill in the
corresponding credentials (see [Section 6](#6-set-environment-variables)).

### Cloudera AI Inference (recommended for Cloudera demos)

1. Go to **AI Inference** in your workspace
2. Deploy a model (e.g. `meta-llama-3-8b-instruct`, `mistral-7b-instruct`)
3. Copy the **API URL** and **API Key** from the endpoint detail page
4. Set in environment variables:
   ```
   LLM_PROVIDER=cloudera
   CLOUDERA_INFERENCE_URL=https://your-workspace.cloudera.site/namespaces/serving/endpoints/your-model
   CLOUDERA_INFERENCE_API_KEY=<key from inference endpoint>
   CLOUDERA_INFERENCE_MODEL_ID=meta-llama-3-8b-instruct
   ```

### OpenAI

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL_ID=gpt-4o
```

### Azure OpenAI

```
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_DEPLOYMENT=gpt-4o          # your deployment name, not the model name
AZURE_OPENAI_API_VERSION=2024-02-01
```

### Amazon Bedrock

```
LLM_PROVIDER=bedrock
BEDROCK_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Option A — IAM instance role (recommended for CML on AWS): leave keys empty
BEDROCK_ACCESS_KEY=
BEDROCK_SECRET_KEY=

# Option B — explicit credentials
BEDROCK_ACCESS_KEY=AKIA...
BEDROCK_SECRET_KEY=...
```

Popular Bedrock model IDs:

| Model | ID |
|---|---|
| Claude 3.5 Sonnet | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| Claude 3 Sonnet | `anthropic.claude-3-sonnet-20240229-v1:0` |
| Llama 3 70B | `meta.llama3-70b-instruct-v1:0` |
| Mistral Large | `mistral.mistral-large-2402-v1:0` |

### Anthropic (direct)

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL_ID=claude-3-5-sonnet-20241022
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
| **Launch Command** | `bash deployment/launch_app.sh` | Runs pip install, DB seed, vector ingest, then uvicorn (FastAPI) |
| **Runtime** | Python 3.10 (Standard or ML Runtime) | Any CML runtime with Python 3.10+ |
| **Enable Spark** | Off | Not needed |

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

Under **Authentication**:

| Option | When to use |
|---|---|
| **Unauthenticated** | Internal demos, no sensitive data |
| **Authenticate via SSO** | Production; uses your workspace SSO (LDAP/AD/SAML) |

For SSO, any user who can log in to the CML workspace can access the app.
No additional auth config is needed in the app itself.

---

### Step 6 — Set Environment Variables

Click **Add Environment Variable** and add each variable from
[Section 6](#6-set-environment-variables).

**At minimum, set these before deploying:**

```
LLM_PROVIDER
CLOUDERA_INFERENCE_URL    (or your provider's equivalent)
CLOUDERA_INFERENCE_API_KEY
```

---

### Step 7 — Deploy

Click **Deploy Application**.

The status indicator will show:

| Status | Meaning |
|---|---|
| `Starting` | Container is pulling and starting |
| `Running` | App is live — click the URL to open it |
| `Stopped` | App was manually stopped |
| `Failed` | Startup error — check logs |

First startup takes **3–10 minutes** because:
- `pip install -r requirements.txt` runs on first boot
- The HuggingFace embeddings model is downloaded (~500 MB)
- Documents are ingested into the FAISS vector store

Subsequent restarts are faster (deps cached, vector store persists).

---

## 6. Set Environment Variables

Set these in the **Environment Variables** section of the Application config.
All values from `.env.example` can be set here.

### Minimum required

| Variable | Example value | Notes |
|---|---|---|
| `LLM_PROVIDER` | `cloudera` | See Section 4 for all options |
| `CLOUDERA_INFERENCE_URL` | `https://...` | Your inference endpoint URL |
| `CLOUDERA_INFERENCE_API_KEY` | `sk-...` | Inference API key |
| `CLOUDERA_INFERENCE_MODEL_ID` | `meta-llama-3-8b-instruct` | Model name |

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

### 8a. Check the status panel

Open the app URL. In the sidebar, the **Status Sistem** panel should show:

- ✅ **Vector Store: Aktif** — FAISS index built and loaded
- ✅ **Database: 3 tabel** — SQLite connected
- ✅ **LLM: meta-llama-3-8b-instruct** — endpoint configured

If any indicator is red, check the logs.

### 8b. Test a document question

Type:
> *Jelaskan ketentuan restrukturisasi kredit berdasarkan dokumen kebijakan.*

Expected: the answer cites a source document in the **Sumber Dokumen** panel.

### 8c. Test a data question

Type:
> *Berapa total outstanding pinjaman UMKM wilayah Jakarta pada Maret 2026?*

Expected: the answer shows a number and the **Query Data Terstruktur** panel
shows the executed SQL and result table.

### 8d. Test conversation memory

Ask a follow-up:
> *Bandingkan dengan wilayah Surabaya.*

Expected: the assistant understands "compare with Surabaya" without
repeating the full context.

### 8e. Check application logs

In the Applications list, click **...** → **View Logs** next to your app.
Startup should show:

```
========================================================
 Cloudera AI Application — Startup
========================================================
 Python   : Python 3.10.x
 Port     : 8080
 Provider : cloudera
 CWD      : /home/cdsw
========================================================
[1/5] Dependencies: already installed
[2/5] Provider SDK: not required for 'cloudera'.
[3/5] Database: found (3 tables).
[4/5] Vector store: found at ./data/vector_store — skipping ingestion.
[5/5] Starting FastAPI server (React UI) on port 8080...
========================================================
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
INFO  SPA index.html cached (NNNNN bytes)
INFO  Startup check — vector store: OK (./data/vector_store)
INFO  Startup check — database: OK (3 tables)
INFO  Startup check — LLM: configured (provider=cloudera, model=meta-llama-3-8b-instruct)
```

If a startup check shows `WARNING` instead of `INFO`, the corresponding feature
(vector store / database / LLM) is not ready and questions will fail until it is fixed.

### 8f. Run the test suite

From a CML Session terminal (or locally before deploying):

```bash
pytest tests/ -v
```

All tests must pass before deploying to production. The three test suites cover:
- `test_sql_guardrails.py` — SQL injection, subquery bypass, table allowlist
- `test_router.py` — LLM classification, error fallback behaviour
- `test_retrieval.py` — chunking, citation building, mocked vector store

---

## 9. Update the Application

When you push new code to the Git branch:

1. In the Applications list, click **...** → **Restart**
2. The container pulls the latest commit and reruns `launch_app.sh`
3. Dependencies and vector store are re-checked (not rebuilt unless missing)

To force a full re-ingestion (e.g. after adding new documents):

1. Stop the application
2. Delete the vector store directory (this also removes the integrity hash file):
   ```bash
   rm -rf data/vector_store/
   ```
   Or set a new `VECTOR_STORE_PATH` environment variable to a fresh path.
3. Restart — `launch_app.sh` detects the missing index, re-ingests all documents,
   and writes a new `index.sha256` integrity file automatically.

> **Note:** Never copy a vector store from another environment without also copying
> its `index.sha256` file. A missing or mismatched hash causes the app to refuse
> loading the index and log an error on startup.

---

## 10. Production Checklist

Before going to production with real enterprise data:

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
- [ ] Rotate the LLM API key and set it as an environment variable — never
      commit it to Git
- [ ] Set `LOG_LEVEL=WARNING` or `ERROR` to avoid logging sensitive query content
- [ ] Validate `SQL_APPROVED_TABLES` against the principle of least privilege —
      expose only the tables required for the demo, nothing else
- [ ] Confirm the vector store `index.sha256` file is present after every ingestion
      run; the app refuses to load an index whose hash is missing or mismatched
- [ ] Verify outbound HTTPS from the pod is restricted to known LLM endpoints only
      (configure network policy in the workspace if available)

### Reliability

- [ ] Set replica count ≥ 2 for high availability
- [ ] Use `GET /api/status` as the health check endpoint — it returns JSON with
      `vector_store.ok`, `database.ok`, and `llm.ok` fields for load balancer probes
- [ ] Pre-build the vector store and store it on a persistent volume so
      startup is fast and does not depend on the first container to build it

### Embeddings

- [ ] If using `EMBEDDINGS_PROVIDER=local`: pre-download the model during
      image build or from a shared cache so startup does not hit HuggingFace
- [ ] If using `EMBEDDINGS_PROVIDER=openai`: confirm outbound HTTPS to
      `api.openai.com` is allowed from the workspace network

---

## 11. Troubleshooting

### App shows `Failed` or does not start

Check **View Logs**. Common causes:

| Log message | Fix |
|---|---|
| `ModuleNotFoundError` | `pip install` failed — check network access to PyPI |
| `Connection refused` on LLM URL | Wrong `CLOUDERA_INFERENCE_URL` or endpoint not running |
| `Port already in use` | Another process on 8080 — check for zombie processes |
| `Address already in use: 8080` | Another process on port 8080 — check for zombie uvicorn processes |
| `FAISS index failed to load` | Corrupted index — delete `data/vector_store/` to force rebuild |
| `integrity check FAILED` | Vector store hash mismatch — delete `data/vector_store/` and re-ingest |
| `index.sha256` not found | Index was built without the integrity hash (older run) — re-ingest to generate it |
| `SPA not found` | `app/static/index.html` is missing — check repo contents and redeploy |

### Sidebar shows `Vector Store: Belum diingest`

The FAISS index was not built. This happens when:
- `DOCS_SOURCE_PATH` is empty or doesn't exist
- The ingestion step failed during startup (check logs for `document_loader` errors)
- `VECTOR_STORE_PATH` points to a non-writable location

Fix: check `DOCS_SOURCE_PATH` contains at least one `.txt`, `.pdf`, or `.docx` file,
then restart the app.

### Sidebar shows `Database: Tidak terhubung`

- For the demo SQLite path: `data/sample_tables/demo.db` — the file doesn't exist.
  The launch script seeds it automatically; if it failed, check logs.
- For external databases: check `DATABASE_URL` format and network connectivity.

### LLM shows `Tidak Tersedia` (LLM URL not configured)

`CLOUDERA_INFERENCE_URL` (or the equivalent for your provider) is empty.
Set the correct env var and restart.

### Answers are empty or the app times out

The LLM endpoint is configured but unreachable or slow. Check:
- The inference endpoint is running and not scaled to zero
- Network connectivity between the app pod and the inference endpoint
- The API key is valid (test with `curl -H "Authorization: Bearer $API_KEY" $URL/models`)

### First startup is very slow (>10 min)

The HuggingFace embeddings model is downloading. Expected once per fresh pod.
To eliminate this delay in production, switch to `EMBEDDINGS_PROVIDER=openai`
or pre-cache the model on a shared volume.

---

## 12. Environment Variable Reference

Full list of supported environment variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | Yes | `cloudera` | `cloudera` / `openai` / `azure` / `bedrock` / `anthropic` / `local` |
| `CLOUDERA_INFERENCE_URL` | If cloudera | — | Cloudera AI Inference endpoint URL |
| `CLOUDERA_INFERENCE_API_KEY` | If cloudera | — | Inference service API key |
| `CLOUDERA_INFERENCE_MODEL_ID` | No | `meta-llama-3-8b-instruct` | Model name on the endpoint |
| `OPENAI_API_KEY` | If openai | — | OpenAI API key |
| `OPENAI_MODEL_ID` | No | `gpt-4o` | OpenAI model name |
| `AZURE_OPENAI_ENDPOINT` | If azure | — | `https://resource.openai.azure.com` |
| `AZURE_OPENAI_API_KEY` | If azure | — | Azure key |
| `AZURE_OPENAI_DEPLOYMENT` | No | `gpt-4o` | Azure deployment name |
| `AZURE_OPENAI_API_VERSION` | No | `2024-02-01` | API version string |
| `BEDROCK_REGION` | If bedrock | `us-east-1` | AWS region |
| `BEDROCK_MODEL_ID` | If bedrock | `anthropic.claude-3-sonnet-20240229-v1:0` | Bedrock model ID |
| `BEDROCK_ACCESS_KEY` | No | — | AWS access key (leave empty for instance role) |
| `BEDROCK_SECRET_KEY` | No | — | AWS secret key |
| `BEDROCK_SESSION_TOKEN` | No | — | STS session token |
| `BEDROCK_PROFILE` | No | — | Named AWS profile |
| `ANTHROPIC_API_KEY` | If anthropic | — | Anthropic API key |
| `ANTHROPIC_MODEL_ID` | No | `claude-3-5-sonnet-20241022` | Claude model name |
| `LOCAL_LLM_URL` | If local | `http://localhost:11434/v1` | Local server base URL |
| `LOCAL_LLM_MODEL_ID` | No | `llama3` | Local model name |
| `EMBEDDINGS_PROVIDER` | No | `local` | `local` or `openai` |
| `EMBEDDINGS_MODEL` | No | `intfloat/multilingual-e5-base` | HuggingFace model ID |
| `VECTOR_STORE_PATH` | No | `./data/vector_store` | FAISS index directory |
| `DOCS_SOURCE_PATH` | No | `./data/sample_docs` | Document source directory |
| `DOCS_STORAGE_TYPE` | No | `local` | `local`, `hdfs`, or `s3` |
| `DATABASE_URL` | No | SQLite demo | SQLAlchemy connection URL |
| `SQL_APPROVED_TABLES` | No | `kredit_umkm,nasabah,cabang` | Allowlist of queryable tables |
| `SQL_MAX_ROWS` | No | `500` | Max rows per query (hard cap: 1000) |
| `APP_PORT` | No | `8080` | Must stay 8080 for CML compatibility |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
