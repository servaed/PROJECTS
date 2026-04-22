# Deployment Guide — Cloudera AI Application (Quick Reference)

For the full deployment guide see [`DEPLOYMENT.md`](../DEPLOYMENT.md).

---

## Prerequisites

- Cloudera AI workspace with Applications access enabled
- Git repository accessible (HTTPS recommended; SSH if no HTTP proxy)
- An LLM endpoint (Cloudera AI Inference, OpenAI, Azure, Bedrock, Anthropic, or local)

---

## Step 1 — Create CML Project from Git

| Field | Value |
|---|---|
| **Source** | Git |
| **HTTPS URL** | `https://github.com/servaed/PROJECTS.git` |
| **SSH URL** | `git@github.com:servaed/PROJECTS.git` |
| **Branch** | `master` |

> SSH through HTTP proxy is not supported — use HTTPS with a PAT for private repos.

---

## Step 2 — Create the Application

Inside the project: **Applications → New Application**

| Field | Value |
|---|---|
| **Name** | `Asisten Enterprise ID` |
| **Subdomain** | `asisten-enterprise` |
| **Script** | `demos/cloudera-ai-id-rag-demo/run_app.py` |
| **Editor** | `Workbench` |
| **Kernel** | `Python 3.10` |
| **Edition** | `Standard` |
| **Resource Profile** | 4 vCPU / 8 GiB |

> **CML fact:** The Script field executes Python only — not bash.
> `run_app.py` is a Python launcher that calls `deployment/launch_app.sh` via subprocess.

---

## Step 3 — Set LLM Environment Variables

Set in the Application form or via `http://<app-url>/configure` after deploy.

**Cloudera AI Inference (recommended):**
```
LLM_PROVIDER=cloudera
LLM_BASE_URL=https://your-workspace/namespaces/serving/endpoints/your-model/v1
LLM_API_KEY=your-api-key
LLM_MODEL_ID=meta-llama-3-8b-instruct
```

**OpenAI:**
```
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL_ID=gpt-4o
```

See `DEPLOYMENT.md` Section 4 for all providers (Azure, Bedrock, Anthropic, Local).

---

## What `launch_app.sh` Does on Startup

```
[0/5] Load data/.env.local (saved credentials from /configure wizard)
[1/5] pip install -r requirements.txt (skipped after first run)
[2/5] Install provider SDK if needed (boto3 / anthropic)
[3/5] Seed Parquet files via seed_parquet.py — 9 tables, 1485 rows (idempotent)
[4/5] Build FAISS vector store (skipped if index.faiss exists)
[5/5] exec uvicorn on $CDSW_APP_PORT
```

First boot: ~3–5 min. Warm restart: ~30 s.

---

## Verify

| Check | URL |
|---|---|
| Chat interface loads | `http://<app-url>/` |
| All components green | `http://<app-url>/setup` |
| Credentials set correctly | `http://<app-url>/configure` |

---

## Key Notes

### Credentials Precedence
Application env vars > Project env vars > `data/.env.local` (/configure wizard) > code defaults.
A variable set as an Application env var appears locked in `/configure`.

### Authentication
- **SSO** (default): CML injects `Remote-user` / `Remote-user-perm` headers. App needs no auth logic.
- **Public access**: Requires admin to enable in Site Administration. Never use with real data.

### Resource Profiles
Admin pre-configures available profiles. Resources must be on a single node.

| Mode | CPU | RAM |
|---|---|---|
| Local embeddings | 4 vCPU | 8 GiB |
| OpenAI embeddings | 1 vCPU | 2 GiB |

### Demo vs Production Data Layer

| Demo (this deployment) | CDP Production equivalent |
|---|---|
| DuckDB + local Parquet files | Cloudera Data Warehouse — Trino + Iceberg on Ozone |
| Local filesystem docs | Apache Ozone (S3-compatible gateway) |
| FAISS (local) | Enterprise vector store |

Switch: `QUERY_ENGINE=trino` + `TRINO_HOST=<cdw-endpoint>`; `DOCS_STORAGE_TYPE=s3` + `MINIO_ENDPOINT=<ozone-s3gw>`.

To connect to real CDP: set `QUERY_ENGINE=trino` + `TRINO_HOST` and
`DOCS_STORAGE_TYPE=s3` + `MINIO_ENDPOINT=http://ozone-s3gw:9878`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `NameError: __file__` | Script must be `run_app.py`, not `launch_app.sh` |
| App stuck starting | First boot takes 3–5 min; check `/setup → Logs` |
| LLM indicator red | Open `/configure` → ⚡ Test LLM → fix credentials |
| `integrity check FAILED` | Delete `data/vector_store/` in Session → restart |
| SSH clone fails | Use HTTPS — SSH through HTTP proxy not supported |
