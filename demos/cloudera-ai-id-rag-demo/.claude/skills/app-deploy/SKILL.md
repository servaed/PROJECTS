---
name: app-deploy
description: Steps for preparing and validating deployment as a Cloudera AI Application, including Git repo setup, env vars, configure wizard, and launch script.
---

# Skill: App Deployment

## Pre-Deployment Checklist

- [ ] `APP_PORT=8080` is set (or left as default)
- [ ] LLM credentials set via platform env vars **or** saved via `/configure` wizard
- [ ] `DATABASE_URL` points to a read-only database user
- [ ] `SQL_APPROVED_TABLES` is set to only the tables needed for the demo
- [ ] `deployment/launch_app.sh` is executable and tested locally
- [ ] No credentials in version control (`.env` and `data/.env.local` are in `.gitignore`)
- [ ] `requirements.txt` is up to date
- [ ] All tests pass: `pytest tests/ -v`

## Local Validation

```bash
# 1. Start the app
uvicorn app.api:app --host 0.0.0.0 --port 8080 --reload

# 2. Open http://localhost:8080 — React SPA loads
# 3. Open http://localhost:8080/setup — all 5 component cards green
# 4. Open http://localhost:8080/configure — credentials form loads, badges show sources
# 5. Submit a test question — streaming response with source citations appears
# 6. Click ▶ Run Demo — auto-play walks through all sample prompts
# 7. Check /api/status returns ok for vector_store, database, and llm
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

## Cloudera AI Applications Deployment Steps

1. Push repo to Git (GitHub, GitLab, Bitbucket)
2. Open Cloudera AI → Applications → New Application
3. Set **Source** to Git, enter repo URL and branch
4. Set **Launch Command**: `bash deployment/launch_app.sh`
5. Set LLM env vars (or skip and use `/configure` after deploy)
6. Select resource profile (2 vCPU / 4 GB minimum; 4 vCPU / 8 GB for local embeddings)
7. Set auth: SSO for production, Unauthenticated for demo only
8. Click Deploy and wait for status → Running (first boot: 3–10 min)
9. Verify at `/setup` — all five cards should be green

## What launch_app.sh Does (startup sequence)

```
[0/5] Source data/.env.local if it exists (written by /configure wizard)
[1/5] pip install -r requirements.txt (skipped after first run)
[2/5] Install provider-specific SDK if needed (boto3 / anthropic)
[3/5] Seed demo SQLite database (idempotent)
[4/5] Ingest documents into FAISS vector store (skipped if index exists)
[5/5] Start uvicorn on port 8080
```

## Updating a Running Application

1. Push code changes to the Git branch
2. In Cloudera AI → Applications → find the app → Restart
3. Or: use `/configure` to update credentials without a code push → then Restart

To force re-ingestion (after adding new documents):
1. Stop the application
2. Delete `data/vector_store/`
3. Restart — ingestion runs automatically, new `index.sha256` is written

## Environment Variables Reference

See `DEPLOYMENT.md` Section 12 for the full variable reference table.
See `deployment/app_config.md` for inline descriptions.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| App stuck starting | Check logs; often missing env var or failed pip install |
| `ImportError` | Check `requirements.txt` includes all needed packages |
| LLM indicator red | Open `/configure`, check provider credentials, save and restart |
| LLM red for Bedrock/Anthropic | These providers have no `LLM_BASE_URL` — configure `LLM_PROVIDER` correctly |
| Vector store missing | Ingestion should auto-run; check logs for `document_loader` errors |
| `integrity check FAILED` | Delete `data/vector_store/` and restart to force re-ingestion |
| Port conflict | Ensure no other service on port 8080; check `APP_PORT` |
| `/configure` shows "From environment" but field locked | Update via Cloudera AI platform UI instead |
