---
name: cloudera-ai-architecture
description: Architecture guidance for Cloudera AI Application design. Covers CML application constraints, port handling, deployment path (Git/Script), auth, resource profiles, and enterprise CDP mapping. Sourced from official Cloudera documentation.
---

# Skill: Cloudera AI Architecture

## CML Applications — Verified Constraints (from Cloudera Docs)

- **Port**: CML injects `CDSW_APP_PORT` (default 8080) and `CDSW_READONLY_PORT`.
  Always bind to `$CDSW_APP_PORT` — do not hardcode. `APP_PORT=8080` works because CML sets `CDSW_APP_PORT=8080`.
- **Script field runs Python only** — CML executes the Script as a Python file.
  Use a Python launcher (`run_app.py`) to invoke bash startup scripts via `subprocess`.
- **No user-specified Docker image source** — CML uses Source-to-Image (S2I) internally.
  Custom Docker images cannot be supplied directly in the Applications UI.
- **Single-node constraint**: All resources for a pod must be contiguous on one node.
  Pods cannot span multiple worker nodes.
- **No auto-timeout**: Applications run indefinitely until manually stopped or restarted.
  Unlike Sessions, which timeout after 60 minutes of inactivity.
- **Auth**: CML handles SSO/LDAP. App receives `Remote-user` and `Remote-user-perm` headers.
  The app must not implement its own authentication.
- **Public access**: Disabled by default. Admin must enable "Allow applications to be
  configured with unauthenticated access" in Site Administration.
- **SSH through HTTP proxy**: Not supported. Use HTTPS for Git operations in such environments.
- **Static subdomains for AMP apps**: Available from CML 2.0.45-b54 onwards.
- **Subdomain format**: DNS-compliant — lowercase letters, digits, hyphens only.

---

## Application Ports

| Port variable | Access level | Use case |
|---|---|---|
| `CDSW_APP_PORT` | Contributors and Admins (RW) | Main application endpoint |
| `CDSW_READONLY_PORT` | All users with read access (RO) | Read-only dashboards |

Bind uvicorn to `CDSW_APP_PORT`:
```bash
exec uvicorn app.api:app --host 0.0.0.0 --port ${CDSW_APP_PORT:-8080}
```

---

## Deployment Path (Git Source + Python Launcher)

This is the only supported path in CML 2.0.55 and earlier UI versions.

```
GitHub repo
  └── demos/cloudera-ai-id-rag-demo/
        ├── run_app.py              ← Script field points here (Python)
        └── deployment/
              └── launch_app.sh    ← Called by run_app.py via subprocess
```

`run_app.py`:
```python
import os, subprocess, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.exit(subprocess.call(["bash", "deployment/launch_app.sh"]))
```

`launch_app.sh` sequence:
1. Source `data/.env.local` (saved credentials from /configure wizard)
2. `pip install -r requirements.txt` (skipped after first run)
3. Install provider SDK if needed (boto3 / anthropic)
4. Seed Parquet files via `seed_parquet.py` — 9 tables, 1485 rows (idempotent, checks `msme_credit.parquet`)
5. Build FAISS vector store (skipped if `index.faiss` exists)
6. `exec uvicorn app.api:app --host 0.0.0.0 --port ${CDSW_APP_PORT:-8080}`

---

## LLM Inference Endpoint (Cloudera AI Inference)

Cloudera AI Inference endpoints are OpenAI-compatible. URL pattern:
```
https://<workspace-domain>/namespaces/serving/endpoints/<endpoint-name>/v1
```
Find endpoint URL and key at: CML Workspace → AI Inference → your model → Endpoint Details.

Set environment variables:
```
LLM_PROVIDER=cloudera
LLM_BASE_URL=https://<workspace>/namespaces/serving/endpoints/<model>/v1
LLM_API_KEY=<key from endpoint detail page>
LLM_MODEL_ID=meta-llama-3-8b-instruct
```

---

## Resource Profiles

Admin pre-configures available profiles. Users select at application creation.

| Mode | vCPU | RAM | Notes |
|---|---|---|---|
| Local embeddings (e5-large) | 4 | 8 GiB | Model ~3 GB RAM |
| OpenAI embeddings | 1–2 | 2–4 GiB | No local model |

Set `EMBEDDINGS_PROVIDER=openai` + `OPENAI_API_KEY` to reduce RAM by ~3 GB.
Minimum absolute: 2 GB RAM (Cloudera docs recommendation).

---

## Storage Architecture

| Layer | This demo (Git/DuckDB) | CDP Production equivalent |
|---|---|---|
| Relational store | DuckDB reading Parquet files in `data/parquet/` | Cloudera Data Warehouse (CDW / Trino + Iceberg) |
| Document store | Local filesystem (`data/sample_docs/`) | Apache Ozone S3 Gateway |
| Iceberg catalog | N/A (Parquet files, no catalog) | Cloudera Unified Metastore |
| Vector store | FAISS (local) | Enterprise vector DB |
| Object storage | N/A | Apache Ozone bucket |

For production: set `QUERY_ENGINE=trino`, `TRINO_HOST`, `TRINO_CATALOG`, `TRINO_SCHEMA`
and `DOCS_STORAGE_TYPE=s3`, `MINIO_ENDPOINT=http://ozone-s3gw:9878`.

**SQL dialect parity**: DuckDB and Trino share the same SQL syntax for the queries this app
generates. Switching engines requires only an env var change, no SQL changes.

---

## Environment Variable Precedence

```
Application-level env vars (set in Applications UI)
  > Project-level env vars (set in Project Settings)
    > data/.env.local (written by /configure wizard)
      > code defaults (src/config/settings.py)
```

Variables set at the Application level appear as locked ("From environment") in the
`/configure` wizard and cannot be overridden from the browser.

---

## Auth Headers Injected by CML

CML injects these HTTP headers on every authenticated request:

| Header | Value |
|---|---|
| `Remote-user` | `<username>` |
| `Remote-user-perm` | `RO` / `RW` / `Unauthorized` |

The app can read these to determine the logged-in user without implementing SSO itself.

---

## CDP Service Mapping

| Embedded demo component | CDP Production service |
|---|---|
| DuckDB + local Parquet files | Cloudera Data Warehouse (CDW) with Trino + Iceberg on Ozone |
| Local filesystem docs | Apache Ozone (S3-compatible gateway) |
| FAISS (local) | Enterprise vector store / Pinecone / OpenSearch kNN |
| uvicorn (single process) | Cloudera AI Application (horizontally scalable) |
