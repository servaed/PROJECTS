"""Database schema discovery — builds schema context for LLM SQL generation.

Only exposes approved tables to prevent the LLM from accessing sensitive tables.
"""

from __future__ import annotations

from src.config.settings import settings
from src.config.logging import get_logger
from src.connectors.db_adapter import get_table_names, get_table_schema

logger = get_logger(__name__)


def get_approved_tables() -> list[str]:
    """Return the intersection of approved tables and tables that actually exist."""
    existing = get_table_names()
    approved = settings.approved_tables

    if not approved:
        # Empty approved list means allow all discovered tables
        return existing

    visible = [t for t in approved if t in existing]
    hidden = [t for t in approved if t not in existing]
    if hidden:
        logger.warning("Approved tables not found in database: %s", hidden)
    return visible


def build_schema_context(tables: list[str] | None = None) -> str:
    """Build a text schema description for approved (or specified) tables.

    This string is injected into the SQL generation prompt so the LLM
    knows what columns exist without having unrestricted schema access.
    """
    if tables is None:
        tables = get_approved_tables()

    if not tables:
        return "Tidak ada tabel yang tersedia."

    lines = []
    for table in tables:
        try:
            columns = get_table_schema(table)
            col_descriptions = ", ".join(
                f"{c['name']} ({c['type']})" for c in columns
            )
            lines.append(f"Tabel: {table}\nKolom: {col_descriptions}")
        except Exception as exc:
            logger.error("Failed to get schema for table '%s': %s", table, exc)

    return "\n\n".join(lines)
