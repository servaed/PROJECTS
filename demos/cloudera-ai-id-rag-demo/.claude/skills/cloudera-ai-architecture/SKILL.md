---
name: cloudera-ai-architecture
description: Architecture guidance for Cloudera AI Application design. Covers port 8080, two deployment paths (Docker image vs Git source), embedded service stack (MinIO/Nessie/Trino), and enterprise CDP mapping.
---

# Skill: Cloudera AI Architecture

## Key Deployment Constraints

- **Port 8080 is mandatory.** Cloudera AI Applications runtime expects the app on port 8080. Never change this.
- Deployment modes: **Docker image** (recommended) or **Git repository URL** via the Cloudera AI Applications UI.
- Auth is handled by the Cloudera AI platform (SSO/LDAP). The app itself must not implement auth.
- Environment variables are injected at deploy time via the Applications UI — never hardcode.
- Resource profiles are selected at deploy time. The app must start correctly under the minimum profile.
- **Single-container constraint**: CML Applications run one container per replica. Docker Compose cannot run directly — all services must be embedded in one image.

## Two Deployment Paths

### Path A — Docker Image (recommended)
- Builds a multi-stage image: Stage 1 downloads MinIO binary, Nessie JAR, Trino 455 tarball; Stage 2 is python:3.11-slim + openjdk-17
- Entry point: `deployment/entrypoint.sh` — starts MinIO → Nessie → Trino → seeds Iceberg → builds vector store → starts uvicorn
- ENV in Dockerfile: `QUERY_ENGINE=trino`, `DOCS_STORAGE_TYPE=s3`
- Represents full Cloudera CDP stack: MinIO → Ozone, Nessie → Unified Metastore, Trino → CDW

### Path B — Git Source (local dev / lightweight CML)
- Launch command: `bash deployment/launch_app.sh`
- Uses SQLite + local filesystem only — no Java services
- Faster to start; suitable for iteration and demos without Docker registry

## Application Launch (Docker / CML)

`deployment/entrypoint.sh` sequence:
1. Start MinIO on :9000 — wait for `/minio/health/live`
2. Start Nessie on :19120 — wait for `/api/v1/config`
3. Start Trino on :8085 — wait for `/v1/info` (up to 100 × 3 s)
4. Run `deployment/seed_iceberg.py` — create buckets, upload docs, seed 9 Iceberg tables
5. Build FAISS vector store if index missing
6. `exec uvicorn app.api:app --host 0.0.0.0 --port $PORT`

## Application Launch (Git / local)

`deployment/launch_app.sh` sequence:
1. Source `data/.env.local` if exists
2. `pip install -r requirements.txt` (skipped after first run via marker file)
3. Install provider-specific SDK if needed (boto3 / anthropic)
4. Seed SQLite demo database (idempotent)
5. Ingest documents into FAISS vector store (skipped if index exists)
6. `uvicorn app.api:app --host 0.0.0.0 --port $APP_PORT`

## LLM Endpoint

Cloudera AI Inference endpoints are OpenAI-compatible. Use `LLM_BASE_URL` and `LLM_API_KEY`. The endpoint URL pattern is:
```
https://<workspace-domain>/namespaces/serving/endpoints/<endpoint-name>/v1
```

## Storage Architecture

| Layer | Demo (Docker) | CDP Production |
|-------|---------------|----------------|
| Object storage | MinIO :9000 | Apache Ozone S3 Gateway |
| Documents bucket | `rag-docs` (boto3) | Ozone bucket (same API) |
| Iceberg warehouse | `rag-warehouse` (MinIO) | Ozone bucket |
| Iceberg catalog | Nessie REST :19120 | Cloudera Unified Metastore |
| Query engine | Trino :8085 (Iceberg conn.) | Cloudera Data Warehouse (CDW) |
| Vector store | FAISS local | Enterprise vector DB |
| Local dev fallback | SQLite + local FS | N/A |

Connector factory in `src/connectors/db_adapter.py` dispatches on `QUERY_ENGINE`:
- `sqlite` → SQLAlchemy + SQLite (default, local dev)
- `trino` → `trino_adapter.py` (Docker/CML)

Document loader in `src/retrieval/document_loader.py` dispatches on `DOCS_STORAGE_TYPE`:
- `local` → `FilesAdapter` (default, local dev)
- `s3` → `OzoneAdapter` (boto3, Docker/CML)

Always use adapters (`src/connectors/`) — never hardcode storage access in domain logic.
