# Deployment Guide — Cloudera AI Workbench

This guide covers deploying **cloudera-ai-id-rag-demo** as a
[Cloudera AI Application](https://docs.cloudera.com/machine-learning/cloud/applications/topics/ml-applications.html)
on Cloudera AI Workbench (CML).

---

## Choose a deployment path

| | **Path A — Docker Image** | **Path B — Git Source** |
|---|---|---|
| **Entry point** | `deployment/entrypoint.sh` | `deployment/launch_app.sh` |
| **SQL engine** | Trino + Iceberg (mirrors CDW) | SQLite |
| **Document store** | MinIO (mirrors Ozone S3) | Local filesystem |
| **First boot** | ~3–5 min (Trino cold start) | ~3–5 min (embedding model download) |
| **Warm restart** | ~30 s (MinIO data persists on CML) | ~30 s |
| **Best for** | Full Cloudera presales demo | Quick iteration, no Docker registry |

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Path A — Docker Image](#2-path-a--docker-image)
3. [Path B — Git Source](#3-path-b--git-source)
4. [Configure LLM Provider](#4-configure-llm-provider)
   - [Cloudera AI Inference](#cloudera-ai-inference)
   - [OpenAI](#openai)
   - [Azure OpenAI](#azure-openai)
   - [Amazon Bedrock](#amazon-bedrock)
   - [Anthropic](#anthropic)
   - [Local / Ollama / vLLM](#local--ollama--vllm)
5. [Startup Timeline](#5-startup-timeline)
6. [Verify the Deployment](#6-verify-the-deployment)
7. [Update the Application](#7-update-the-application)
8. [Resource Profiles](#8-resource-profiles)
9. [Production Checklist](#9-production-checklist)
10. [Troubleshooting](#10-troubleshooting)
11. [Environment Variable Reference](#11-environment-variable-reference)

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Cloudera AI Workbench workspace | Admin or Project Creator role |
| Applications feature enabled | Site Administration → Applications; contact admin if missing |
| LLM endpoint | One of: Cloudera AI Inference, OpenAI, Azure OpenAI, Bedrock, Anthropic, Ollama |
| Docker registry (Path A only) | GHCR, Harbor, ECR, Docker Hub — reachable from the workspace |
| Git repository (Path B only) | GitHub, GitLab, Bitbucket — reachable from workspace network |

### Minimum resource profile

| Mode | vCPU | RAM |
|---|---|---|
| Docker image (local embeddings) | 4 | 8 GB |
| Docker image (OpenAI embeddings) | 2 | 4 GB |
| Git source (local embeddings) | 4 | 8 GB |
| Git source (OpenAI embeddings) | 1 | 2 GB |

> **Why so much RAM?** Trino JVM ~1.5 GB + Nessie ~256 MB + MinIO ~128 MB + Python + multilingual-e5-large ~3 GB ≈ 5 GB minimum.

---

## 2. Path A — Docker Image

### 2a. Build the image

**Option 1 — GitHub Actions (automatic, recommended)**

The repo includes `.github/workflows/docker-build.yml`. On every push to `master`/`main`
or a semver tag (`v*.*.*`) that touches `demos/cloudera-ai-id-rag-demo/**`, it:
- Builds the multi-stage image
- Pushes to GHCR: `ghcr.io/servaed/cloudera-ai-id-rag-demo`
- Tags: `:master`, `:latest`, `:sha-<short>`, `:1.2.3` (on semver tags)
- Caches layers in GHCR `buildcache` tag — subsequent builds take ~2 min

No manual push required. Check progress at the **Actions** tab on GitHub.

**Option 2 — Makefile (local build + push)**

```bash
cd demos/cloudera-ai-id-rag-demo

# Build
make docker REGISTRY=ghcr.io/servaed TAG=latest

# Authenticate to GHCR with a Personal Access Token (write:packages scope)
echo $GITHUB_PAT | docker login ghcr.io -u servaed --password-stdin

# Push
make docker-push REGISTRY=ghcr.io/servaed TAG=latest
```

**Option 3 — Docker directly**

```bash
docker build -t ghcr.io/servaed/cloudera-ai-id-rag-demo:latest \
  -f demos/cloudera-ai-id-rag-demo/Dockerfile \
  demos/cloudera-ai-id-rag-demo/

docker push ghcr.io/servaed/cloudera-ai-id-rag-demo:latest
```

Build time: ~5–10 min first time (downloads MinIO, Nessie 0.83.2 JAR, Trino 455 tarball — ~800 MB total).

### 2b. Test locally before deploying to CML

```bash
# Easiest — docker compose with named volumes
cp demos/cloudera-ai-id-rag-demo/.env.example demos/cloudera-ai-id-rag-demo/.env
# Edit .env: set LLM_PROVIDER, LLM_API_KEY, etc.
cd demos/cloudera-ai-id-rag-demo
docker compose up
```

Open **http://localhost:8080/setup** — all cards should turn green within 3–5 min.

### 2c. Create the CML Application

**Option 1 — API script (one command)**

```bash
cd demos/cloudera-ai-id-rag-demo

# List projects to find your project ID
python deployment/deploy_cml_app.py \
  --cml-url https://ml-xxxx.cloudera.com \
  --api-key $CDSW_API_KEY \
  --list-projects

# Deploy (swap provider flags — see Section 4 for all providers)
python deployment/deploy_cml_app.py \
  --cml-url https://ml-xxxx.cloudera.com \
  --project-id <project-id> \
  --api-key $CDSW_API_KEY \
  --image ghcr.io/servaed/cloudera-ai-id-rag-demo:latest \
  --llm-provider azure \
  --azure-endpoint https://your-resource.openai.azure.com/ \
  --azure-api-key <key> \
  --azure-deployment gpt-4o
```

The script polls until status is **Running**, then prints the app URL.

**Option 2 — CML UI (manual)**

1. **Applications → + New Application**
2. Fill in the form:

| Field | Value |
|---|---|
| **Name** | `Asisten Enterprise ID` |
| **Subdomain** | `asisten-enterprise` |
| **Source** | **Docker Image** |
| **Image URL** | `ghcr.io/servaed/cloudera-ai-id-rag-demo:latest` |
| **Resource Profile** | 4 vCPU / 8 GB RAM |
| **Authentication** | SSO (recommended) or Unauthenticated for open demos |

3. Add LLM environment variables (see [Section 4](#4-configure-llm-provider))
4. **Deploy Application**

### 2d. What happens on startup

```
t=0s    uvicorn starts on :8080 → CML shows "Running" immediately
        (users can open /setup and watch progress live)

t=2s    [1/5] MinIO starts at :9000 — data at /home/cdsw/.minio-data
              (persistent on CML project filesystem, survives restarts)

t=15s   [2/5] Nessie starts at :19120

t=30s   [3/5] Trino starts at :8085
              First boot: JVM cold start takes 2–4 min
              Warm restart: Trino restarts in ~30 s

t~3min  [4/5] seed_iceberg.py runs:
              First boot:  CREATE SCHEMA + 9 Iceberg tables + upload 7 docs
              Warm restart: skipped (sentinel /home/cdsw/.minio-seeded exists)

t~4min  [5/5] FAISS vector store built from MinIO documents
              (skipped on warm restart if index.faiss already exists)

t~4min  /tmp/.cml_services_ready written
              → /api/chat opens for queries
              → /setup shows all cards green
```

> **Warm restart time:** After the first boot, MinIO data persists on the CML project
> filesystem at `/home/cdsw/.minio-data`. Seeding and vector store are both skipped.
> The app is fully ready in ~30 s instead of 3–5 min.
>
> To force a full re-seed (e.g., after replacing documents):
> ```bash
> rm /home/cdsw/.minio-seeded       # in a CML Session terminal
> rm -rf /home/cdsw/.minio-data     # to also wipe object storage
> ```
> Then restart the Application.

---

## 3. Path B — Git Source

This path uses **SQLite + local filesystem** — no MinIO, Nessie, or Trino required.
Ideal for quick demos when a Docker registry is not available.

### 3a. Ensure cdsw-build.sh is present

The repo includes `cdsw-build.sh` in the project root. CML runs this file automatically
when the project is first synced from Git. It pre-installs Python dependencies and
downloads the multilingual-e5-large embedding model (~500 MB) so Application boots
are faster (no pip install at startup).

No action needed — it runs automatically on first project load.

### 3b. Create the CML Application

**Option 1 — API script**

```bash
python deployment/deploy_cml_app.py \
  --cml-url https://ml-xxxx.cloudera.com \
  --project-id <project-id> \
  --api-key $CDSW_API_KEY \
  --git-source \
  --llm-provider openai \
  --llm-api-key sk-... \
  --llm-model-id gpt-4o
```

**Option 2 — CML UI**

| Field | Value |
|---|---|
| **Source** | **Git Repository** |
| **Git URL** | `https://github.com/servaed/PROJECTS` |
| **Branch** | `master` |
| **Subdirectory** | `demos/cloudera-ai-id-rag-demo` *(if supported by your CML version)* |
| **Launch Command** | `bash deployment/launch_app.sh` |
| **Runtime** | Python 3.10 or 3.11 (Standard Runtime) |
| **Resource Profile** | 4 vCPU / 8 GB RAM |

Add LLM environment variables (see [Section 4](#4-configure-llm-provider)), then **Deploy**.

### 3c. What happens on startup

```
[0/5] Source data/.env.local (written by /configure wizard on previous runs)
[1/5] pip install -r requirements.txt  (skipped after cdsw-build.sh runs)
[2/5] Install provider-specific SDK if needed (boto3 for Bedrock, anthropic package)
[3/5] Seed SQLite demo.db — 9 tables, 148+ rows (idempotent)
[4/5] Build FAISS vector store (skipped if data/vector_store/index.faiss exists)
[5/5] exec uvicorn app.api:app --host 0.0.0.0 --port 8080
```

---

## 4. Configure LLM Provider

There are **three ways** to set credentials — pick one per deployment:

| Method | When to use |
|---|---|
| **A — CML platform env vars** | Before first deploy; credentials set in the Applications UI |
| **B — deploy_cml_app.py flags** | One-command deploy with credentials baked in |
| **C — /configure browser wizard** | After deploy, without shell access; values persist in `data/.env.local` |

> **Precedence:** Platform env vars (Method A) > `data/.env.local` (Method C) > code defaults.
> A variable set via Method A cannot be overridden by Method C — it shows as locked
> ("From environment") in the configure wizard.

---

### Cloudera AI Inference

The recommended provider for Cloudera presales — uses your workspace's built-in
AI Inference service. Find the endpoint URL and key in
**CML Workspace → AI Inference → your model → Endpoint Details**.

**Method A — CML platform environment variables**

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `cloudera` |
| `LLM_BASE_URL` | `https://ml-xxxx.cloudera.com/namespaces/serving/endpoints/your-model/v1` |
| `LLM_API_KEY` | *(key from endpoint detail page)* |
| `LLM_MODEL_ID` | `meta-llama-3-8b-instruct` |

**Method B — deploy_cml_app.py**

```bash
python deployment/deploy_cml_app.py \
  --cml-url https://ml-xxxx.cloudera.com \
  --project-id <id> \
  --image ghcr.io/servaed/cloudera-ai-id-rag-demo:latest \
  --llm-provider cloudera \
  --llm-base-url https://ml-xxxx.cloudera.com/namespaces/serving/endpoints/your-model/v1 \
  --llm-api-key <key> \
  --llm-model-id meta-llama-3-8b-instruct
```

**Method C — /configure wizard**

Open `http://<app-url>/configure` → select **Cloudera AI** → fill in:
- Endpoint URL → saves as `LLM_BASE_URL`
- API Key → saves as `LLM_API_KEY`
- Model ID → saves as `LLM_MODEL_ID`

Click **Save Configuration** then restart.

---

### OpenAI

**Method A — CML platform environment variables**

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `openai` |
| `LLM_API_KEY` | `sk-proj-...` |
| `LLM_MODEL_ID` | `gpt-4o` (or `gpt-4o-mini`, `gpt-4.1`, `o3-mini`) |

`LLM_BASE_URL` is not needed — the app defaults to `https://api.openai.com/v1`.

**Method B — deploy_cml_app.py**

```bash
python deployment/deploy_cml_app.py \
  --cml-url https://ml-xxxx.cloudera.com \
  --project-id <id> \
  --image ghcr.io/servaed/cloudera-ai-id-rag-demo:latest \
  --llm-provider openai \
  --llm-api-key sk-proj-... \
  --llm-model-id gpt-4o
```

**Method C — /configure wizard**

Select **OpenAI** → fill in API Key and Model ID. Base URL auto-fills.

---

### Azure OpenAI

Azure requires its own endpoint, key, and deployment name — **different from the generic OpenAI variables**.

**Method A — CML platform environment variables**

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `azure` |
| `AZURE_OPENAI_ENDPOINT` | `https://your-resource.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | *(key from Azure portal → Keys and Endpoint)* |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` *(your deployment name, not the model name)* |
| `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` *(or latest stable)* |

> **Note:** Do **not** use `LLM_BASE_URL` / `LLM_API_KEY` for Azure — the app reads the
> `AZURE_OPENAI_*` variables directly when `LLM_PROVIDER=azure`.

**Method B — deploy_cml_app.py**

```bash
python deployment/deploy_cml_app.py \
  --cml-url https://ml-xxxx.cloudera.com \
  --project-id <id> \
  --image ghcr.io/servaed/cloudera-ai-id-rag-demo:latest \
  --llm-provider azure \
  --azure-endpoint https://your-resource.openai.azure.com/ \
  --azure-api-key <key> \
  --azure-deployment gpt-4o \
  --azure-api-version 2024-12-01-preview
```

**Method C — /configure wizard**

Select **Azure OpenAI** → fill in Endpoint URL, API Key, Deployment Name, and API Version.

**Available Azure models** (deployment names must match what you created in Azure portal):

| Azure model | Deployment name example |
|---|---|
| GPT-4o | `gpt-4o` |
| GPT-4.1 | `gpt-4.1` |
| GPT-4o mini | `gpt-4o-mini` |
| o3-mini | `o3-mini` |

---

### Amazon Bedrock

Bedrock uses AWS credentials — no base URL or API key required. The app calls the
**Bedrock Converse API** which works with all listed models.

**Method A — CML platform environment variables**

*Option 1 — IAM user credentials:*

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `bedrock` |
| `LLM_MODEL_ID` | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| `AWS_DEFAULT_REGION` | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | `...` |

*Option 2 — IAM instance role (no credentials in env):*

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `bedrock` |
| `LLM_MODEL_ID` | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| `AWS_DEFAULT_REGION` | `us-east-1` |

*(AWS SDK picks up the instance role automatically — no key/secret needed.)*

*Option 3 — STS temporary credentials:*

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `bedrock` |
| `LLM_MODEL_ID` | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| `AWS_DEFAULT_REGION` | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | `ASIA...` |
| `AWS_SECRET_ACCESS_KEY` | `...` |
| `AWS_SESSION_TOKEN` | `...` |

**Method B — deploy_cml_app.py**

```bash
python deployment/deploy_cml_app.py \
  --cml-url https://ml-xxxx.cloudera.com \
  --project-id <id> \
  --image ghcr.io/servaed/cloudera-ai-id-rag-demo:latest \
  --llm-provider bedrock \
  --llm-model-id anthropic.claude-3-5-sonnet-20241022-v2:0
# Add --llm-api-key and AWS_ vars via CML platform UI after deploy
# (avoid passing AWS credentials as CLI args)
```

**Method C — /configure wizard**

Select **Amazon Bedrock** → fill in Region and Model ID. Set AWS credentials via
CML platform UI (not via /configure — keep secrets out of `data/.env.local`).

**Supported Bedrock model IDs:**

| Family | Model ID |
|---|---|
| Anthropic Claude 3.5 Sonnet | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| Anthropic Claude 3.5 Haiku | `anthropic.claude-3-5-haiku-20241022-v1:0` |
| Anthropic Claude 3 Sonnet | `anthropic.claude-3-sonnet-20240229-v1:0` |
| Meta Llama 3.1 70B | `meta.llama3-1-70b-instruct-v1:0` |
| Meta Llama 3.1 8B | `meta.llama3-1-8b-instruct-v1:0` |
| Amazon Titan Text G1 | `amazon.titan-text-express-v1` |
| Mistral Large | `mistral.mistral-large-2402-v1:0` |

Model must be enabled in your AWS account (Bedrock → Model Access).

---

### Anthropic

Direct API — no base URL required. The app uses the `anthropic` Python SDK.

**Method A — CML platform environment variables**

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `anthropic` |
| `LLM_API_KEY` | `sk-ant-api03-...` |
| `LLM_MODEL_ID` | `claude-sonnet-4-6` |

**Method B — deploy_cml_app.py**

```bash
python deployment/deploy_cml_app.py \
  --cml-url https://ml-xxxx.cloudera.com \
  --project-id <id> \
  --image ghcr.io/servaed/cloudera-ai-id-rag-demo:latest \
  --llm-provider anthropic \
  --llm-api-key sk-ant-api03-... \
  --llm-model-id claude-sonnet-4-6
```

**Method C — /configure wizard**

Select **Anthropic** → fill in API Key and Model ID.

**Available Anthropic model IDs:**

| Model | ID |
|---|---|
| Claude Sonnet 4.6 (latest) | `claude-sonnet-4-6` |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` |
| Claude Opus 4.7 | `claude-opus-4-7` |
| Claude 3.5 Sonnet | `claude-3-5-sonnet-20241022` |
| Claude 3.5 Haiku | `claude-3-5-haiku-20241022` |

---

### Local / Ollama / vLLM

Use any OpenAI-compatible local server. The app sends requests to `LLM_BASE_URL/chat/completions`.

**Method A — CML platform environment variables**

*Ollama (running on the same host or accessible host):*

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `local` |
| `LLM_BASE_URL` | `http://host.docker.internal:11434/v1` |
| `LLM_MODEL_ID` | `llama3.2` |
| `LLM_API_KEY` | `no-key` *(Ollama ignores this)* |

*vLLM:*

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `local` |
| `LLM_BASE_URL` | `http://your-vllm-host:8000/v1` |
| `LLM_MODEL_ID` | `meta-llama/Llama-3.1-8B-Instruct` |
| `LLM_API_KEY` | `no-key` |

*LM Studio:*

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `local` |
| `LLM_BASE_URL` | `http://localhost:1234/v1` |
| `LLM_MODEL_ID` | `lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF` |
| `LLM_API_KEY` | `no-key` |

**Method B — deploy_cml_app.py**

```bash
python deployment/deploy_cml_app.py \
  --cml-url https://ml-xxxx.cloudera.com \
  --project-id <id> \
  --image ghcr.io/servaed/cloudera-ai-id-rag-demo:latest \
  --llm-provider local \
  --llm-base-url http://your-ollama-host:11434/v1 \
  --llm-model-id llama3.2 \
  --llm-api-key no-key
```

**Method C — /configure wizard**

Select **Local** → fill in Base URL and Model ID.

---

## 5. Startup Timeline

Understanding startup helps interpret the `/setup` page and CML logs.

### Path A — Docker image (first boot)

```
 0:00  uvicorn binds :8080 → CML Application shows "Running"
       /setup banner shows "Waiting for: Trino / MinIO / Nessie..."
 0:02  MinIO starts at :9000 (data dir /home/cdsw/.minio-data created)
 0:15  Nessie starts at :19120
 0:30  Trino JVM begins loading (~800 MB, takes 2–4 min)
 3:00  Trino passes health check at /v1/info
 3:10  seed_iceberg.py: buckets created, 7 docs uploaded, 9 Iceberg tables seeded
       sentinel written to /home/cdsw/.minio-seeded
 3:30  FAISS vector store built from MinIO documents (embedding model already cached)
 3:35  /tmp/.cml_services_ready written
       /setup banner disappears, all cards turn green
       /api/chat accepts queries
```

### Path A — Docker image (warm restart, CML only)

```
 0:00  uvicorn binds :8080 → CML Application shows "Running"
 0:02  MinIO restarts (data at /home/cdsw/.minio-data — already populated)
 0:15  Nessie restarts
 0:30  Trino restarts (JVM still cached in OS, starts faster)
 2:00  Trino passes health check
 2:05  seed_iceberg.py: sentinel exists → SKIPPED
 2:05  FAISS index exists → SKIPPED
 2:05  /tmp/.cml_services_ready written → fully ready
```

### Path B — Git source (first boot, after cdsw-build.sh)

```
 0:00  launch_app.sh starts
 0:01  pip install: already done by cdsw-build.sh → ~2 s
 0:05  SQLite demo.db seeded (idempotent)
 0:10  FAISS index exists → skipped  (or ~3 min if first time)
 0:12  uvicorn binds :8080 → CML Application shows "Running"
```

---

## 6. Verify the Deployment

### 6a. Health dashboard

Navigate to `http://<app-url>/setup`. All status cards must be green:

- ✅ **Vector Store** — FAISS index present and SHA-256 hash verified
- ✅ **Database** — 9 tables found with row counts (Trino or SQLite)
- ✅ **LLM** — endpoint reachable, ping latency shown
- ✅ **Embeddings** — provider and model ID confirmed
- ✅ **Documents** — source files listed

In Docker/CML mode, also check: ✅ **Services Ready** (Trino stack fully started).

Use the **⚡ Test LLM** button on `/configure` to verify credentials without a full chat round-trip.

### 6b. Test with sample questions

**Document retrieval (RAG):**
> *Jelaskan ketentuan restrukturisasi kredit berdasarkan dokumen kebijakan.*

Expected: streaming Indonesian answer with source document citation cards.

**SQL query:**
> *Berapa total outstanding pinjaman UMKM wilayah Jakarta pada Maret 2026?*

Expected: answer + SQL trace panel + result table + bar chart.

**Combined (gabungan):**
> *Apakah utilisasi jaringan di Bali sudah melampaui ambang SLA yang berlaku?*

Expected: answer merges retrieved policy chunk + live query result.

**English mode** (toggle language in sidebar):
> *Show the top 5 UMKM borrowers by outstanding balance.*

### 6c. Run the auto-play demo

Click **▶ Run Demo** in the sidebar. All sample prompts should play automatically.
Use **⏸ Pause** to pause for Q&A, **↺ Reset Demo** to restart from scratch.

### 6d. Check logs

Open `/setup → Logs` to see the last 200 log lines from the running process.

Expected on successful startup:
```
[startup] MinIO is ready.
[startup] Nessie is ready.
[startup] Trino is ready.
[seed]    Data already present — skipping seed (warm restart)
[startup] All services ready. Signalling uvicorn...
INFO  Startup - LLM warm-up: OK (model cache primed)
INFO  Startup check — vector store: OK
INFO  Startup check — database: OK (9 tables via trino)
INFO  Startup check — LLM: configured (provider=azure)
```

---

## 7. Update the Application

### Code change — Docker path

```bash
# Push code; GitHub Actions builds and pushes automatically
git push origin master

# OR build and push manually
make docker-push REGISTRY=ghcr.io/servaed TAG=latest

# Then restart in CML:
python deployment/deploy_cml_app.py \
  --cml-url https://ml-xxxx.cloudera.com \
  --project-id <id> \
  --image ghcr.io/servaed/cloudera-ai-id-rag-demo:latest \
  --update-existing
# OR: CML UI → Application → ⋯ → Restart
```

### Code change — Git source path

```bash
git push origin master
# CML UI → Application → ⋯ → Restart
# CML pulls the latest commit and reruns launch_app.sh
```

### Credential change only

```bash
# No restart needed for /configure changes:
# 1. Open http://<app-url>/configure
# 2. Update credentials → Save Configuration
# 3. CML UI → Restart (to apply to already-running process)
# OR use the platform UI for the env var if it was set there
```

### Force re-ingestion (new documents added)

```bash
# Docker/CML mode — in a CML Session terminal:
rm /home/cdsw/.minio-seeded          # removes seed sentinel
rm -rf data/vector_store/            # removes FAISS index
# Then restart Application — seed + ingest both run

# Git source mode:
rm -rf data/vector_store/
# Restart Application
```

---

## 8. Resource Profiles

| Deployment | vCPU | RAM | Notes |
|---|---|---|---|
| Docker — local embeddings (e5-large) | **4** | **8 GB** | MinIO + Nessie + Trino + Python |
| Docker — OpenAI embeddings | **2** | **4 GB** | No local model; set `EMBEDDINGS_PROVIDER=openai` |
| Git source — local embeddings | **4** | **8 GB** | Model download ~500 MB on first boot |
| Git source — OpenAI embeddings | **1** | **2 GB** | Lightest possible footprint |

**Embeddings with OpenAI** (`EMBEDDINGS_PROVIDER=openai`): set `OPENAI_API_KEY` and optionally
`EMBEDDINGS_MODEL=text-embedding-3-large`. Reduces RAM by ~3 GB but adds API cost per query.

---

## 9. Production Checklist

### Before go-live

- [ ] Set `LLM_PROVIDER` and credentials via **CML platform env vars** (not `/configure`) — so they are locked and cannot be changed from the browser
- [ ] `SQL_APPROVED_TABLES` lists only the tables you intend to expose to LLM queries
- [ ] `LOG_LEVEL=WARNING` — avoids logging query content and user messages
- [ ] SSO authentication enabled on the Application (never `Unauthenticated` with real data)
- [ ] Verify `GET /health` returns `{"status":"ok"}` — use as the liveness probe URL

### Data

- [ ] Replace demo SQLite / MinIO data with production Iceberg tables on CDW:
  set `QUERY_ENGINE=trino`, `TRINO_HOST=<cdw-endpoint>`, `TRINO_PORT`, `TRINO_CATALOG`, `TRINO_SCHEMA`
- [ ] Replace demo documents with production docs in the `rag-docs` bucket (or Ozone):
  set `DOCS_STORAGE_TYPE=s3`, `MINIO_ENDPOINT=http://ozone-s3gw:9878`
- [ ] Verify `VECTOR_STORE_PATH` is on a persistent NFS share so the index survives pod restarts
- [ ] Confirm `index.sha256` is present after every ingestion run (integrity gate)

### Security

- [ ] Rotate LLM API keys before sharing the app URL
- [ ] Verify outbound HTTPS from the pod is restricted to known LLM endpoints only
- [ ] For Bedrock: prefer IAM instance role over static `AWS_ACCESS_KEY_ID`
- [ ] `/configure` route should be access-controlled in production (use SSO)

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| App shows "Starting" for >10 min | Trino cold start taking longer than expected | Check `/setup → Logs` for Trino errors; ensure 4 vCPU / 8 GB |
| Chat shows "Layanan data sedang disiapkan" | `/tmp/.cml_services_ready` not yet written | Wait for Trino to finish; watch `/setup` for status |
| `/setup` shows Services Ready: ✗ | Trino stack failed to start | Check `/setup → Logs` for startup errors; restart |
| `ModuleNotFoundError` on startup | pip install failed | Check network access to PyPI; verify `requirements.txt` |
| `Connection refused` for LLM | Wrong `LLM_BASE_URL` | Open `/configure` → ⚡ Test LLM → fix URL |
| LLM shows red — Bedrock / Anthropic | `LLM_BASE_URL` not needed — normal | Status derives from `LLM_PROVIDER`; check credentials |
| Azure LLM test returns 404 | Using `LLM_BASE_URL` instead of `AZURE_OPENAI_ENDPOINT` | Set `AZURE_OPENAI_ENDPOINT` (see Azure section) |
| `/configure` field shows "From environment" but is wrong | Platform env var takes precedence | Update via **CML Applications UI** → env vars → restart |
| `integrity check FAILED` on vector store | `index.sha256` mismatch | Delete `data/vector_store/` and let it rebuild |
| MinIO bucket missing | `seed_iceberg.py` failed on first boot | Check `/setup → Logs` for boto3 errors; restart |
| Warm restart still re-seeds | Sentinel `/home/cdsw/.minio-seeded` was deleted | Expected — re-seed runs once, writes sentinel |
| `SQL_APPROVED_TABLES` blocking valid query | Table not in the allowlist | Add table name to `SQL_APPROVED_TABLES` env var |
| `git source` app takes 3–5 min to start | Embedding model not pre-cached | `cdsw-build.sh` runs once on project sync; subsequent boots are faster |
| `deploy_cml_app.py` returns 401 | API key invalid or expired | Generate a new key at `<cml-url>/user/<username>/api-keys` |
| `deploy_cml_app.py` returns 404 on application | Wrong `--project-id` | Run `--list-projects` to find the correct ID |

---

## 11. Environment Variable Reference

> Variables can be set via:
> - **CML platform UI** (Applications → environment variables) — takes highest precedence, locks field in `/configure`
> - **`/configure` browser wizard** — writes to `data/.env.local`; survives restarts
> - **`.env` file** (local dev only) — loaded by `launch_app.sh` at step 0

### LLM — common (all providers)

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | Yes | `cloudera` / `openai` / `azure` / `bedrock` / `anthropic` / `local` |
| `LLM_BASE_URL` | Most | OpenAI-compatible endpoint URL (not needed for Bedrock / Anthropic) |
| `LLM_API_KEY` | Most | API key (not needed for Bedrock with IAM role) |
| `LLM_MODEL_ID` | Yes | Model or deployment name |

### LLM — Cloudera AI Inference

| Variable | Required | Default | Description |
|---|---|---|---|
| `CLOUDERA_INFERENCE_URL` | If no `LLM_BASE_URL` | — | Full inference endpoint URL |
| `CLOUDERA_INFERENCE_API_KEY` | If no `LLM_API_KEY` | — | Endpoint API key |
| `CLOUDERA_INFERENCE_MODEL_ID` | If no `LLM_MODEL_ID` | `meta-llama-3-8b-instruct` | Model name |

### LLM — Azure OpenAI

| Variable | Required | Default | Description |
|---|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | Yes | — | `https://your-resource.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Yes | — | Azure API key |
| `AZURE_OPENAI_DEPLOYMENT` | Yes | `gpt-4o` | Deployment name (not model name) |
| `AZURE_OPENAI_API_VERSION` | No | `2024-02-01` | API version string |

### LLM — Amazon Bedrock

| Variable | Required | Default | Description |
|---|---|---|---|
| `BEDROCK_MODEL_ID` or `LLM_MODEL_ID` | Yes | `anthropic.claude-3-sonnet...` | Bedrock model ID |
| `AWS_DEFAULT_REGION` | Yes | `us-east-1` | AWS region where model is enabled |
| `AWS_ACCESS_KEY_ID` | No | — | IAM user key; omit to use instance role |
| `AWS_SECRET_ACCESS_KEY` | No | — | IAM user secret |
| `AWS_SESSION_TOKEN` | No | — | STS temporary session token |

### LLM — Anthropic

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` or `LLM_API_KEY` | Yes | — | `sk-ant-...` key |
| `ANTHROPIC_MODEL_ID` or `LLM_MODEL_ID` | No | `claude-3-5-sonnet-20241022` | Claude model ID |

### LLM — Local

| Variable | Required | Default | Description |
|---|---|---|---|
| `LOCAL_LLM_URL` or `LLM_BASE_URL` | Yes | `http://localhost:11434/v1` | Local server base URL |
| `LOCAL_LLM_MODEL_ID` or `LLM_MODEL_ID` | No | `llama3` | Model name on the local server |
| `LOCAL_LLM_API_KEY` or `LLM_API_KEY` | No | `no-key` | Most local servers ignore this |

### Embeddings

| Variable | Required | Default | Description |
|---|---|---|---|
| `EMBEDDINGS_PROVIDER` | No | `local` | `local` (sentence-transformers) or `openai` |
| `EMBEDDINGS_MODEL` | No | `intfloat/multilingual-e5-large` | HuggingFace model ID or OpenAI model |

### Vector store

| Variable | Required | Default | Description |
|---|---|---|---|
| `VECTOR_STORE_PATH` | No | `./data/vector_store` | Directory for FAISS index + SHA-256 hash |

### Query engine

| Variable | Required | Default | Description |
|---|---|---|---|
| `QUERY_ENGINE` | No | `sqlite` | `sqlite` (local dev) or `trino` (Docker/CML) |
| `TRINO_HOST` | If trino | `localhost` | Trino coordinator hostname |
| `TRINO_PORT` | If trino | `8085` | Trino HTTP port |
| `TRINO_CATALOG` | If trino | `iceberg` | Catalog name |
| `TRINO_SCHEMA` | If trino | `demo` | Schema within the catalog |
| `TRINO_USER` | If trino | `admin` | Trino username |
| `DATABASE_URL` | If sqlite | `sqlite:///./data/sample_tables/demo.db` | SQLAlchemy connection URL |
| `SQL_APPROVED_TABLES` | No | 9 demo tables | Comma-separated table allowlist for LLM |
| `SQL_MAX_ROWS` | No | `500` | Max rows per query result (hard cap: 1000) |

### Document / object storage

| Variable | Required | Default | Description |
|---|---|---|---|
| `DOCS_STORAGE_TYPE` | No | `local` | `local`, `s3`, or `hdfs` |
| `DOCS_SOURCE_PATH` | No | `./data/sample_docs` | Used when `DOCS_STORAGE_TYPE=local` |
| `MINIO_ENDPOINT` | If s3 | `http://localhost:9000` | S3-compatible endpoint |
| `MINIO_ACCESS_KEY` | If s3 | `minioadmin` | S3 access key |
| `MINIO_SECRET_KEY` | If s3 | `minioadmin` | S3 secret key |
| `MINIO_DOCS_BUCKET` | If s3 | `rag-docs` | Source documents bucket |
| `MINIO_WAREHOUSE_BUCKET` | If s3 | `rag-warehouse` | Iceberg warehouse bucket |

### Application

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_PORT` | No | `8080` | **Must be 8080** — required by Cloudera AI Applications |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
