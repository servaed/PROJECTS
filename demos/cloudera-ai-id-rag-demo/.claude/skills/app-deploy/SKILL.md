---
name: app-deploy
description: Steps for preparing and validating deployment as a Cloudera AI Application, including Git repo setup, env vars, and launch script.
---

# Skill: App Deployment

## Pre-Deployment Checklist

- [ ] `APP_PORT=8080` is set (or left as default)
- [ ] `CLOUDERA_INFERENCE_URL` and `CLOUDERA_INFERENCE_API_KEY` are configured
- [ ] `DATABASE_URL` points to a read-only database user
- [ ] `SQL_APPROVED_TABLES` is set to only the tables needed for the demo
- [ ] `deployment/launch_app.sh` is executable and tested locally
- [ ] No credentials in version control (`.env` is in `.gitignore`)
- [ ] `requirements.txt` is up to date

## Local Validation

```bash
# 1. Test that the app starts on port 8080
bash deployment/launch_app.sh
# OR run directly (development with hot reload):
uvicorn app.api:app --host 0.0.0.0 --port 8080 --reload

# 2. Open http://localhost:8080 and verify the React SPA loads
# 3. Submit a test question and verify streaming response appears
# 4. Check /api/status returns ok for vector_store, database, and llm
# 5. Check logs for any errors
```

## Cloudera AI Applications Deployment Steps

1. Push repo to Git (GitHub, GitLab, Bitbucket)
2. Open Cloudera AI → Applications → New Application
3. Set **Source** to Git, enter repo URL and branch
4. Set **Launch Command**: `bash deployment/launch_app.sh`
5. Set all required environment variables from `.env.example`
6. Select resource profile (2 vCPU / 4 GB minimum)
7. Set auth type: SSO for production, Unauthenticated for demo only
8. Click Deploy and wait for status → Running
9. Click the app URL to verify

## Updating a Running Application

1. Push code changes to the Git branch
2. In Cloudera AI → Applications → find the app → Restart
3. Or: create a new application version pointing to the updated branch

## Environment Variables Reference

See `deployment/app_config.md` for the full variable reference table.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| App stuck starting | Check logs; often a missing env var or failed pip install |
| `ImportError` | Check `requirements.txt` includes all needed packages |
| `LLM not available` | Verify `CLOUDERA_INFERENCE_URL` is reachable from the workspace |
| Vector store missing | Ingestion should auto-run; check logs for errors |
| Port conflict | Ensure no other service is on port 8080; check `APP_PORT` |
