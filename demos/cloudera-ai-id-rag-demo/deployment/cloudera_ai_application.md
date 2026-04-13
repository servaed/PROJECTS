# Deployment Guide — Cloudera AI Application

## Prerequisites

- Cloudera AI workspace with Applications access enabled
- An LLM model deployed in Cloudera AI Inference (or another OpenAI-compatible endpoint)
- Git repository accessible from the workspace

---

## Deployment Steps

### 1. Prepare the Repository

```bash
# Push all code to Git
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

### 4. Set Environment Variables

In the **Environment Variables** section, set all variables from `.env.example`.

**Required:**
```
LLM_PROVIDER=cloudera
CLOUDERA_INFERENCE_URL=https://your-workspace/namespaces/serving/endpoints/your-model
CLOUDERA_INFERENCE_API_KEY=your-api-key
CLOUDERA_INFERENCE_MODEL_ID=meta-llama-3-8b-instruct
```

**Optional (if using enterprise storage):**
```
DOCS_STORAGE_TYPE=local
DOCS_SOURCE_PATH=./data/sample_docs
DATABASE_URL=sqlite:///./data/sample_tables/demo.db
SQL_APPROVED_TABLES=kredit_umkm,nasabah,cabang
```

### 5. Deploy

- Click **Deploy Application**
- Wait for status to change to **Running**
- Access the application via the URL provided by Cloudera AI

---

## Important Notes

### Port
The app **must** run on port **8080**. `launch_app.sh` sets this automatically. Do not change the Streamlit port without also updating `APP_PORT`.

### Authentication
- **SSO**: Recommended for production. Cloudera AI handles authentication — the app does not need its own auth logic.
- **Unauthenticated**: For internal demos only. Never use with sensitive data.

### Persistent Storage
For production environments:
- Store the vector store on NFS/S3 mounted to the pod, not in the container filesystem
- Set `VECTOR_STORE_PATH` to a persistent path
- Set `DATABASE_URL` to an enterprise database (PostgreSQL, Hive, Impala)

### Resource Profiles

| Scenario | CPU | RAM |
|----------|-----|-----|
| Demo / development | 1 vCPU | 2 GB |
| Production (light) | 2 vCPU | 4 GB |
| Local embeddings (large model) | 4 vCPU | 8 GB |

---

## Deployment Verification

After the application is running:

1. Open the application URL — the chat interface should appear
2. Type a test question: *"Halo, apa yang bisa kamu bantu?"*
3. Verify the **Source Documents** panel appears with results
4. Verify the **SQL Query** panel appears for data questions

---

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| App does not start | Check logs in the Cloudera AI Application console |
| `LLM not available` | Verify `CLOUDERA_INFERENCE_URL` and API key |
| Documents not found | Ensure `DOCS_SOURCE_PATH` contains files and ingestion ran |
| SQL error | Check `DATABASE_URL` and `SQL_APPROVED_TABLES` |
| Port error | Ensure `APP_PORT=8080` — do not modify |
