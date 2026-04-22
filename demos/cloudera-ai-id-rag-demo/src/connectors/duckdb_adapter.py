"""DuckDB adapter — queries Parquet files as virtual Iceberg-style tables.

Registers each .parquet file in DUCKDB_PARQUET_DIR as a DuckDB in-memory
view so it appears as a named table to the SQL generator and guardrails.
The connection is rebuilt from Parquet on startup — no separate DB process needed.

Swap story:
  Local dev   : QUERY_ENGINE=duckdb  (Parquet files in data/parquet/)
  Production  : QUERY_ENGINE=trino   (same Parquet/Iceberg files in Ozone/S3)

The SQL your LLM generates works identically on both — DuckDB and Trino share
the same SQL dialect for the queries this app generates (SELECT, GROUP BY,
WHERE, LIMIT, JOIN).
"""

from __future__ import annotations

import pathlib
import threading

from src.config.logging import get_logger
from src.config.settings import settings

logger = get_logger(__name__)

_conn = None
_lock = threading.Lock()


def _get_connection():
    global _conn
    if _conn is not None:
        return _conn
    with _lock:
        if _conn is None:
            _conn = _build_connection()
    return _conn


def _build_connection():
    import duckdb

    parquet_dir = pathlib.Path(settings.duckdb_parquet_dir).resolve()
    conn = duckdb.connect(":memory:")

    parquet_files = sorted(parquet_dir.glob("*.parquet"))
    if not parquet_files:
        logger.warning(
            "DuckDB: no Parquet files found in %s — run: python data/sample_tables/seed_parquet.py",
            parquet_dir,
        )
        return conn

    for pf in parquet_files:
        table_name = pf.stem
        # Use forward slashes — DuckDB on Windows accepts posix paths inside SQL strings
        safe_path = pf.as_posix()
        conn.execute(
            f'CREATE OR REPLACE VIEW "{table_name}" AS SELECT * FROM read_parquet(\'{safe_path}\')'
        )
        logger.info("DuckDB: view '%s' <- %s", table_name, pf.name)

    logger.info("DuckDB: %d views registered from %s", len(parquet_files), parquet_dir)
    return conn


def get_table_names() -> list[str]:
    conn = _get_connection()
    rows = conn.execute("SHOW TABLES").fetchall()
    return [r[0] for r in rows]


def get_table_schema(table_name: str) -> list[dict]:
    """Return column metadata as [{name, type}, ...].

    DuckDB DESCRIBE returns: column_name, column_type, null, key, default, extra.
    """
    conn = _get_connection()
    rows = conn.execute(f'DESCRIBE "{table_name}"').fetchall()
    return [{"name": r[0], "type": r[1]} for r in rows]


def execute_read_query(sql: str) -> list[dict]:
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed in execute_read_query.")
    conn = _get_connection()
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def get_parquet_dir() -> pathlib.Path:
    """Return the resolved Parquet directory path (used by health checks)."""
    return pathlib.Path(settings.duckdb_parquet_dir).resolve()
