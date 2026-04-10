"""Tests for SQL guardrails — the most critical security layer."""

import pytest
from src.sql.guardrails import validate_sql, ensure_limit, SqlGuardrailError

APPROVED = ["kredit_umkm", "nasabah", "cabang"]


# ── Valid queries ─────────────────────────────────────────────────────────

def test_valid_select_passes():
    sql = "SELECT * FROM kredit_umkm LIMIT 10"
    result = validate_sql(sql, APPROVED)
    assert result == sql


def test_trailing_semicolon_stripped():
    sql = "SELECT id FROM nasabah;"
    result = validate_sql(sql, APPROVED)
    assert result == "SELECT id FROM nasabah"


def test_complex_valid_select():
    sql = "SELECT wilayah, SUM(outstanding) FROM kredit_umkm WHERE wilayah = 'Jakarta' GROUP BY wilayah LIMIT 100"
    result = validate_sql(sql, APPROVED)
    assert "SELECT" in result


# ── Blocked keywords ──────────────────────────────────────────────────────

@pytest.mark.parametrize("sql", [
    "DROP TABLE kredit_umkm",
    "DELETE FROM nasabah WHERE id = 1",
    "UPDATE kredit_umkm SET outstanding = 0",
    "INSERT INTO nasabah VALUES (1, 'Test')",
    "ALTER TABLE kredit_umkm ADD COLUMN foo TEXT",
    "TRUNCATE TABLE cabang",
    "CREATE TABLE evil (id INT)",
])
def test_blocked_keywords_rejected(sql):
    with pytest.raises(SqlGuardrailError):
        validate_sql(sql)


# ── Non-SELECT statements ─────────────────────────────────────────────────

def test_non_select_rejected():
    with pytest.raises(SqlGuardrailError, match="SELECT"):
        validate_sql("SHOW TABLES")


def test_empty_sql_rejected():
    with pytest.raises(SqlGuardrailError, match="kosong"):
        validate_sql("")


def test_whitespace_only_rejected():
    with pytest.raises(SqlGuardrailError):
        validate_sql("   ")


# ── Multi-statement ───────────────────────────────────────────────────────

def test_multi_statement_rejected():
    with pytest.raises(SqlGuardrailError, match="Multi-statement"):
        validate_sql("SELECT 1; DROP TABLE kredit_umkm")


# ── Table access control ──────────────────────────────────────────────────

def test_unapproved_table_rejected():
    with pytest.raises(SqlGuardrailError, match="tidak diizinkan"):
        validate_sql("SELECT * FROM rahasia_nasabah", approved_tables=APPROVED)


def test_approved_table_allowed():
    sql = "SELECT * FROM nasabah LIMIT 5"
    result = validate_sql(sql, approved_tables=APPROVED)
    assert result is not None


# ── LLM cannot-answer sentinel ────────────────────────────────────────────

def test_sentinel_rejected():
    with pytest.raises(SqlGuardrailError):
        validate_sql("TIDAK_DAPAT_DIJAWAB")


# ── ensure_limit ─────────────────────────────────────────────────────────

def test_ensure_limit_adds_limit():
    sql = "SELECT * FROM kredit_umkm"
    result = ensure_limit(sql, 500)
    assert "LIMIT 500" in result


def test_ensure_limit_replaces_existing():
    sql = "SELECT * FROM kredit_umkm LIMIT 9999"
    result = ensure_limit(sql, 500)
    assert "LIMIT 500" in result
    assert "9999" not in result
