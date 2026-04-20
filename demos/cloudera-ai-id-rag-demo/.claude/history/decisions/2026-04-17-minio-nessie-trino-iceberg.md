# Decision — 2026-04-17: MinIO + Nessie + Trino + Iceberg Embedded Stack

## Stack selection: MinIO + Nessie + Trino (over DuckDB, StarRocks, ClickHouse)

**Decision**: Embed MinIO (object storage), Project Nessie (Iceberg REST catalog), and
Trino 455 (query engine) inside the Docker image. Use Apache Iceberg (Parquet) as the
table format.

**Alternatives considered**:
- **DuckDB**: No separate service needed (in-process), but doesn't map to any Cloudera CDP
  component. Poor demo value for CDP presales.
- **StarRocks / ClickHouse**: Require significant RAM and startup time; no Cloudera mapping;
  Iceberg support is secondary rather than native.
- **Real CDP components**: Not available on developer laptops; CML environments vary.
  Would make the demo non-portable.

**Why MinIO + Nessie + Trino**:
- Each maps 1:1 to a Cloudera CDP service (Ozone, Unified Metastore, CDW)
- Moving to real CDP requires only environment variable changes — no code changes
- Trino 455 Iceberg connector is production-grade and well-tested
- Total image overhead is acceptable (~1.5 GB binaries)

## Single-container constraint: supervisord vs entrypoint.sh

**Decision**: Use a plain `entrypoint.sh` with sequential `wait_for_http` loops rather
than supervisord for process management.

**Rationale**: CML Applications run one container per replica. The simplest approach that
works is a sequential startup script with HTTP health-check loops. supervisord adds
complexity (config file, process names, log routing) without meaningful benefit for a
demo — if Trino crashes after startup, the user will restart the CML Application anyway.
Sequential startup also produces clear, ordered log output that's easy to read in CML's
log viewer.

## OzoneAdapter: relative paths for domain inference

**Decision**: `OzoneAdapter.list_documents()` returns relative `Path` objects
(e.g. `Path("banking/kebijakan_kredit.txt")`) rather than full S3 URIs.

**Rationale**: `document_loader._infer_domain()` uses `path.relative_to(base_path)` to
extract the domain subdirectory. For S3 mode, `base_path=Path(".")` means the S3 key
itself (e.g. `banking/file.txt`) acts as the relative path. This reuses the existing
domain inference logic without any changes to that function.

## db_adapter factory: lazy import pattern

**Decision**: `db_adapter.py` uses lazy imports inside the dispatch functions
(`from src.connectors.trino_adapter import execute_read_query as _exec`) rather than
module-level imports.

**Rationale**: `trino` and `boto3` are optional dependencies. If the user runs in local
dev mode without these packages installed (or before `pip install`), a module-level import
would crash on startup. Lazy import means the trino package is only imported when
`QUERY_ENGINE=trino`, so local dev with SQLite continues to work without trino installed.

## Trino port: 8085 instead of 8080

**Decision**: Run Trino on port 8085 (not the default 8080).

**Rationale**: The FastAPI app must run on port 8080 (CML requirement). Trino's default
port is also 8080. Running both in the same container requires one of them to use a
different port. 8085 was chosen as an obvious Trino-adjacent port with no other conflicts.

## Nessie in-memory backend

**Decision**: Use Nessie with its default in-memory backend (no persistent storage).

**Rationale**: This is a demo. The Iceberg table data (Parquet files) persists in MinIO.
Nessie only stores table metadata (schema, partition spec, snapshot pointer). If Nessie
restarts, `seed_iceberg.py` recreates the catalog entries on next boot. The in-memory
backend eliminates the need for a database (RocksDB, PostgreSQL) inside the container.

## Backwards compatibility: local dev unchanged

**Decision**: All new features are opt-in via environment variables. Default settings
(`QUERY_ENGINE=sqlite`, `DOCS_STORAGE_TYPE=local`) preserve the existing local dev flow
without any changes to `launch_app.sh` or existing tests.

**Rationale**: Developers iterating on the app locally shouldn't need to run Java services.
The Docker image activates the full stack via `ENV QUERY_ENGINE=trino DOCS_STORAGE_TYPE=s3`.
