"""SQL guardrails — validate generated SQL before execution.

All validation is enforced here before any query reaches the database.
Never execute SQL that has not passed this validator.
"""

from __future__ import annotations

import re

# Blocked SQL keywords — block destructive and data-modifying statements
BLOCKED_PATTERNS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bCREATE\b",
    r"\bREPLACE\b",
    r"\bMERGE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bCALL\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bPRAGMA\b",
]

MULTI_STATEMENT_PATTERN = re.compile(r";\s*\S")
CANNOT_ANSWER_SENTINEL = "TIDAK_DAPAT_DIJAWAB"


class SqlGuardrailError(ValueError):
    """Raised when a query fails guardrail validation."""


def validate_sql(sql: str, approved_tables: list[str] | None = None) -> str:
    """Validate and normalize a SQL string.

    Returns the cleaned SQL if valid.
    Raises SqlGuardrailError with a Bahasa Indonesia message if not.
    """
    if not sql or not sql.strip():
        raise SqlGuardrailError("Query SQL kosong.")

    cleaned = sql.strip().rstrip(";")

    # Reject sentinel returned by LLM when it can't answer
    if cleaned.upper() == CANNOT_ANSWER_SENTINEL:
        raise SqlGuardrailError("Model mengembalikan: pertanyaan tidak dapat dijawab dengan skema yang ada.")

    # Block multi-statement execution
    if MULTI_STATEMENT_PATTERN.search(cleaned):
        raise SqlGuardrailError("Multi-statement SQL tidak diizinkan.")

    upper = cleaned.upper()

    # Must start with SELECT
    if not upper.lstrip().startswith("SELECT"):
        raise SqlGuardrailError("Hanya query SELECT yang diizinkan.")

    # Block destructive keywords
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, upper):
            keyword = pattern.strip(r"\b")
            raise SqlGuardrailError(f"Keyword SQL '{keyword}' tidak diizinkan.")

    # Block subquery bypasses using unapproved tables
    if approved_tables:
        _check_table_access(cleaned, approved_tables)

    return cleaned


def _check_table_access(sql: str, approved_tables: list[str]) -> None:
    """Verify all referenced tables are in the approved list."""
    # Extract identifiers after FROM and JOIN keywords
    candidates = re.findall(r"(?:FROM|JOIN)\s+([`\"\[]?\w+[`\"\]]?)", sql, re.IGNORECASE)
    for candidate in candidates:
        table = candidate.strip("`\"[]")
        if table.lower() not in [t.lower() for t in approved_tables]:
            raise SqlGuardrailError(
                f"Akses ke tabel '{table}' tidak diizinkan. "
                f"Tabel yang disetujui: {', '.join(approved_tables)}."
            )


def ensure_limit(sql: str, max_rows: int) -> str:
    """Append or replace LIMIT clause to enforce max row count."""
    upper = sql.upper()
    if "LIMIT" in upper:
        # Replace existing LIMIT with the configured maximum
        cleaned = re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {max_rows}", sql, flags=re.IGNORECASE)
        return cleaned
    return f"{sql} LIMIT {max_rows}"
