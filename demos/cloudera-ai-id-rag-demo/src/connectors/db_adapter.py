"""Database adapter — factory that dispatches to the configured query engine.

Supported engines (settings.query_engine):
  "sqlite" — SQLAlchemy + SQLite (local dev default, backwards-compatible)
  "trino"  — Trino Python client against Iceberg tables on MinIO / Ozone

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
    return _sqlite_execute(sql)


def get_table_names() -> list[str]:
    if settings.query_engine == "trino":
        from src.connectors.trino_adapter import get_table_names as _fn
        return _fn()
    return _sqlite_table_names()


def get_table_schema(table_name: str) -> list[dict]:
    if settings.query_engine == "trino":
        from src.connectors.trino_adapter import get_table_schema as _fn
        return _fn(table_name)
    return _sqlite_table_schema(table_name)


# ── SQLite / SQLAlchemy implementation (unchanged from original) ───────────

from sqlalchemy import create_engine, text, inspect  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        logger.info("Creating SQLite engine: %s", _masked_url())
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


# Public alias kept for callers (e.g. app/api.py setup health check) that
# need direct engine access for SQLite-specific introspection.
def get_engine() -> Engine:
    return _get_engine()


def _sqlite_execute(sql: str) -> list[dict]:
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed in execute_read_query.")
    engine = _get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        return [dict(row._mapping) for row in result]


def _sqlite_table_names() -> list[str]:
    engine = _get_engine()
    return inspect(engine).get_table_names()


def _sqlite_table_schema(table_name: str) -> list[dict]:
    engine = _get_engine()
    cols = inspect(engine).get_columns(table_name)
    return [{"name": c["name"], "type": str(c["type"])} for c in cols]


def _masked_url() -> str:
    url = settings.database_url
    if "@" in url:
        parts = url.split("@")
        cred_part = parts[0].split("://", 1)
        if len(cred_part) == 2:
            scheme = cred_part[0]
            credentials = cred_part[1].rsplit(":", 1)
            if len(credentials) == 2:
                return f"{scheme}://{credentials[0]}:***@{'@'.join(parts[1:])}"
    return url
