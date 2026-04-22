"""Database adapter — factory that dispatches to the configured query engine.

Supported engines (settings.query_engine):
  "duckdb" — DuckDB reading local Parquet files (Iceberg-style, no server needed)
  "trino"  — Trino Python client against Iceberg tables on Ozone/S3 (CDP CDW)

All callers (src/sql/executor.py, src/sql/metadata.py, app/api.py) import
from this module and are engine-agnostic.
"""

from __future__ import annotations

from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)


# ── Public API — identical signatures regardless of engine ─────────────────


def execute_read_query(sql: str) -> list[dict]:
    if settings.query_engine == "trino":
        from src.connectors.trino_adapter import execute_read_query as _exec
        return _exec(sql)
    from src.connectors.duckdb_adapter import execute_read_query as _exec
    return _exec(sql)


def get_table_names() -> list[str]:
    if settings.query_engine == "trino":
        from src.connectors.trino_adapter import get_table_names as _fn
        return _fn()
    from src.connectors.duckdb_adapter import get_table_names as _fn
    return _fn()


def get_table_schema(table_name: str) -> list[dict]:
    if settings.query_engine == "trino":
        from src.connectors.trino_adapter import get_table_schema as _fn
        return _fn(table_name)
    from src.connectors.duckdb_adapter import get_table_schema as _fn
    return _fn(table_name)


def get_table_row_count(table_name: str) -> int | None:
    """Return the row count for a table, engine-agnostic."""
    try:
        rows = execute_read_query(f"SELECT COUNT(*) AS n FROM {table_name}")
        return int(rows[0]["n"]) if rows else None
    except Exception as exc:
        logger.warning("get_table_row_count('%s') failed: %s", table_name, exc)
        return None


def get_engine_label() -> str:
    """Return a human-readable label for the active query engine."""
    if settings.query_engine == "trino":
        return f"trino ({settings.trino_host}:{settings.trino_port})"
    return f"duckdb (parquet @ {settings.duckdb_parquet_dir})"
