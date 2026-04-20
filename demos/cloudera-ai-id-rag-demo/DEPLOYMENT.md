# Deployment Guide — Cloudera AI Workbench

This guide covers deploying **cloudera-ai-id-rag-demo** as a
[Cloudera AI Application](https://docs.cloudera.com/machine-learning/cloud/applications/topics/ml-applications.html)
on Cloudera AI Workbench (CML).

Two deployment paths are available:

| Path | Entry point | Storage | Query engine | Recommended for |
|------|-------------|---------|--------------|-----------------|
| **Docker image** (recommended) | `deployment/entrypoint.sh` | MinIO → Ozone | Trino + Iceberg | Full Cloudera demo, production presales |
| **Git source** | `deployment/launch_app.sh` | Local filesystem | SQLite | Quick iteration, no Docker registry |

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Path A — Docker Image (Recommended)](#3-path-a--docker-image-recommended)
4. [Path B — Git Source (SQLite Mode)](#4-path-b--git-source-sqlite-mode)
5. [Configure Your LLM Provider](#5-configure-your-llm-provider)
6. [Environment Variables](#6-environment-variables)
7. [Resource Profiles](#7-resource-profiles)
8. [Verify the Deployment](#8-verify-the-deployment)
9. [Update the Application](#9-update-the-application)
10. [Production Checklist](#10-production-checklist)
11. [Troubleshooting](#11-troubleshooting)
12. [Environment Variable Reference](#12-environment-variable-reference)

---

## 1. Architecture Overview

### Docker / CML mode (full stack)

```
Cloudera AI Workbench
│
└── AI Application (single container)
    │
    ├── uvicorn :8080   ← exposed by CML reverse proxy
    │     ├── React SPA        GET /              chat interface
    │     ├── Health dashboard GET /setup         component status
    │     ├── Config wizard    GET /configure     set env vars via browser
    │     ├── Chat stream      POST /api/chat     Server-Sent Events
    │     └── ... other API routes
    │
    ├── RAG pipeline    FAISS vector store  (documents from MinIO)
    ├── SQL pipeline    Trino → Iceberg → MinIO  (guarded SELECT only)
    │
    ├── Trino  :8085    Distributed SQL — Iceberg connector
    ├── Nessie :19120   Iceberg REST catalog
    └── MinIO  :9000    S3-compatible object store (docs + warehouse buckets)
```

### Local dev mode (lightweight)

```
Developer laptop
│
└── uvicorn :8080
    ├── RAG pipeline    FAISS vector store  (documents from data/sample_docs/)
    └── SQL pipeline    SQLite → demo.db    (seeded by seed_database.py)
```

The app **must listen on port 8080** — Cloudera AI Applications proxies all
traffic through its reverse proxy to that port.

---

## 2. Prerequisites

| Requirement | Notes |
|---|---|
| Cloudera AI Workbench workspace | Admin or Project Creator role |
| Applications feature enabled | Ask workspace admin if not visible |
| Docker registry (Path A) | Harbor, ECR, DockerHub — accessible from the workspace |
| Git repository (Path B) | GitHub, GitLab, Bitbucket — accessible from workspace network |
| LLM endpoint | Cloudera AI Inference, OpenAI, Azure OpenAI, Bedrock, Anthropic, or local Ollama |
| Docker Desktop / BuildKit (Path A) | To build the multi-stage image locally |

### Check that Applications are enabled

In your workspace, go to **Site Administration → Applications**.
If the menu item is missing, contact your Cloudera platform admin.

---

## 3. Path A — Docker Image (Recommended)

### 3a. Build the image

**Option 1 — Makefile (recommended):**
```bash
make docker                                   # build with default tag
make docker REGISTRY=ghcr.io/your-org TAG=v1.0.0   # custom registry + tag
make docker-push REGISTRY=ghcr.io/your-org    # push after build
```

**Option 2 — GitHub Actions (fully automated):**
The repo includes `.github/workflows/docker-build.yml`. On every push to `main` or
`master`, or on a semver tag (`v*.*.*`), the workflow:
- Builds the image
- Pushes to GHCR (`ghcr.io/<org>/cloudera-ai-id-rag-demo`)
- Tags with branch name, semver, `latest` (default branch), and `sha-<short>`

No manual `docker push` needed for teams using GitHub.

**Option 3 — Docker directly:**
```bash
docker build -t cloudera-ai-id-rag-demo:latest .
docker tag cloudera-ai-id-rag-demo:latest <registry>/cloudera-ai-id-rag-demo:latest
docker push <registry>/cloudera-ai-id-rag-demo:latest
```

The multi-stage Dockerfile:
- **Stage 1** (`infra`) — downloads MinIO binary, Nessie JAR, and Trino 455 tarball
- **Stage 2** — Python 3.11-slim + OpenJDK 17 + all Python deps + infra binaries

Build time: ~5–10 min first time (downloads ~800 MB of infra binaries).

### 3b. Test the image locally

**Option 1 — Docker Compose (easiest):**
```bash
cp .env.example .env     # set LLM_PROVIDER, LLM_API_KEY, etc.
docker compose up
```
Open **http://localhost:8080**. Named volumes (`vector-store`, `minio-data`) persist
across restarts. The startup banner on `/setup` fades once all services are ready.

**Option 2 — Makefile:**
```bash
export LLM_PROVIDER=openai LLM_API_KEY=sk-... LLM_MODEL_ID=gpt-4o
make docker-run
```

**Option 3 — Docker directly:**
```bash
docker run --rm -p 8080:8080 \
  -e LLM_PROVIDER=openai \
  -e LLM_API_KEY=sk-... \
  -e LLM_MODEL_ID=gpt-4o \
  cloudera-ai-id-rag-demo:latest
```

Open **http://localhost:8080/setup**. All status cards should be green after
the first-boot seeding completes (~2–4 min).

### 3d. Create the Cloudera AI Application

1. In your workspace, click **Applications → + New Application**
2. Fill in:

| Field | Value |
|---|---|
| **Name** | `Asisten Enterprise ID` |
| **Subdomain** | `asisten-enterprise` |
| **Source** | **Docker Image** |
| **Image URL** | `<registry>/cloudera-ai-id-rag-demo:latest` |
| **Resource Profile** | 4 vCPU / 8 GB RAM (see Section 7) |
| **Auth Type** | SSO (recommended) or Unauthenticated |

3. Set LLM environment variables (see Section 5)
4. Click **Deploy Application**

### 3e. What `entrypoint.sh` does on startup

```
[1/6] Start MinIO on :9000  — wait for health check
[2/6] Start Nessie on :19120 — wait for health check
[3/6] Start Trino on :8085  — wait for health check (up to 5 min)
[4/6] Run deployment/seed_iceberg.py:
        - Create buckets: rag-docs, rag-warehouse
        - Upload data/sample_docs/ to MinIO (preserving banking/telco/government/ prefixes)
        - CREATE SCHEMA iceberg.demo WITH (location='s3://rag-warehouse/')
        - Drop + recreate all 9 Iceberg tables with demo data
[5/6] Build FAISS vector store (skipped if index already exists)
[6/6] exec uvicorn app.api:app --host 0.0.0.0 --port $PORT
```

First boot: ~3–5 min (Trino startup + seeding). Subsequent restarts: ~2–3 min.

---

## 4. Path B — Git Source (SQLite Mode)

### 4a. Push code to Git

```bash
git push origin main
```

### 4b. Create the Cloudera AI Application

1. Click **Applications → + New Application**
2. Fill in:

| Field | Value |
|---|---|
| **Name** | `Asisten Enterprise ID` |
| **Subdomain** | `asisten-enterprise` |
| **Source** | **Git Repository** |
| **Git URL** | `https://github.com/your-org/cloudera-ai-id-rag-demo` |
| **Branch** | `main` |
| **Launch Command** | `bash deployment/launch_app.sh` |
| **Runtime** | Python 3.10 or 3.11 (Standard or ML Runtime) |
| **Resource Profile** | 4 vCPU / 8 GB RAM |

### 4c. What `launch_app.sh` does on startup

```
[0/5] Load data/.env.local if it exists (written by /configure wizard)
[1/5] pip install -r requirements.txt (skipped if already done)
[2/5] Install provider-specific SDK if needed (boto3 / anthropic)
[3/5] Seed SQLite demo database (idempotent — data/sample_tables/demo.db)
[4/5] Ingest documents into FAISS vector store (skipped if index exists)
[5/5] Start uvicorn on port 8080
```

This path uses **SQLite + local filesystem** only — no MinIO, Nessie, or Trino.

---

## 5. Configure Your LLM Provider

You can set credentials in two ways:

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
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...        # or leave empty for IAM instance role
AWS_SECRET_ACCESS_KEY=...
```

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

## 6. Environment Variables

### LLM (all paths)

| Variable | Example | Notes |
|---|---|---|
| `LLM_PROVIDER` | `cloudera` | `cloudera` / `openai` / `bedrock` / `anthropic` / `local` |
| `LLM_BASE_URL` | `https://...` | Inference endpoint base URL |
| `LLM_API_KEY` | `sk-...` | API key |
| `LLM_MODEL_ID` | `meta-llama-3-8b-instruct` | Model name |

### Query engine

| Variable | Default | Description |
|---|---|---|
| `QUERY_ENGINE` | `sqlite` | `sqlite` (local dev) or `trino` (Docker/CML) |
| `TRINO_HOST` | `localhost` | Trino coordinator host |
| `TRINO_PORT` | `8085` | Trino HTTP port |
| `TRINO_CATALOG` | `iceberg` | Trino catalog name |
| `TRINO_SCHEMA` | `demo` | Trino schema name |
| `TRINO_USER` | `admin` | Trino user |

The Dockerfile sets `QUERY_ENGINE=trino` automatically. For local dev, leave unset (defaults to `sqlite`).

### Document storage

| Variable | Default | Description |
|---|---|---|
| `DOCS_STORAGE_TYPE` | `local` | `local` (dev) or `s3` (Docker/CML via MinIO) |
| `DOCS_SOURCE_PATH` | `./data/sample_docs` | Used when `DOCS_STORAGE_TYPE=local` |
| `VECTOR_STORE_PATH` | `./data/vector_store` | FAISS index directory |

### MinIO / Ozone (Docker/CML mode)

| Variable | Default | Description |
|---|---|---|
| `MINIO_ENDPOINT` | `http://localhost:9000` | S3-compatible endpoint URL |
| `MINIO_ACCESS_KEY` | `minioadmin` | S3 access key |
| `MINIO_SECRET_KEY` | `minioadmin` | S3 secret key |
| `MINIO_DOCS_BUCKET` | `rag-docs` | Bucket for source documents |
| `MINIO_WAREHOUSE_BUCKET` | `rag-warehouse` | Iceberg warehouse bucket |

For CDP production, set `MINIO_ENDPOINT` to your Ozone S3 Gateway URL and update credentials.

### SQLite (local dev mode)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/sample_tables/demo.db` | SQLAlchemy URL |
| `SQL_APPROVED_TABLES` | all 9 demo tables | Allowlist of tables the LLM can query |
| `SQL_MAX_ROWS` | `500` | Hard row cap on any query result |

### Optional tuning

| Variable | Default | Notes |
|---|---|---|
| `EMBEDDINGS_PROVIDER` | `local` | `local` or `openai` |
| `EMBEDDINGS_MODEL` | `intfloat/multilingual-e5-large` | Any sentence-transformers model |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` |
| `APP_PORT` | `8080` | **Do not change** — required by CML |

---

## 7. Resource Profiles

| Scenario | vCPU | RAM | Notes |
|---|---|---|---|
| Docker/CML (local embeddings, e5-large) | 4 | 8 GB | MinIO + Nessie + Trino + Python in one container |
| Docker/CML (OpenAI embeddings) | 2 | 4 GB | No local embeddings model |
| Git source (local embeddings, e5-large) | 4 | 8 GB | First-start model download ~1.1 GB (~3–5 min) |
| Git source (OpenAI embeddings) | 1 | 2 GB | No local model needed |

> **Why 4 vCPU / 8 GB for Docker mode?**
> Trino requires ~1.5 GB JVM heap; Nessie ~256 MB; MinIO ~128 MB;
> Python + embeddings model ~3 GB. Total minimum ~5 GB.

---

## 8. Verify the Deployment

After status changes to **Running**:

### 8a. Open the health dashboard

Navigate to `http://<app-url>/setup`. All status cards should be green:

- ✅ **Vector Store** — FAISS index built and integrity hash verified
- ✅ **Database** — tables found with row counts (Trino or SQLite)
- ✅ **LLM** — endpoint reachable and ping latency shown
- ✅ **Embeddings** — provider and model confirmed
- ✅ **Documents** — source files listed

### 8b. Test a document question

Type:
> *Jelaskan ketentuan restrukturisasi kredit berdasarkan dokumen kebijakan.*

Expected: streaming answer with source document cards.

### 8c. Test a data question

Type:
> *Berapa total outstanding pinjaman UMKM wilayah Jakarta pada Maret 2026?*

Expected: streaming answer + SQL trace panel showing the generated query and result table.

### 8d. Test the auto-play demo

Click **▶ Run Demo** in the sidebar. All sample prompts should run automatically.

### 8e. Check application logs

**Docker/CML mode** — startup should show:

```
MinIO started OK
Nessie started OK
Trino started OK
seed_iceberg: uploaded 7 documents to rag-docs
seed_iceberg: Iceberg schema + 9 tables created
seed_iceberg: seeded all tables
INFO  Startup check — vector store: OK
INFO  Startup check — database: OK (9 tables via trino)
INFO  Startup check — LLM: configured (provider=cloudera)
```

**Git source mode** — startup should show:

```
[3/5] Database: found (9 tables).
[4/5] Vector store: found at ./data/vector_store — skipping ingestion.
[5/5] Starting FastAPI server (React UI) on port 8080...
```

### 8f. Run the test suite

```bash
pytest tests/ -v
```

| Suite | Tests | Coverage |
|-------|-------|---------|
| `test_sql_guardrails.py` | 25 | SQL injection, subquery bypass, CTE, allowlist |
| `test_router.py` | 12 | LLM classification, aliases, error fallback |
| `test_retrieval.py` | 17 | Chunking, citations, mocked vector store |
| `test_api.py` | 12 | FastAPI endpoints, SSE shape, LLM provider indicators |

---

## 9. Update the Application

### Code changes (Docker path)

1. Update code; rebuild and push the image:
   ```bash
   docker build -t <registry>/cloudera-ai-id-rag-demo:latest .
   docker push <registry>/cloudera-ai-id-rag-demo:latest
   ```
2. In Applications list, click **...** → **Restart**

### Code changes (Git source path)

1. Push changes to the Git branch
2. Click **...** → **Restart** — the container pulls the latest commit and reruns `launch_app.sh`

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
3. Restart — the startup script detects the missing index and re-ingests all documents

> **Note:** Never copy a vector store from another environment without also copying
> its `index.sha256` file. A missing or mismatched hash causes the app to refuse
> loading the index.

---

## 10. Production Checklist

### Data & storage

- [ ] For Docker/CML mode: point `MINIO_ENDPOINT` to your production Ozone S3 Gateway and update credentials
- [ ] Pre-upload production documents to the `rag-docs` bucket with `banking/`, `telco/`, `government/` prefixes
- [ ] Replace `DATABASE_URL` (SQLite mode) with Trino endpoint pointing to production Iceberg tables
- [ ] Mount `VECTOR_STORE_PATH` to a persistent NFS volume so the index survives pod restarts
- [ ] Validate `SQL_APPROVED_TABLES` lists only the tables you intend to expose
- [ ] Set `TRINO_*` variables to point to your production CDW (Cloudera Data Warehouse) endpoint

### Security

- [ ] Enable SSO authentication on the Application (never use Unauthenticated with real data)
- [ ] Rotate the LLM API key and set it as a platform environment variable — locked in configure wizard
- [ ] Set `LOG_LEVEL=WARNING` to avoid logging sensitive query content
- [ ] Confirm the vector store `index.sha256` file is present after every ingestion run
- [ ] Verify outbound HTTPS from the pod is restricted to known LLM endpoints
- [ ] Restrict access to `GET /configure` and `POST /api/configure` in production

### Reliability

- [ ] Set replica count ≥ 2 for high availability
- [ ] Use `GET /health` as the orchestrator liveness/readiness probe — returns 200 OK or 503 Degraded
- [ ] Use `GET /api/status` for detailed component status (vector store hash, DB tables, LLM latency)
- [ ] Pre-build the vector store and store it on a persistent volume so startup doesn't rebuild on every start
- [ ] Mount a Docker volume for MinIO data so Iceberg tables survive container restarts (see below)

### Persistent Data Volumes (Docker mode)

By default, MinIO data and the FAISS vector store live inside the container and are lost when it stops.
Mount volumes to make them persistent:

```bash
# Run with persistent data (local Docker)
docker run -d \
  --name cloudera-rag-demo \
  -p 8080:8080 \
  -v cloudera-rag-minio:/data/minio \
  -v cloudera-rag-vectorstore:/app/data/vector_store \
  -e LLM_PROVIDER=openai \
  -e LLM_API_KEY=sk-... \
  -e LLM_MODEL_ID=gpt-4o \
  <registry>/cloudera-ai-id-rag-demo:latest
```

| Volume | Mount point inside container | What it persists |
|--------|------------------------------|-----------------|
| `cloudera-rag-minio` | `/data/minio` | MinIO object store — Iceberg tables + source documents |
| `cloudera-rag-vectorstore` | `/app/data/vector_store` | FAISS index + SHA-256 hash — skips re-ingestion on restart |

For Cloudera AI Applications, configure persistent storage via the workspace's NFS-backed storage or
set `VECTOR_STORE_PATH` to a mounted NFS share path accessible to the application pod.

---

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError` | `pip install` failed — check network access to PyPI |
| `Connection refused` on LLM URL | Wrong `LLM_BASE_URL` or endpoint not running |
| `Port already in use: 8080` | Zombie uvicorn process — restart the application |
| `integrity check FAILED` | Vector store hash mismatch — delete `data/vector_store/` and re-ingest |
| `index.sha256 not found` | Index built without hash — re-ingest to generate it |
| `SPA not found` | `app/static/index.html` missing — check repo contents and redeploy |
| Trino not ready (timeout) | First boot: Trino takes 2–4 min to start; `entrypoint.sh` waits up to 5 min (100 × 3 s) |
| `Cannot connect to Trino` at runtime | `QUERY_ENGINE=trino` but Trino not running — check Docker logs |
| LLM indicator red for Bedrock/Anthropic | No `LLM_BASE_URL` needed; status inferred from `LLM_PROVIDER` |
| `/configure` shows "From environment" but changes don't apply | Platform env vars take precedence; update in Cloudera AI Applications UI |
| Config saved but not applied after restart | Check that startup script ran step [0] and sourced `data/.env.local` |
| MinIO bucket not found | `seed_iceberg.py` failed — check logs for boto3 connection errors |

### Sidebar shows `Vector Store: Belum diingest`

The FAISS index was not built. Check:
- `DOCS_SOURCE_PATH` contains at least one `.txt`, `.pdf`, or `.docx` file (local mode)
- For Docker/CML mode: `seed_iceberg.py` ran successfully and documents were uploaded to MinIO
- `VECTOR_STORE_PATH` is writable

### LLM shows `Tidak Tersedia`

Open `/configure` and fill in LLM credentials, or set `LLM_PROVIDER`, `LLM_BASE_URL`,
`LLM_API_KEY`, `LLM_MODEL_ID` in the Cloudera AI Application environment variables and restart.

---

## 12. Environment Variable Reference

### Core

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | Yes | `cloudera` | `cloudera` / `openai` / `bedrock` / `anthropic` / `local` |
| `LLM_BASE_URL` | Most providers | — | OpenAI-compatible endpoint base URL |
| `LLM_API_KEY` | Most providers | — | API key for the LLM provider |
| `LLM_MODEL_ID` | Yes | — | Model identifier (varies by provider) |
| `EMBEDDINGS_PROVIDER` | No | `local` | `local` or `openai` |
| `EMBEDDINGS_MODEL` | No | `intfloat/multilingual-e5-large` | HuggingFace model ID |
| `VECTOR_STORE_PATH` | No | `./data/vector_store` | FAISS index directory |
| `APP_PORT` | No | `8080` | **Must stay 8080** for Cloudera AI compatibility |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

### Query engine

| Variable | Required | Default | Description |
|---|---|---|---|
| `QUERY_ENGINE` | No | `sqlite` | `sqlite` or `trino` |
| `TRINO_HOST` | If trino | `localhost` | Trino coordinator hostname |
| `TRINO_PORT` | If trino | `8085` | Trino HTTP port |
| `TRINO_CATALOG` | If trino | `iceberg` | Iceberg catalog name in Trino |
| `TRINO_SCHEMA` | If trino | `demo` | Schema within the catalog |
| `TRINO_USER` | If trino | `admin` | Trino username |

### Document / object storage

| Variable | Required | Default | Description |
|---|---|---|---|
| `DOCS_STORAGE_TYPE` | No | `local` | `local`, `hdfs`, or `s3` |
| `DOCS_SOURCE_PATH` | No | `./data/sample_docs` | Used when `DOCS_STORAGE_TYPE=local` |
| `MINIO_ENDPOINT` | If s3 | `http://localhost:9000` | S3-compatible endpoint URL |
| `MINIO_ACCESS_KEY` | If s3 | `minioadmin` | S3 access key |
| `MINIO_SECRET_KEY` | If s3 | `minioadmin` | S3 secret key |
| `MINIO_DOCS_BUCKET` | If s3 | `rag-docs` | Source documents bucket |
| `MINIO_WAREHOUSE_BUCKET` | If s3 | `rag-warehouse` | Iceberg warehouse bucket |

### SQLite (local dev)

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | No | SQLite demo | SQLAlchemy connection URL |
| `SQL_APPROVED_TABLES` | No | all 9 demo tables | Allowlist of queryable tables |
| `SQL_MAX_ROWS` | No | `500` | Max rows per query (hard cap: 1000) |

> All variables can be set via the **Cloudera AI Applications environment variables UI**
> or via the browser **`/configure` wizard** (which writes `data/.env.local`).
> Platform environment variables always take precedence over the override file.
