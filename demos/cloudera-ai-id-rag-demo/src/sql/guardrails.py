"""SQL guardrails — validate generated SQL before execution.

All validation is enforced here before any query reaches the database.
Never execute SQL that has not passed this validator.
"""

from __future__ import annotations

import re

import sqlparse
import sqlparse.tokens as T
from sqlparse.sql import Identifier, IdentifierList, Parenthesis, Where

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

_FROM_JOIN_KEYWORDS = frozenset({
    "FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN",
    "CROSS JOIN", "FULL JOIN", "LEFT OUTER JOIN", "RIGHT OUTER JOIN",
    "FULL OUTER JOIN", "STRAIGHT_JOIN",
})

_CLAUSE_RESET_KEYWORDS = frozenset({
    "WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "UNION",
    "INTERSECT", "EXCEPT", "ON", "SET", "RETURNING",
})

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

    # Block access to unapproved tables — including subqueries and CTEs
    if approved_tables:
        _check_table_access(cleaned, approved_tables)

    return cleaned


def _check_table_access(sql: str, approved_tables: list[str]) -> None:
    """Verify all referenced tables are in the approved list.

    Uses sqlparse AST walking so subqueries, CTEs, and multi-JOIN queries
    are all covered — not just the top-level FROM clause.
    """
    approved_lower = {t.lower() for t in approved_tables}
    cte_names = _extract_cte_names(sql)
    referenced = _extract_table_names(sql)

    for table in referenced:
        if table in cte_names:
            continue  # CTE alias — derived from the query itself, not a real table
        if table not in approved_lower:
            raise SqlGuardrailError(
                f"Akses ke tabel '{table}' tidak diizinkan. "
                f"Tabel yang disetujui: {', '.join(approved_tables)}."
            )


def _extract_cte_names(sql: str) -> set[str]:
    """Extract CTE alias names from WITH clauses so they are not validated as tables."""
    # Match: WITH name AS ( ...
    return {m.lower() for m in re.findall(r"\bWITH\s+(\w+)\s+AS\s*\(", sql, re.IGNORECASE)}


def _extract_table_names(sql: str) -> set[str]:
    """Recursively extract all table names referenced in FROM/JOIN clauses.

    Handles: subqueries, CTEs, multi-JOIN, schema-qualified names (uses leaf name).
    """
    tables: set[str] = set()
    for statement in sqlparse.parse(sql):
        _walk(statement.tokens, tables)
    return tables


def _walk(tokens: list, tables: set[str]) -> None:
    """Walk a token list and collect table names after FROM/JOIN keywords."""
    from_seen = False
    for token in tokens:
        ttype = token.ttype

        # Detect FROM / JOIN keyword — set flag
        if ttype in (T.Keyword, T.Keyword.DML):
            norm = token.normalized.upper()
            if norm in _FROM_JOIN_KEYWORDS:
                from_seen = True
                continue
            if norm in _CLAUSE_RESET_KEYWORDS:
                from_seen = False

        # Skip whitespace/punctuation
        if ttype in (T.Whitespace, T.Newline, T.Punctuation, T.Newline):
            continue

        if from_seen:
            if isinstance(token, Identifier):
                _collect_identifier(token, tables)
                from_seen = False
            elif isinstance(token, IdentifierList):
                for item in token.get_identifiers():
                    if isinstance(item, Identifier):
                        _collect_identifier(item, tables)
                from_seen = False
            elif isinstance(token, Parenthesis):
                # Derived table / subquery — recurse, don't add as table name
                _walk(token.tokens, tables)
                from_seen = False
            elif ttype not in (T.Whitespace, T.Newline):
                from_seen = False

        # Always recurse into compound tokens (catches nested subqueries / CTEs)
        if hasattr(token, "tokens") and not isinstance(token, Identifier):
            _walk(token.tokens, tables)


def _collect_identifier(identifier: Identifier, tables: set[str]) -> None:
    """Add the real table name from an Identifier token (strips alias and schema prefix)."""
    # get_real_name() returns the rightmost name (strips schema prefix like schema.table)
    name = identifier.get_real_name()
    if name:
        tables.add(name.lower())
    # Recurse into any nested parentheses (subquery in FROM)
    for token in identifier.tokens:
        if isinstance(token, Parenthesis):
            _walk(token.tokens, tables)


def ensure_limit(sql: str, max_rows: int) -> str:
    """Append or replace LIMIT clause to enforce max row count."""
    upper = sql.upper()
    if "LIMIT" in upper:
        # Replace existing LIMIT with the configured maximum
        cleaned = re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {max_rows}", sql, flags=re.IGNORECASE)
        return cleaned
    return f"{sql} LIMIT {max_rows}"
