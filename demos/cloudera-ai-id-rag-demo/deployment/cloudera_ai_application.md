# Deployment Guide — Cloudera AI Application (Quick Reference)

For the full deployment guide see [`DEPLOYMENT.md`](../DEPLOYMENT.md).

---

## Prerequisites

- Cloudera AI workspace with Applications access enabled
- An LLM model deployed in Cloudera AI Inference (or another OpenAI-compatible endpoint)
- Git repository accessible from the workspace

---

## Deployment Steps

### 1. Prepare the Repository

```bash
git push origin main
```

### 2. Open Cloudera AI Applications

In your Cloudera AI workspace:
- Click **Applications** in the left sidebar
- Click **+ New Application**

### 3. Configure the Application

| Field | Value |
|-------|-------|
| **Name** | `asisten-enterprise-id` |
| **Subdomain** | `asisten-enterprise` |
| **Description** | Bahasa Indonesia Enterprise Assistant |
| **Source** | Git Repository |
| **Git URL** | Your repository URL |
| **Branch** | `main` |
| **Launch Command** | `bash deployment/launch_app.sh` |
| **Resource Profile** | 2 vCPU / 4 GB RAM (minimum) |
| **Auth Type** | SSO (recommended) or Unauthenticated (demo only) |

### 4. Set Environment Variables (two options)

**Option A — Platform UI (before or after deploy):**

```
LLM_PROVIDER=cloudera
LLM_BASE_URL=https://your-workspace/namespaces/serving/endpoints/your-model/v1
LLM_API_KEY=your-api-key
LLM_MODEL_ID=meta-llama-3-8b-instruct
```

**Option B — Configure wizard (after deploy, no shell access needed):**

1. Open `http://<app-url>/configure`
2. Select provider, fill in credentials, click **Save Configuration**
3. Restart the app from Cloudera AI Applications UI

### 5. Deploy

- Click **Deploy Application**
- Wait for status → **Running** (first boot: 3–10 min for pip install + model download)
- Open the application URL

### 6. Verify

| Check | URL |
|-------|-----|
| Chat interface loads | `http://<app-url>/` |
| All components green | `http://<app-url>/setup` |
| Credentials set correctly | `http://<app-url>/configure` |

---

## What `launch_app.sh` Does

```
[0/5] Source data/.env.local if it exists (written by /configure wizard)
[1/5] pip install -r requirements.txt (skipped if marker file present)
[2/5] Install provider SDK if needed (boto3 / anthropic)
[3/5] Seed SQLite demo database (idempotent)
[4/5] Ingest documents into FAISS vector store (skipped if index exists)
[5/5] Start uvicorn on port 8080
```

---

## Important Notes

### Port
The app **must** run on port **8080**. `launch_app.sh` starts uvicorn on this port
automatically. Do not change the port without also updating `APP_PORT`.

### Credentials precedence
Platform environment variables **always** take precedence over values saved via
the `/configure` wizard. Wizard-saved values are stored in `data/.env.local` and
loaded at step [0/5] of the startup script.

### Authentication
- **SSO**: Recommended for production — Cloudera AI handles auth, the app has no auth logic.
- **Unauthenticated**: For internal demos only. Never use with real customer data.

### Persistent Storage
For production environments:
- Mount `VECTOR_STORE_PATH` on NFS/S3 so the index persists across pod restarts
- Set `DATABASE_URL` to an enterprise database (PostgreSQL, Hive, Impala) with read-only credentials
- Set `SQL_APPROVED_TABLES` to expose only the tables needed for the demo

### Resource Profiles

| Scenario | CPU | RAM |
|----------|-----|-----|
| Demo (OpenAI embeddings) | 1 vCPU | 2 GB |
| Demo (local embeddings, e5-large) | 4 vCPU | 8 GB |
| Production (light) | 2 vCPU | 4 GB |

---

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| App does not start | Check logs in the Cloudera AI Application console |
| LLM indicator red | Open `/configure`, check provider credentials, save and restart |
| Vector store missing | Check logs for ingestion errors; verify `DOCS_SOURCE_PATH` has files |
| `integrity check FAILED` | Delete `data/vector_store/` and restart to force re-ingestion |
| SQL errors | Check `DATABASE_URL` and `SQL_APPROVED_TABLES` |
| Port error | Ensure `APP_PORT=8080` — do not modify |
| `/configure` shows "From environment" but field is locked | Update via Cloudera AI platform UI instead |
