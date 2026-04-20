# Deployment Guide — Cloudera AI Application (Quick Reference)

For the full deployment guide see [`DEPLOYMENT.md`](../DEPLOYMENT.md).

Two deployment paths are available:

| Path | Launch method | Storage | Query engine |
|------|---------------|---------|--------------|
| **Docker image** (recommended) | Docker Image source | MinIO / Ozone | Trino + Iceberg |
| **Git source** | `bash deployment/launch_app.sh` | Local filesystem | SQLite |

---

## Prerequisites

- Cloudera AI workspace with Applications access enabled
- An LLM model deployed in Cloudera AI Inference (or another OpenAI-compatible endpoint)
- **Path A**: Docker registry accessible from the workspace; Docker build environment
- **Path B**: Git repository accessible from the workspace

---

## Path A — Docker Image (Recommended)

### 1. Build and Push

```bash
cd cloudera-ai-id-rag-demo
docker build -t <registry>/cloudera-ai-id-rag-demo:latest .
docker push <registry>/cloudera-ai-id-rag-demo:latest
```

Build time: ~5–10 min first time (downloads MinIO binary, Nessie JAR, Trino 455 tarball).

### 2. Create the Application

In your Cloudera AI workspace:
- Click **Applications** → **+ New Application**

| Field | Value |
|-------|-------|
| **Name** | `asisten-enterprise-id` |
| **Subdomain** | `asisten-enterprise` |
| **Source** | **Docker Image** |
| **Image URL** | `<registry>/cloudera-ai-id-rag-demo:latest` |
| **Resource Profile** | 4 vCPU / 8 GB RAM |
| **Auth Type** | SSO (recommended) or Unauthenticated (demo only) |

### 3. Set LLM Environment Variables

```
LLM_PROVIDER=cloudera
LLM_BASE_URL=https://your-workspace/namespaces/serving/endpoints/your-model/v1
LLM_API_KEY=your-api-key
LLM_MODEL_ID=meta-llama-3-8b-instruct
```

Or leave blank and configure via `http://<app-url>/configure` after the app is running.

### 4. Deploy

- Click **Deploy Application**
- Wait for status → **Running** (~5–15 min first boot)
  - MinIO, Nessie, Trino start sequentially inside the container
  - `seed_iceberg.py` creates buckets, uploads documents, creates Iceberg tables
  - FAISS vector store is built from documents in MinIO

### What `entrypoint.sh` does

```
[1/6] Start MinIO on :9000       wait for health check
[2/6] Start Nessie on :19120     wait for health check
[3/6] Start Trino on :8085       wait for health check (up to 5 min)
[4/6] Run seed_iceberg.py        create buckets + upload docs + seed 9 Iceberg tables
[5/6] Build FAISS vector store   (skipped if index already exists)
[6/6] exec uvicorn on port $PORT
```

---

## Path B — Git Source (SQLite Mode)

### 1. Push code to Git

```bash
git push origin main
```

### 2. Create the Application

| Field | Value |
|-------|-------|
| **Name** | `asisten-enterprise-id` |
| **Subdomain** | `asisten-enterprise` |
| **Source** | Git Repository |
| **Git URL** | Your repository URL |
| **Branch** | `main` |
| **Launch Command** | `bash deployment/launch_app.sh` |
| **Resource Profile** | 4 vCPU / 8 GB RAM |
| **Auth Type** | SSO (recommended) or Unauthenticated (demo only) |

### What `launch_app.sh` does

```
[0/5] Source data/.env.local if it exists (written by /configure wizard)
[1/5] pip install -r requirements.txt (skipped if marker file present)
[2/5] Install provider SDK if needed (boto3 / anthropic)
[3/5] Seed SQLite demo database (idempotent)
[4/5] Ingest documents into FAISS vector store (skipped if index exists)
[5/5] Start uvicorn on port 8080
```

Uses SQLite + local filesystem only — no MinIO, Nessie, or Trino.

---

## Configure Credentials After Deployment

**Option A — Configure wizard (no shell access needed):**

1. Open `http://<app-url>/configure`
2. Select provider, fill in credentials, click **Save Configuration**
3. Restart the app from Cloudera AI Applications UI

**Option B — Platform UI:**

Set `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_ID` in the
Application **Environment Variables** panel and restart.

---

## Verify

| Check | URL |
|-------|-----|
| Chat interface loads | `http://<app-url>/` |
| All components green | `http://<app-url>/setup` |
| Credentials set correctly | `http://<app-url>/configure` |

---

## Important Notes

### Port
The app **must** run on port **8080**. Both `entrypoint.sh` and `launch_app.sh` start uvicorn
on this port automatically. Do not change `APP_PORT`.

### Credentials precedence
Platform environment variables **always** take precedence over values saved via
the `/configure` wizard. Wizard-saved values are stored in `data/.env.local` and
loaded at step [0] of the startup script.

### Authentication
- **SSO**: Recommended for production — Cloudera AI handles auth; the app has no auth logic.
- **Unauthenticated**: For internal demos only. Never use with real customer data.

### Resource Profiles

| Scenario | CPU | RAM |
|----------|-----|-----|
| Docker image (full stack) | 4 vCPU | 8 GB |
| Git source (local embeddings) | 4 vCPU | 8 GB |
| Git source (OpenAI embeddings) | 1 vCPU | 2 GB |

### Mapping to Cloudera CDP services

| Docker component | CDP equivalent |
|---|---|
| MinIO (embedded) | Apache Ozone (set `MINIO_ENDPOINT` to Ozone S3GW URL) |
| Nessie (embedded) | Cloudera Unified Metastore |
| Trino (embedded) | Cloudera Data Warehouse (CDW) |
| Iceberg tables (Parquet) | Apache Iceberg on Ozone |

---

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| App does not start | Check logs in the Cloudera AI Application console |
| LLM indicator red | Open `/configure`, check provider credentials, save and restart |
| Vector store missing | Check logs for ingestion errors; verify documents were uploaded |
| `integrity check FAILED` | Delete `data/vector_store/` and restart to force re-ingestion |
| Trino not ready at startup | Trino takes 2–4 min on first boot; `entrypoint.sh` waits up to 5 min |
| MinIO bucket missing | `seed_iceberg.py` failed — check startup logs for boto3 errors |
| SQL errors | Verify `QUERY_ENGINE` and `TRINO_*` / `DATABASE_URL` settings |
| Port error | Ensure `APP_PORT=8080` — do not modify |
| `/configure` shows "From environment" | Update via Cloudera AI platform UI instead |
