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


def generate_sql(
    question: str,
    approved_tables: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Generate a validated SQL query from a natural-language question.

    approved_tables — optional domain-specific table list override.
                      Falls back to settings.approved_tables when None.

    Returns:
        (sql_string, approved_tables)

    Raises:
        SqlGuardrailError if generated SQL fails validation.
        RuntimeError if LLM is unavailable.
    """
    approved = approved_tables if approved_tables is not None else get_approved_tables()
    schema = build_schema_context(approved)
    messages = build_sql_generation_prompt(schema, question, max_rows=settings.sql_max_rows)

    llm = get_llm_client()
    response = llm.chat(messages, temperature=0.0)
    raw_sql = response.content.strip()

    # Strip markdown code fences if the LLM wrapped the query.
    # Handles: ```sql\n...\n```, ```\n...\n```, and inline ` backtick wrapping.
    if raw_sql.startswith("```"):
        lines = raw_sql.splitlines()
        # Drop the opening fence (```sql or ```) and closing fence (```)
        inner = [ln for ln in lines if not ln.strip().startswith("```")]
        extracted = "\n".join(inner).strip()
        if extracted:
            logger.debug("Stripped markdown fence from generated SQL")
            raw_sql = extracted
        else:
            logger.warning("Markdown fence stripping produced empty SQL — using raw response")
    elif raw_sql.startswith("`") and raw_sql.endswith("`"):
        raw_sql = raw_sql.strip("`").strip()

    # Strip <think>...</think> blocks emitted by reasoning models before parsing.
    import re as _re
    raw_sql = _re.sub(r"<think>.*?</think>", "", raw_sql, flags=_re.DOTALL | _re.IGNORECASE).strip()

    logger.info("Generated SQL: %s", raw_sql[:200])

    # Explicit "cannot answer" signal from the LLM — raise before guardrail validation
    # so the caller gets a clear SqlGuardrailError rather than a generic parse error.
    if "TIDAK_DAPAT_DIJAWAB" in raw_sql.upper():
        raise SqlGuardrailError(
            "LLM indicated the question cannot be answered with the available schema"
        )

    validated = validate_sql(raw_sql, approved_tables=approved)
    final = ensure_limit(validated, settings.sql_max_rows)
    return final, approved
