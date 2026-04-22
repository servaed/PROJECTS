# Decision — 2026-04-22 — Replace SQLite with DuckDB + Parquet

## Context

The demo was using SQLite + SQLAlchemy for the local dev data layer. As part of the
full English migration (table names, column names, data values), the opportunity arose
to also fix the longer-term alignment problem: the local dev SQL dialect (SQLite) and
production (Trino) were different enough to require separate testing.

## Decision

Replace SQLite + SQLAlchemy with **DuckDB reading local Parquet files**.

## Reasoning

1. **SQL dialect parity with Trino.** DuckDB and Trino both use standard SQL on Parquet
   files. The LLM-generated SELECT/GROUP BY/JOIN/LIMIT queries work identically on both
   engines. Testing DuckDB locally gives high confidence the same SQL will work on CDW.

2. **No server required.** DuckDB is in-process (no daemon, no port, no Docker). Simpler
   than running a Trino container locally and easier to deploy on CML where no auxiliary
   services are available.

3. **Parquet is the production file format.** Iceberg on Ozone uses Parquet data files.
   By reading local Parquet in dev, the data format is identical to production — only the
   catalog/metadata layer differs.

4. **Remove SQLAlchemy dependency.** SQLAlchemy is a large dependency (~25 MB) that
   added no value beyond the SQLite connection. DuckDB's Python API is simpler and lighter.

5. **Seed script simplifies.** `seed_parquet.py` is simpler than `seed_database.py` —
   no CREATE TABLE, no INSERT loop, just DataFrame.to_parquet().

## Tradeoffs

- **No SQLite fallback.** Anyone who had `QUERY_ENGINE=sqlite` in their `.env` will need
  to update to `QUERY_ENGINE=duckdb`. This is a breaking change for existing deployments.
- **Requires pandas + pyarrow for seeding.** These were already in requirements.txt.
- **DuckDB in-process** means no persistent connection between sessions — the DuckDB
  connection is rebuilt from Parquet on startup. This is fine because Parquet files are
  the source of truth and the connection is fast to rebuild.

## Migration Path

1. Run `python data/sample_tables/seed_parquet.py` to create `data/parquet/*.parquet`
2. Set `QUERY_ENGINE=duckdb` (now the default — no action needed for new deployments)
3. Remove `DATABASE_URL` from any `.env.local` overrides (no longer read)
