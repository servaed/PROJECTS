"""Tests for SQL guardrails — validate_sql, ensure_limit, and table access control.

These tests do not require a database or LLM — they only exercise the guardrail
logic in src/sql/guardrails.py. Run with: pytest tests/test_sql_guardrails.py -v
"""

import pytest
from src.sql.guardrails import validate_sql, ensure_limit, SqlGuardrailError

APPROVED = ["msme_credit", "customer", "branch"]


# ── validate_sql: basic acceptance ────────────────────────────────────────

def test_valid_select_passes():
    sql = validate_sql("SELECT * FROM msme_credit", approved_tables=APPROVED)
    assert sql == "SELECT * FROM msme_credit"


def test_trailing_semicolon_stripped():
    sql = validate_sql("SELECT id FROM customer;", approved_tables=APPROVED)
    assert not sql.endswith(";")


def test_whitespace_trimmed():
    sql = validate_sql("  SELECT id FROM branch  ", approved_tables=APPROVED)
    assert sql == sql.strip()


# ── validate_sql: blocked statements ──────────────────────────────────────

@pytest.mark.parametrize("bad_sql", [
    "DROP TABLE customer",
    "DELETE FROM customer WHERE id=1",
    "UPDATE msme_credit SET outstanding=0",
    "INSERT INTO customer VALUES (1, 'x')",
    "ALTER TABLE customer ADD COLUMN x INT",
    "TRUNCATE TABLE customer",
    "CREATE TABLE evil (x INT)",
    "EXEC xp_cmdshell('whoami')",
    "PRAGMA table_info(customer)",
    "ATTACH DATABASE '/etc/passwd' AS p",
])
def test_destructive_keywords_blocked(bad_sql):
    with pytest.raises(SqlGuardrailError):
        validate_sql(bad_sql)


def test_non_select_blocked():
    with pytest.raises(SqlGuardrailError, match="SELECT"):
        validate_sql("SHOW TABLES")


def test_empty_sql_blocked():
    with pytest.raises(SqlGuardrailError):
        validate_sql("")


def test_whitespace_only_blocked():
    with pytest.raises(SqlGuardrailError):
        validate_sql("   ")


def test_multi_statement_blocked():
    with pytest.raises(SqlGuardrailError):
        validate_sql("SELECT 1; DROP TABLE customer", approved_tables=APPROVED)


def test_sentinel_blocked():
    with pytest.raises(SqlGuardrailError):
        validate_sql("TIDAK_DAPAT_DIJAWAB")


# ── validate_sql: table access control ────────────────────────────────────

def test_approved_table_passes():
    validate_sql("SELECT * FROM msme_credit LIMIT 10", approved_tables=APPROVED)


def test_unapproved_table_blocked():
    with pytest.raises(SqlGuardrailError, match="not permitted"):
        validate_sql("SELECT * FROM secret_table", approved_tables=APPROVED)


def test_case_insensitive_table_check():
    validate_sql("SELECT * FROM MSME_CREDIT", approved_tables=APPROVED)


def test_join_approved_table_passes():
    sql = "SELECT c.id, c.name FROM msme_credit m JOIN customer c ON m.customer_id = c.id"
    validate_sql(sql, approved_tables=APPROVED)


def test_join_unapproved_table_blocked():
    sql = "SELECT * FROM msme_credit JOIN hidden_table ON msme_credit.id = hidden_table.id"
    with pytest.raises(SqlGuardrailError):
        validate_sql(sql, approved_tables=APPROVED)


def test_subquery_unapproved_table_blocked():
    """Subquery bypass must be caught — this was the regex vulnerability."""
    sql = "SELECT * FROM (SELECT * FROM hidden_table) AS t"
    with pytest.raises(SqlGuardrailError):
        validate_sql(sql, approved_tables=APPROVED)


def test_cte_unapproved_inner_table_blocked():
    """CTE referencing a hidden table in its body must be caught."""
    sql = (
        "WITH cte AS (SELECT * FROM hidden_table) "
        "SELECT * FROM cte"
    )
    with pytest.raises(SqlGuardrailError):
        validate_sql(sql, approved_tables=APPROVED)


def test_cte_with_approved_table_passes():
    """CTE over an approved table should be allowed."""
    sql = (
        "WITH top_loans AS (SELECT * FROM msme_credit ORDER BY outstanding DESC LIMIT 10) "
        "SELECT * FROM top_loans"
    )
    validate_sql(sql, approved_tables=APPROVED)


def test_schema_qualified_name_uses_leaf():
    """schema.table — the leaf name is validated against the approved list."""
    sql = "SELECT * FROM public.msme_credit"
    validate_sql(sql, approved_tables=APPROVED)


def test_schema_qualified_unapproved_blocked():
    sql = "SELECT * FROM public.hidden_table"
    with pytest.raises(SqlGuardrailError):
        validate_sql(sql, approved_tables=APPROVED)


# ── ensure_limit ──────────────────────────────────────────────────────────

def test_ensure_limit_appends_when_missing():
    sql = ensure_limit("SELECT * FROM msme_credit", 500)
    assert "LIMIT 500" in sql.upper()


def test_ensure_limit_replaces_existing():
    sql = ensure_limit("SELECT * FROM msme_credit LIMIT 9999", 500)
    assert "LIMIT 500" in sql.upper()
    assert "9999" not in sql


def test_ensure_limit_case_insensitive_replacement():
    sql = ensure_limit("SELECT * FROM msme_credit limit 100", 200)
    assert "200" in sql
    assert "100" not in sql
