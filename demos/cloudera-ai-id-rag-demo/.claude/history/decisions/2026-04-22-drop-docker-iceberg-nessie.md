# Decision — Drop Docker/Iceberg/Nessie Embedded Deployment

**Date:** 2026-04-22

## Decision

Remove the embedded Docker approach (Dockerfile + docker-compose with MinIO + Nessie +
Trino inside a single container) from the project. The standard deployment path is now
**Cloudera AI Application (Git source)** with SQLite + local filesystem for dev and
CDW Trino + Apache Ozone for production.

## Context

The original design bundled MinIO, Project Nessie, and Trino inside a Docker image so
the demo could run anywhere without CDP. This added significant complexity:
- Multi-service Docker entrypoint script managing 4 processes
- Iceberg seed script (`seed_iceberg.py`) separate from the SQLite seeder
- GitHub Actions CI for building and pushing the Docker image
- Trino catalog config files
- ~5–10 min first-build time downloading 1 GB+ of binaries

## Why Dropped

1. **Cloudera AI Workbench is the target platform** — CML Applications run from Git source
   (Python script), not Docker images. The Docker path was never the CML path.
2. **SQLite is sufficient for presales demos** — all 9 tables, 1485 rows, full bilingual
   Q&A works perfectly on SQLite. No functional advantage to embedded Trino for demos.
3. **CDP connectors already in code** — `trino_adapter.py` and `ozone_adapter.py` exist;
   switching to real CDW/Ozone requires only env var changes. The architecture story holds.
4. **Simplicity wins** — fewer moving parts = faster to deploy, easier to troubleshoot on
   customer sites.

## What Was Removed

- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `.github/workflows/docker-build.yml`
- `deployment/entrypoint.sh`
- `deployment/seed_iceberg.py`
- `deployment/trino/etc/catalog/iceberg.properties`
- `src/connectors/hdfs_adapter.py` (HDFS not in any current deployment path)
- `data/manifests/sample_manifest.json`
- `cloudera-ai-rag-write_docs.py`
- `test_sse_runner.py`

## What Was Kept

- `src/connectors/trino_adapter.py` — production CDP path (CDW)
- `src/connectors/ozone_adapter.py` — production CDP path (Ozone S3GW)
- `deployment/launch_app.sh` — CML startup script
- `deployment/cloudera_ai_application.md` — CML deployment guide

## Architecture Narrative

README now shows Trino + Ozone as the primary architecture (matching Cloudera technology)
with a clear note that local dev uses SQLite + local filesystem via swappable connectors.
This gives a stronger Cloudera story without requiring a running CDP cluster for the demo.
