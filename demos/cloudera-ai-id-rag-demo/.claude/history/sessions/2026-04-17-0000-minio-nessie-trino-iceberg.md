# Session — 2026-04-17: MinIO + Nessie + Trino + Iceberg Embedded Stack

## Objectives
- Integrate Ozone (object storage), Trino (query engine), and Iceberg table format to
  relate the demo directly to Cloudera CDP solutions
- Make the demo self-contained and portable: single Docker image, runs on developer
  laptop and Cloudera AI Workbench (CML) with zero external dependencies
- Maintain backwards compatibility: local dev continues to work with SQLite + local filesystem

## Architecture Decisions
See `decisions/2026-04-17-minio-nessie-trino-iceberg.md`

## Work Completed

### 1. New connectors

`src/connectors/trino_adapter.py`:
- Trino Python client (`trino` package) implementing `execute_read_query`, `get_table_names`,
  `get_table_schema` — same interface as db_adapter's SQLAlchemy layer
- Connects to Trino on `TRINO_HOST:TRINO_PORT` using catalog/schema from settings

`src/connectors/ozone_adapter.py`:
- boto3 S3 client for MinIO / Ozone S3GW (path-style, s3v4 signature)
- `list_documents()` returns relative `Path` objects (e.g. `Path("banking/file.txt")`)
  so `_infer_domain()` works without changes
- `read_bytes(path)` downloads and returns raw bytes

### 2. Updated connectors

`src/connectors/db_adapter.py`:
- Rewritten as factory: `QUERY_ENGINE=trino` → trino_adapter; default → SQLAlchemy/SQLite
- Added `get_engine()` public alias (bug fix: `app/api.py` imports it for health check)

`src/retrieval/document_loader.py`:
- `load_documents()` branches on `DOCS_STORAGE_TYPE == "s3"` → OzoneAdapter
- `base_path=Path(".")` passed for S3 mode (keys are already relative)

### 3. Settings

`src/config/settings.py` — added:
- `query_engine: Literal["sqlite", "trino"] = "sqlite"`
- `trino_host`, `trino_port`, `trino_catalog`, `trino_schema`, `trino_user`
- `minio_endpoint`, `minio_access_key`, `minio_secret_key`
- `minio_docs_bucket`, `minio_warehouse_bucket`

### 4. Trino configuration

`deployment/trino/etc/catalog/iceberg.properties`:
- Iceberg connector with Nessie REST catalog
- MinIO native S3 filesystem with path-style access

### 5. Dockerfile (multi-stage)

- Stage 1 `infra`: downloads MinIO binary, Nessie 0.83.2 JAR, Trino 455 tarball (~800 MB)
- Stage 2: python:3.11-slim + openjdk-17 + Python deps + infra binaries from stage 1
- ENV sets `QUERY_ENGINE=trino`, `DOCS_STORAGE_TYPE=s3`, `JAVA_HOME`
- CMD: `["bash", "deployment/entrypoint.sh"]`

### 6. entrypoint.sh

Sequential startup with `wait_for_http` loops:
MinIO → Nessie → Trino (up to 5 min wait) → seed_iceberg.py → FAISS build → uvicorn

### 7. seed_iceberg.py

Creates `rag-docs` and `rag-warehouse` buckets, uploads `data/sample_docs/` to MinIO,
creates `iceberg.demo` schema, drops and recreates all 9 Iceberg tables (BIGINT/DOUBLE/
VARCHAR/INTEGER types), inserts 148+ rows.

### 8. requirements.txt

Added `trino>=0.328.0,<1.0.0`, `boto3>=1.34.0,<2.0.0`, `pyarrow>=15.0.0,<20.0.0`

### 9. Test fixes

`tests/test_retrieval.py`:
- Added `domain="banking"` to `_make_raw_doc()` (required field)
- Changed `assert_called_once_with(k=3)` to `assert_called_once()` for hybrid retriever

### 10. Documentation

All 4 user-facing MD files + 2 skill files + 3 new history files updated.

## CML Deployment Notes

- CML runs a single container per application replica — no Docker Compose
- All Java services (MinIO, Nessie, Trino) must be in the same image as Python
- supervisord was considered but `entrypoint.sh` with sequential `wait_for_http` loops
  is simpler and produces cleaner startup logs
- First boot: ~5–15 min (Trino startup ~3–4 min + seeding + FAISS build)
- Subsequent restarts: ~2–3 min (Trino restarts but data re-seeded idempotently)

## Key Decisions
See `decisions/2026-04-17-minio-nessie-trino-iceberg.md`
