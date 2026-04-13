"""SQL executor — runs validated queries and returns structured results.

Logs every execution with timing. Never executes unvalidated SQL.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import pandas as pd

from src.connectors.db_adapter import execute_read_query
from src.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueryResult:
    sql: str
    rows: list[dict]
    row_count: int
    latency_ms: float
    error: str | None = None
    dataframe: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def succeeded(self) -> bool:
        return self.error is None and self.row_count > 0

    @property
    def is_empty(self) -> bool:
        return self.error is None and self.row_count == 0

    def to_markdown_table(self, max_rows: int = 20) -> str:
        if self.dataframe is None or self.dataframe.empty:
            return "_Tidak ada data._"
        return self.dataframe.head(max_rows).to_markdown(index=False)


def run_query(sql: str) -> QueryResult:
    """Execute a pre-validated SQL query and return structured results.

    This function trusts that the caller has already run the guardrails.
    """
    logger.info("Executing SQL: %s", sql[:200])
    start = time.monotonic()
    try:
        rows = execute_read_query(sql)
        latency = (time.monotonic() - start) * 1000
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        result = QueryResult(
            sql=sql,
            rows=rows,
            row_count=len(rows),
            latency_ms=round(latency, 1),
            dataframe=df,
        )
        logger.info("Query returned %d rows in %.1f ms", result.row_count, latency)
        return result
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        logger.error("Query failed after %.1f ms: %s", latency, exc)
        return QueryResult(
            sql=sql,
            rows=[],
            row_count=0,
            latency_ms=round(latency, 1),
            error=str(exc),
        )
