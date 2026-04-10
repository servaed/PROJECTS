"""Database adapter — SQLAlchemy-based read-only connection.

Wraps SQLAlchemy engine creation so callers never touch connection strings
directly. All access goes through this adapter for logging and safety.
"""

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return a shared SQLAlchemy engine (lazy init)."""
    global _engine
    if _engine is None:
        logger.info("Creating database engine: %s", _masked_url())
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def execute_read_query(sql: str) -> list[dict]:
    """Execute a read-only SQL query and return rows as a list of dicts.

    Raises ValueError if the statement is not a plain SELECT.
    """
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = [dict(row._mapping) for row in result]
    return rows


def get_table_names() -> list[str]:
    """Return all table names visible in the database."""
    engine = get_engine()
    inspector = inspect(engine)
    return inspector.get_table_names()


def get_table_schema(table_name: str) -> list[dict]:
    """Return column metadata for a given table."""
    engine = get_engine()
    inspector = inspect(engine)
    return inspector.get_columns(table_name)


def _masked_url() -> str:
    """Return database URL with password masked for safe logging."""
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
