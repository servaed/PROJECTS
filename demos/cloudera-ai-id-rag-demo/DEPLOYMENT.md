# Deployment Guide — Cloudera AI Workbench

This guide covers deploying **cloudera-ai-id-rag-demo** as a
[Cloudera AI Application](https://docs.cloudera.com/machine-learning/cloud/applications/topics/ml-applications.html)
on Cloudera AI Workbench (CML) using the **Git Source** path.

> **Demo architecture note:** The demo runs on DuckDB (reading local Parquet files) + local filesystem.
> In a real enterprise deployment this maps to Cloudera Data Warehouse (Trino + Iceberg on Ozone) —
> the same SQL dialect and same Parquet/Iceberg file format, swap the connectors via env vars.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Step 1 — Create a CML Project from Git](#2-step-1--create-a-cml-project-from-git)
3. [Step 2 — Create the CML Application](#3-step-2--create-the-cml-application)
4. [Step 3 — Configure LLM Provider](#4-step-3--configure-llm-provider)
5. [Step 4 — Startup Timeline](#5-step-4--startup-timeline)
6. [Step 5 — Verify the Deployment](#6-step-5--verify-the-deployment)
7. [Updating the Application](#7-updating-the-application)
8. [Adding Documents to the Knowledge Base](#8-adding-documents-to-the-knowledge-base)
9. [Resource Profiles](#9-resource-profiles)
10. [Production Checklist](#10-production-checklist)
11. [Troubleshooting](#11-troubleshooting)
12. [Environment Variable Reference](#12-environment-variable-reference)

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Cloudera AI Workbench workspace | Admin or Project Creator role |
| Applications feature enabled | Site Administration → Applications; contact admin if missing |
| LLM endpoint | One of: Cloudera AI Inference, OpenAI, Azure OpenAI, Bedrock, Anthropic, Ollama |
| Git repository accessible | HTTPS recommended; SSH supported if no HTTP proxy |

### Minimum Resource Profile

| Mode | vCPU | RAM |
|---|---|---|
| Local embeddings (multilingual-e5-large) | 4 | 8 GiB |
| OpenAI embeddings | 1 | 2 GiB |

> Set `EMBEDDINGS_PROVIDER=openai` + `OPENAI_API_KEY` to reduce RAM to 2 GiB (no local model).

---

## 2. Step 1 — Create a CML Project from Git

1. In your CML workspace, click **New Project**
2. Select **Git** as the source
3. Choose **HTTPS** (recommended) or **SSH**

**HTTPS:**
```
https://github.com/servaed/PROJECTS.git
```
For private repos, embed a Personal Access Token (PAT):
```
https://servaed:<GITHUB_PAT>@github.com/servaed/PROJECTS.git
```

**SSH** (only if workspace has direct internet — SSH through HTTP proxy is not supported):
```
git@github.com:servaed/PROJECTS.git
```
For SSH: go to **User Settings → SSH Keys**, copy the public key, add it to
**GitHub → Settings → SSH and GPG keys**.

**Branch:** `master`

4. Click **Create Project** — CML clones the full repo into the project.

---

## 3. Step 2 — Create the CML Application

> **Important:** CML Applications execute the Script field as Python, not bash.
> `run_app.py` is a Python launcher that calls `deployment/launch_app.sh` via subprocess.

Inside the project: **Applications → New Application**

| Field | Value |
|---|---|
| **Name** | `Asisten Enterprise ID` |
| **Subdomain** | `asisten-enterprise` (a–z, 0–9, hyphens only) |
| **Script** | `demos/cloudera-ai-id-rag-demo/run_app.py` |
| **Editor** | `Workbench` |
| **Kernel** | `Python 3.10` |
| **Edition** | `Standard` |
| **Resource Profile** | 4 vCPU / 8 GiB (or 1 vCPU / 2 GiB with OpenAI embeddings) |
| **Enable Spark** | OFF |
| **Enable GPU** | OFF |

Add LLM environment variables (see [Step 3](#4-step-3--configure-llm-provider)), then click **Create Application**.

---

## 4. Step 3 — Configure LLM Provider

There are **three ways** to set credentials — pick one per deployment:

| Method | When to use |
|---|---|
| **A — Application env vars** | Set in the New Application form before deploying |
| **B — /configure browser wizard** | After deploy, without shell access |
| **C — Project-level env vars** | Project Settings → Advanced → Environment Variables |

> **Precedence:** Application env vars (A) > Project env vars (C) > `data/.env.local` (B) > code defaults.
> A variable set via Method A appears locked ("From environment") in the `/configure` wizard.

---

### Cloudera AI Inference

Find the endpoint URL and API key at: **CML Workspace → AI Inference → your model → Endpoint Details**

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `cloudera` |
| `LLM_BASE_URL` | `https://ml-xxxx.cloudera.com/namespaces/serving/endpoints/your-model/v1` |
| `LLM_API_KEY` | *(key from endpoint detail page)* |
| `LLM_MODEL_ID` | `meta-llama-3-8b-instruct` |

---

### OpenAI

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `openai` |
| `LLM_API_KEY` | `sk-proj-...` |
| `LLM_MODEL_ID` | `gpt-4o` |

---

### Azure OpenAI

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `azure` |
| `AZURE_OPENAI_ENDPOINT` | `https://your-resource.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | *(key from Azure portal → Keys and Endpoint)* |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` *(deployment name, not model name)* |
| `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` |

---

### Amazon Bedrock

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `bedrock` |
| `LLM_MODEL_ID` | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| `AWS_DEFAULT_REGION` | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | *(omit to use IAM instance role)* |
| `AWS_SECRET_ACCESS_KEY` | |

---

### Anthropic

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `anthropic` |
| `LLM_API_KEY` | `sk-ant-api03-...` |
| `LLM_MODEL_ID` | `claude-sonnet-4-6` |

---

### Local / Ollama / vLLM

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `local` |
| `LLM_BASE_URL` | `http://your-ollama-host:11434/v1` |
| `LLM_MODEL_ID` | `llama3.2` |
| `LLM_API_KEY` | `no-key` |

---

### /configure Browser Wizard (Method B)

1. Open `http://<app-url>/configure` after the app is running
2. Select your LLM provider and fill in credentials
3. Click **Save Configuration**
4. Restart from **Applications UI → ⋯ → Restart**

---

## 5. Step 4 — Startup Timeline

`run_app.py` → `deployment/launch_app.sh`:

```
[0/5] Load data/.env.local (saved by /configure wizard on prior runs)
[1/5] pip install -r requirements.txt  (skipped after first run)
[2/5] Install provider SDK if needed (boto3 for Bedrock, anthropic package)
[3/5] Seed Parquet files via seed_parquet.py — 9 tables, 1485 rows (idempotent, checks msme_credit.parquet)
[4/5] Build FAISS vector store (skipped if data/vector_store/index.faiss exists)
      First run: downloads multilingual-e5-large (~500 MB) — please wait
[5/5] exec uvicorn app.api:app on $CDSW_APP_PORT
```

**First boot:** ~3–5 min (embedding model download + Parquet seed)
**Warm restart:** ~30 s (pip skipped, Parquet files already present, vector store skipped)

---

## 6. Step 5 — Verify the Deployment

### Health Dashboard

Navigate to `http://<app-url>/setup`. All status cards must be green:

- ✅ **Vector Store** — FAISS index present and SHA-256 verified
- ✅ **Database** — 9 tables found with row counts
- ✅ **LLM** — endpoint reachable, ping latency shown
- ✅ **Embeddings** — provider and model confirmed
- ✅ **Documents** — source files listed

### Test with Sample Questions

**Document RAG:**
> *Jelaskan ketentuan restrukturisasi kredit berdasarkan dokumen kebijakan.*

Expected: streaming Indonesian answer with source document citation cards.

**SQL query:**
> *Berapa total outstanding pinjaman UMKM wilayah Jakarta pada Maret 2026?*

Expected: answer + SQL trace panel + result table + bar chart.

**English mode** (toggle in sidebar):
> *Show the top 5 UMKM borrowers by outstanding balance.*

### Run the Auto-Play Demo

Click **▶ Run Demo** in the sidebar. All sample prompts play automatically.

### Check Logs

Open `/setup → Logs`. Expected on successful startup:

```
[0/5] No override file found at data/.env.local ...
[1/5] Dependencies: already installed ...
[2/5] Provider SDK: not required for 'openai'.
[3/5] Database: found (9 tables).
[4/5] Vector store: found at ./data/vector_store — skipping ingestion.
[5/5] Starting FastAPI server (React UI) on port 8080...
INFO  Startup check — vector store: OK
INFO  Startup check — database: OK (9 tables via duckdb)
INFO  Startup check — LLM: configured (provider=openai)
```

---

## 7. Updating the Application

### After a Code Change

```bash
# In a CML Session terminal inside the project:
git pull origin master

# Then restart:
# Applications → your app → ⋯ → Restart
```

### Credential Change Only

1. Open `http://<app-url>/configure`
2. Update credentials → **Save Configuration**
3. Applications UI → **Restart**

### Force Re-ingestion (after adding new documents)

```bash
# In a CML Session terminal:
rm -rf demos/cloudera-ai-id-rag-demo/data/vector_store/
# Then restart — ingestion runs automatically
```

Or use the **⟳ Re-ingest** button on `/setup` (no restart needed).

---

## 8. Adding Documents to the Knowledge Base

Place new files under `data/sample_docs/` in the appropriate domain folder:

```
data/sample_docs/
  banking/      ← domain = "banking"
  telco/        ← domain = "telco"
  government/   ← domain = "government"
```

Supported formats: `.txt`, `.pdf`, `.docx`, `.md`, `.html`

Then rebuild the vector store:

- **Re-ingest button:** `http://<app-url>/setup` → **⟳ Re-ingest**
- **API:** `curl -X POST http://<app-url>/api/ingest`
- **CLI (Session terminal):** `python -m src.retrieval.document_loader`

---

## 9. Resource Profiles

| Mode | vCPU | RAM |
|---|---|---|
| Local embeddings (e5-large) | **4** | **8 GiB** |
| OpenAI embeddings | **1** | **2 GiB** |

To use OpenAI embeddings: set `EMBEDDINGS_PROVIDER=openai` and `OPENAI_API_KEY`.
Reduces RAM by ~3 GB, adds API cost per query.

---

## 10. Production Checklist

- [ ] Set LLM credentials via **Application-level env vars** — locked from browser override
- [ ] `SQL_APPROVED_TABLES` lists only the tables you intend to expose
- [ ] `LOG_LEVEL=WARNING` — avoids logging user message content
- [ ] SSO authentication enabled (default). Unauthenticated/public access requires admin
  to enable "Allow applications to be configured with unauthenticated access" in Site Administration
- [ ] `GET /health` returns `{"status":"ok"}` — use as liveness probe URL
- [ ] `index.sha256` present after every ingestion run (integrity gate)

---

## 11. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `SyntaxError` or `NameError: __file__` | Script pointing to `.sh` file or `__file__` undefined | Ensure Script is `run_app.py`, not `launch_app.sh` |
| App stuck at "Starting" for >5 min | pip install or embedding model download | Check `/setup → Logs`; first boot takes 3–5 min |
| `ModuleNotFoundError` | `requirements.txt` incomplete or pip failed | Check logs; verify network access to PyPI |
| LLM indicator red | Wrong credentials or URL | Open `/configure` → ⚡ Test LLM → fix |
| Azure LLM returns 404 | Using `LLM_BASE_URL` instead of `AZURE_OPENAI_ENDPOINT` | Set `AZURE_OPENAI_ENDPOINT` correctly |
| `/configure` shows "From environment" but wrong | Application env var overrides wizard | Update via Applications UI → env vars → restart |
| `integrity check FAILED` | `index.sha256` mismatch | Delete `data/vector_store/` → restart |
| Git clone fails via SSH | SSH through HTTP proxy not supported | Switch to HTTPS with PAT |
| App URL not accessible | Subdomain has invalid characters | Use only a–z, 0–9, hyphens |
| `git pull` shows no updates in CML | CML project is a shallow clone | Run `git fetch origin master` then `git pull` |

---

## 12. Environment Variable Reference

> Variables can be set via:
> - **Application env vars** (Applications UI) — highest precedence, locks field in `/configure`
> - **Project env vars** (Project Settings → Advanced) — overridden by Application env vars
> - **`/configure` browser wizard** — writes to `data/.env.local`
> - **`.env` file** (local dev only)

### LLM — Common

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | Yes | `cloudera` / `openai` / `azure` / `bedrock` / `anthropic` / `local` |
| `LLM_BASE_URL` | Most | OpenAI-compatible endpoint URL (not needed for Bedrock / Anthropic) |
| `LLM_API_KEY` | Most | API key |
| `LLM_MODEL_ID` | Yes | Model or deployment name |

### LLM — Cloudera AI Inference

| Variable | Default | Description |
|---|---|---|
| `CLOUDERA_INFERENCE_URL` | — | Full inference endpoint URL |
| `CLOUDERA_INFERENCE_API_KEY` | — | Endpoint API key |
| `CLOUDERA_INFERENCE_MODEL_ID` | `meta-llama-3-8b-instruct` | Model name |

### LLM — Azure OpenAI

| Variable | Required | Description |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | Yes | `https://your-resource.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Yes | Azure API key |
| `AZURE_OPENAI_DEPLOYMENT` | Yes | Deployment name (not model name) |
| `AZURE_OPENAI_API_VERSION` | No | Default: `2024-02-01` |

### LLM — Amazon Bedrock

| Variable | Required | Description |
|---|---|---|
| `LLM_MODEL_ID` | Yes | Bedrock model ID |
| `AWS_DEFAULT_REGION` | Yes | AWS region |
| `AWS_ACCESS_KEY_ID` | No | Omit to use IAM instance role |
| `AWS_SECRET_ACCESS_KEY` | No | |
| `AWS_SESSION_TOKEN` | No | STS temporary session token |

### Embeddings

| Variable | Default | Description |
|---|---|---|
| `EMBEDDINGS_PROVIDER` | `local` | `local` or `openai` |
| `EMBEDDINGS_MODEL` | `intfloat/multilingual-e5-large` | HuggingFace model or OpenAI model |

### Query Engine / Database

| Variable | Default | Description |
|---|---|---|
| `QUERY_ENGINE` | `duckdb` | `duckdb` (local Parquet) or `trino` (CDP CDW) |
| `DUCKDB_PARQUET_DIR` | `./data/parquet` | Directory of Parquet files read by DuckDB |
| `SQL_APPROVED_TABLES` | all 9 demo tables | Comma-separated table allowlist for LLM queries |
| `SQL_MAX_ROWS` | `500` | Max rows per result (hard cap: 1000) |

**Trino settings** (when `QUERY_ENGINE=trino`):

| Variable | Default | Description |
|---|---|---|
| `TRINO_HOST` | `localhost` | Trino coordinator hostname |
| `TRINO_PORT` | `8085` | Trino HTTP port |
| `TRINO_CATALOG` | `iceberg` | Catalog name |
| `TRINO_SCHEMA` | `demo` | Schema within the catalog |
| `TRINO_USER` | `admin` | Trino username |

### Documents

| Variable | Default | Description |
|---|---|---|
| `DOCS_STORAGE_TYPE` | `local` | `local` or `s3` (Ozone/MinIO) |
| `DOCS_SOURCE_PATH` | `./data/sample_docs` | Used when `DOCS_STORAGE_TYPE=local` |

### Application

| Variable | Default | Description |
|---|---|---|
| `APP_PORT` | `8080` | Fallback; CML injects `CDSW_APP_PORT` (default 8080) |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
