---
name: app-deploy
description: Steps for preparing and validating deployment as a Cloudera AI Application. Covers both Docker image path (MinIO+Nessie+Trino) and Git source path (SQLite), env vars, configure wizard, and startup scripts.
---

# Skill: App Deployment

## Pre-Deployment Checklist

- [ ] `APP_PORT=8080` is set (or left as default)
- [ ] LLM credentials set via platform env vars **or** saved via `/configure` wizard
- [ ] `SQL_APPROVED_TABLES` is set to only the tables needed for the demo
- [ ] No credentials in version control (`.env` and `data/.env.local` are in `.gitignore`)
- [ ] `requirements.txt` is up to date
- [ ] All tests pass: `pytest tests/ -v`
- [ ] **Docker path**: image builds cleanly (`docker build -t ... .`)
- [ ] **Git path**: `deployment/launch_app.sh` is executable and tested locally

## Two Deployment Paths

### Path A — Docker Image (recommended for full Cloudera demo)

```bash
# Build (5-10 min first time — downloads MinIO, Nessie, Trino)
docker build -t <registry>/cloudera-ai-id-rag-demo:latest .
docker push <registry>/cloudera-ai-id-rag-demo:latest

# Local test
docker run --rm -p 8080:8080 \
  -e LLM_PROVIDER=openai \
  -e LLM_API_KEY=sk-... \
  -e LLM_MODEL_ID=gpt-4o \
  <registry>/cloudera-ai-id-rag-demo:latest
```

In Cloudera AI: Source = **Docker Image**, Image URL = registry path.
Entry point is `deployment/entrypoint.sh` (set in Dockerfile CMD).

### Path B — Git Source (lightweight, SQLite only)

In Cloudera AI: Source = **Git Repository**, Launch Command = `bash deployment/launch_app.sh`.
Uses SQLite + local filesystem. No Java services.

## Local Validation

```bash
# Option A: Docker
docker run --rm -p 8080:8080 -e LLM_PROVIDER=... <image>
# Option B: local Python
uvicorn app.api:app --host 0.0.0.0 --port 8080 --reload

# Validate:
# 1. http://localhost:8080        — React SPA loads
# 2. http://localhost:8080/setup  — all component cards green
# 3. http://localhost:8080/configure — credentials form loads
# 4. Submit a test question       — streaming response with source citations
# 5. Click ▶ Run Demo             — auto-play walks through all sample prompts
# 6. GET /api/status              — returns ok for vector_store, database, llm
```

## Credential Configuration Options

### Option A — Cloudera AI platform UI (before or after deploy)
Set `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_ID` in the
Environment Variables section of the Application config.

### Option B — /configure wizard (after deploy, no shell access needed)
1. Open `http://<app-url>/configure`
2. Select provider, fill in credentials, click **Save Configuration**
3. Restart from Cloudera AI Applications UI

Platform env vars always take precedence over `/configure` wizard values.

## What entrypoint.sh Does (Docker/CML mode)

```
[1/6] Start MinIO on :9000       wait for health check
[2/6] Start Nessie on :19120     wait for health check
[3/6] Start Trino on :8085       wait for health check (up to 5 min)
[4/6] Run seed_iceberg.py        create buckets + upload docs + seed 9 Iceberg tables
[5/6] Build FAISS vector store   (skipped if index already exists)
[6/6] exec uvicorn on port $PORT
```

## What launch_app.sh Does (Git source / local dev mode)

```
[0/5] Source data/.env.local if it exists (written by /configure wizard)
[1/5] pip install -r requirements.txt (skipped after first run)
[2/5] Install provider-specific SDK if needed (boto3 / anthropic)
[3/5] Seed demo SQLite database (idempotent)
[4/5] Ingest documents into FAISS vector store (skipped if index exists)
[5/5] Start uvicorn on port 8080
```

## Cloudera AI Applications Deployment Steps (Docker Image)

1. Build and push Docker image to registry
2. Open Cloudera AI → Applications → New Application
3. Set **Source** to **Docker Image**, enter image URL
4. Set LLM env vars (or skip and use `/configure` after deploy)
5. Select resource profile: 4 vCPU / 8 GB RAM (MinIO + Nessie + Trino + Python)
6. Set auth: SSO for production, Unauthenticated for demo only
7. Click Deploy and wait for status → Running (~5–15 min first boot)
8. Verify at `/setup` — all status cards should be green

## Cloudera AI Applications Deployment Steps (Git Source)

1. Push repo to Git (GitHub, GitLab, Bitbucket)
2. Open Cloudera AI → Applications → New Application
3. Set **Source** to Git, enter repo URL and branch
4. Set **Launch Command**: `bash deployment/launch_app.sh`
5. Set LLM env vars; select 4 vCPU / 8 GB for local embeddings
6. Click Deploy and wait for status → Running (first boot: 3–10 min)

## Updating a Running Application

### Docker path
1. Rebuild and push the image
2. In Cloudera AI → Applications → Restart

### Git source path
1. Push code changes to the Git branch
2. In Cloudera AI → Applications → Restart

To update credentials without a code change: use `/configure` → then Restart.

To force re-ingestion (after adding new documents):
1. Stop the application
2. Delete `data/vector_store/`
3. Restart — ingestion runs automatically, new `index.sha256` is written

## Key Environment Variables

| Variable | Docker default | Local dev default | Notes |
|---|---|---|---|
| `QUERY_ENGINE` | `trino` | `sqlite` | Set by Dockerfile ENV |
| `DOCS_STORAGE_TYPE` | `s3` | `local` | Set by Dockerfile ENV |
| `LLM_PROVIDER` | — | — | Required |
| `APP_PORT` | `8080` | `8080` | Must stay 8080 |

See `DEPLOYMENT.md` Section 12 and `deployment/app_config.md` for full reference.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| App stuck starting | Check logs; often missing env var or failed pip install |
| `ImportError` | Check `requirements.txt` includes all needed packages |
| Trino not ready | Trino takes 2–4 min on first boot; entrypoint.sh waits up to 5 min |
| MinIO bucket missing | `seed_iceberg.py` failed — check logs for boto3 connection errors |
| LLM indicator red | Open `/configure`, check provider credentials, save and restart |
| LLM red for Bedrock/Anthropic | No `LLM_BASE_URL` needed — configure `LLM_PROVIDER` correctly |
| Vector store missing | Ingestion should auto-run; check logs for `document_loader` errors |
| `integrity check FAILED` | Delete `data/vector_store/` and restart to force re-ingestion |
| Port conflict | Ensure no other service on port 8080; check `APP_PORT` |
| `/configure` shows "From environment" but field locked | Update via Cloudera AI platform UI instead |
