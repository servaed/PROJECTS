"""Trino adapter — query engine for Iceberg tables on MinIO / Ozone.

Drop-in replacement for db_adapter's SQLAlchemy layer when
settings.query_engine == "trino".  Exposes the same three functions so all
callers (executor, metadata, api) work without changes.
"""

from __future__ import annotations

import trino
import trino.dbapi

from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)


def _connect() -> trino.dbapi.Connection:
    return trino.dbapi.connect(
        host=settings.trino_host,
        port=settings.trino_port,
        user=settings.trino_user,
        catalog=settings.trino_catalog,
        schema=settings.trino_schema,
        http_scheme="http",
    )


def execute_read_query(sql: str) -> list[dict]:
    """Execute a read-only SELECT and return rows as list of dicts."""
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed in execute_read_query.")
    conn = _connect()
    cur = conn.cursor()
    logger.debug("Trino query: %s", sql[:200])
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    logger.debug("Trino returned %d rows", len(rows))
    return rows


def get_table_names() -> list[str]:
    """Return all table names in the configured Trino schema."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(f"SHOW TABLES FROM {settings.trino_catalog}.{settings.trino_schema}")
    return [row[0] for row in cur.fetchall()]


def get_table_schema(table_name: str) -> list[dict]:
    """Return column metadata for a table as list of {'name', 'type'} dicts.

    Compatible with the format expected by src/sql/metadata.py.
    """
    conn = _connect()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT column_name, data_type
        FROM {settings.trino_catalog}.information_schema.columns
        WHERE table_schema = '{settings.trino_schema}'
          AND table_name   = '{table_name}'
        ORDER BY ordinal_position
    """)
    return [{"name": row[0], "type": row[1]} for row in cur.fetchall()]
