# Session — 2026-04-22 — English Migration, Eval Fix, Project Cleanup

## Goals

1. Complete English migration: table names, column names, data values
2. Fix eval_all.py language parameter bug (Q22 English fallback)
3. Fix Q22 LLM synthesis ("no data" despite 11-row result)
4. UI: fix remaining Indonesian strings in index.html
5. Tidy project: remove Docker/Iceberg/Nessie artifacts
6. Update README with Cloudera technology architecture
7. Update CLAUDE.md with current state

## Changes Made

### Q22 LLM Synthesis Fix

Root cause: `_format_sql_summary()` returned a markdown table with aggregated column names
(`subscriber_count`) but no context about what the query selected. The LLM saw a table
but couldn't relate `subscriber_count` to "subscribers with churn_risk_score > 70" and
reported "no data."

Fix: prefix the result table with the SQL query text:
```python
def _format_sql_summary(result: QueryResult | None) -> str:
    if result is None or result.error or result.is_empty:
        return "No data matching the request."
    header = f"SQL: {result.sql}\n\nResult ({result.row_count} rows):\n"
    return header + result.to_markdown_table(max_rows=20)
```

### English Migration (completed)

- All 9 SQLite tables renamed: msme_credit, customer, branch, subscriber, data_usage,
  network, resident, regional_budget, public_service
- All column names in English
- Status/segment values translated: Active, Inactive, Micro, Small, Medium, Prepaid,
  Postpaid, Corporate, High, Critical, Optimal
- OJK credit quality codes and Indonesian govt agency names kept in Indonesian
- metadata.py, prompts.py, settings.py, conftest.py, test_sql_guardrails.py all updated

### eval_all.py Fix

`ask()` was missing the `language` parameter in the API payload. English questions were
answered in Indonesian. Fixed to pass `language=lang`.

### UI Fixes

- "Tampilkan semua N sumber" / "Sembunyikan" → "Show all N sources" / "Hide"
- `_INDEX_HTML` startup cache removed → `GET /` reads index.html from disk per request
- Documents health check: `iterdir()` → `rglob("*")` for subdirectory counting

### Project Cleanup

Files deleted: cloudera-ai-rag-write_docs.py, test_sse_runner.py,
src/connectors/hdfs_adapter.py, data/manifests/sample_manifest.json

Settings cleanup: removed `hdfs` from docs_storage_type, removed hdfs_url/hdfs_user fields.

### Documentation

- README.md: complete rewrite showing Trino + Ozone as primary architecture
- CLAUDE.md: updated table names, test count (86), document count (14), connectors desc

## Evaluation Results

36/36 bilingual questions passing after all fixes.
86/86 unit tests passing.

---

## Part 2 — SQLite → DuckDB Migration + Explorer/Upload Pages

Continued in the same day's work session.

### SQLite → DuckDB

Replaced SQLAlchemy/SQLite with DuckDB reading local Parquet files. Motivation: align
local dev SQL dialect with production Trino (both use standard SQL on Parquet), eliminate
the SQLAlchemy dependency, simplify the connector stack.

- `src/connectors/duckdb_adapter.py` (new): DuckDB in-process engine, one view per .parquet,
  thread-safe singleton connection.
- `src/connectors/db_adapter.py`: default engine `"duckdb"`; added `get_table_row_count()`
  and `get_engine_label()` used by health endpoints.
- `data/sample_tables/seed_parquet.py` (new): seeds 9 Parquet files from `sample_data.py`
  using pandas + pyarrow. Replaces `seed_database.py`.
- `src/config/settings.py`: `query_engine` default → `"duckdb"`; added `duckdb_parquet_dir`;
  removed `database_url`.
- `requirements.txt`: added `duckdb>=1.1.0`, `python-multipart>=0.0.9`; dropped `SQLAlchemy`.
- `deployment/launch_app.sh` step 3: seeds Parquet via `seed_parquet.py`.

### SQL Explorer + Document Upload Pages

- `app/static/explorer.html` (new): SQL query editor with schema browser, dark mode.
- `app/static/upload.html` (new): document upload with domain/language tagging.
- `app/api.py`: added `GET /explorer`, `GET /upload`, `GET /api/sql/tables`,
  `POST /api/sql/query`, `GET /api/docs/list`, `POST /api/docs/upload`.
- `/api/setup` database section now shows per-table row counts + engine label.

### Bilingual Documents Added

7 English counterpart documents added under `data/sample_docs/{domain}/`:
`sme_credit_policy_en.txt`, `kyc_aml_procedures_en.txt`, `ojk_regulatory_summary_en.txt`,
`customer_service_sla_policy_en.txt`, `spectrum_network_operations_en.txt`,
`public_service_standard_en.txt`, `municipal_budget_regulation_en.txt`.

`document_loader.py`: added `_infer_language()` helper; `RawDocument.language` field
propagated to FAISS metadata so retrieval filters by language.

### All Docs Updated (skills, DEPLOYMENT.md, app_config.md, etc.)

All references to SQLite, seed_database.py, DATABASE_URL, HDFS adapter updated to
DuckDB/Parquet equivalents across CLAUDE.md, README.md, DEPLOYMENT.md, app_config.md,
cloudera_ai_application.md, PRESALES_CHECKLIST.md, all skills SKILL.md files.

## Next Steps

- Consider Trino integration test (DuckDB connector tested, Trino only validated via SQL parity)
- Consider adding `GET /api/docs/{name}` to serve individual document content for the explorer
- `/api/status` document count is available via FilesAdapter — could add to sidebar indicator
