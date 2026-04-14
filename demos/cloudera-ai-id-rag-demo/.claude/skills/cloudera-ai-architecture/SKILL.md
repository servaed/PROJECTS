---
name: cloudera-ai-architecture
description: Architecture guidance for Cloudera AI Application design. Reminds the agent about port 8080, deployment model, auth, and enterprise constraints.
---

# Skill: Cloudera AI Architecture

## Key Deployment Constraints

- **Port 8080 is mandatory.** Cloudera AI Applications runtime expects the app on port 8080. Never change this.
- Deployment modes: Git repository URL or Docker image via the Cloudera AI Applications UI.
- Auth is handled by the Cloudera AI platform (SSO/LDAP). The app itself must not implement auth.
- Environment variables are injected at deploy time via the Applications UI — never hardcode.
- Resource profiles are selected at deploy time. The app must start correctly under the minimum profile.
- Autoscaling is optional — the app must be stateless or store state in external storage to support it.

## Application Launch

Always use `deployment/launch_app.sh` as the launch command. It handles:
1. Dependency install (idempotent, skipped after first run via `.deps_installed` marker)
2. Optional provider SDK install (boto3 for Bedrock, anthropic for Anthropic)
3. Demo SQLite database seeding (idempotent)
4. Document ingestion if FAISS vector store does not exist
5. FastAPI + React SPA startup on port `$APP_PORT` (default 8080) via `uvicorn app.api:app`

## LLM Endpoint

Cloudera AI Inference endpoints are OpenAI-compatible. Use `CLOUDERA_INFERENCE_URL` and `CLOUDERA_INFERENCE_API_KEY`. The endpoint URL pattern is:
```
https://<workspace-domain>/namespaces/serving/endpoints/<endpoint-name>
```

## Storage in Enterprise Environments

| Data type | Demo mode | Enterprise mode |
|-----------|-----------|-----------------|
| Documents | Local filesystem | HDFS or object storage mounted to pod |
| Vector store | Local FAISS file | Managed vector DB or NFS |
| Structured data | SQLite file | PostgreSQL / Hive / Impala via JDBC |

Always use adapters (`src/connectors/`) — never hardcode storage access in domain logic.
