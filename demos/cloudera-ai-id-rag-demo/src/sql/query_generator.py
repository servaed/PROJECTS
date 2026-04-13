"""SQL query generator — converts natural language to validated SQL.

Uses the LLM with a schema-aware prompt. The generated SQL is validated
by the guardrails layer before being handed to the executor.
"""

from __future__ import annotations

from src.llm.inference_client import get_llm_client
from src.llm.prompts import build_sql_generation_prompt
from src.sql.guardrails import validate_sql, ensure_limit, SqlGuardrailError
from src.sql.metadata import build_schema_context, get_approved_tables
from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)


def generate_sql(question: str) -> tuple[str, list[str]]:
    """Generate a validated SQL query from a natural-language question.

    Returns:
        (sql_string, approved_tables)

    Raises:
        SqlGuardrailError if generated SQL fails validation.
        RuntimeError if LLM is unavailable.
    """
    approved = get_approved_tables()
    schema = build_schema_context(approved)
    messages = build_sql_generation_prompt(schema, question, max_rows=settings.sql_max_rows)

    llm = get_llm_client()
    response = llm.chat(messages, temperature=0.0)
    raw_sql = response.content.strip()

    # Strip markdown code fences if the LLM wrapped the query
    if raw_sql.startswith("```"):
        lines = raw_sql.split("\n")
        raw_sql = "\n".join(
            line for line in lines if not line.startswith("```")
        ).strip()

    logger.info("Generated SQL: %s", raw_sql[:200])

    validated = validate_sql(raw_sql, approved_tables=approved)
    final = ensure_limit(validated, settings.sql_max_rows)
    return final, approved
