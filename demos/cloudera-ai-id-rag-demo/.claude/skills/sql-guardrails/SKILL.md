---
name: sql-guardrails
description: Safe SQL generation rules, metadata-first schema inspection, read-only discipline, limits, timeouts, and blocked keywords.
---

# Skill: SQL Guardrails

## Non-negotiable Rules

1. **Read-only only.** Every SQL query must start with `SELECT`. Any other statement is rejected.
2. **Blocked keywords** — rejected regardless of context:
   `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `CREATE`, `REPLACE`, `MERGE`,
   `EXEC`, `EXECUTE`, `CALL`, `GRANT`, `REVOKE`, `ATTACH`, `DETACH`, `PRAGMA`
3. **No multi-statement execution.** A `;` followed by more SQL is blocked.
4. **Table allowlist.** Only tables in `SQL_APPROVED_TABLES` are accessible. Queries referencing other tables are rejected.
5. **Row limit enforced.** `ensure_limit()` always appends or replaces `LIMIT` to respect `SQL_MAX_ROWS`.

## Schema-First Approach

The LLM never sees the full database. Only `get_approved_tables()` + `build_schema_context()` results are injected into the prompt. This prevents the LLM from discovering or referencing sensitive tables.

## Validation Flow

```
generate_sql(question)
  → build_schema_context(approved_tables)
  → LLM generates SQL
  → strip markdown fences
  → validate_sql(sql, approved_tables)  ← raises SqlGuardrailError if invalid
  → ensure_limit(sql, max_rows)
  → run_query(sql)
```

Never call `run_query()` with SQL that has not passed `validate_sql()`.

## LLM Cannot-Answer Sentinel

If the LLM returns `TIDAK_DAPAT_DIJAWAB`, `validate_sql()` raises `SqlGuardrailError`.
The orchestrator catches this and returns `get_answer_sql_failed(language)` to the user
(localised: Bahasa Indonesia or English depending on the chat request language).

## Error Message Language

Since the 2026-04-22 English migration all `SqlGuardrailError` messages are in English
(e.g. "Only SELECT queries are permitted."). These are internal error strings passed to
the orchestrator, not shown directly to end users.

## Logging

Every executed query is logged with: SQL text, timestamp, row count, and latency (ms).
This is done in `src/sql/executor.py` automatically.

## Adding New Approved Tables

Update `SQL_APPROVED_TABLES` in the `.env` file or environment variable.
Current demo tables (English names):
```
SQL_APPROVED_TABLES=msme_credit,customer,branch,subscriber,data_usage,network,resident,regional_budget,public_service
```
Never add tables to the allowlist without confirming they contain only data the demo is authorized to expose.

## DuckDB vs Trino

The guardrails work identically on both engines — same SQL dialect for the queries this
app generates (SELECT, GROUP BY, WHERE, LIMIT, JOIN). The approved-table check runs before
query execution and is engine-agnostic.
