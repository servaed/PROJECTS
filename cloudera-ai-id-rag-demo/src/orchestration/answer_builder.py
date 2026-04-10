"""Answer builder — the main orchestration pipeline.

Runs the full flow for a user question:
  1. Classify question mode
  2. Retrieve documents and/or run SQL as needed
  3. Call LLM to synthesize a Bahasa Indonesia answer
  4. Assemble citations and query trace
  5. Return a structured AnswerResult for the UI
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.orchestration.router import classify_question, AnswerMode
from src.orchestration.citations import (
    build_document_citations,
    build_sql_citation,
    DocumentCitation,
    SqlCitation,
)
from src.retrieval.retriever import retrieve, RetrievedChunk
from src.sql.query_generator import generate_sql
from src.sql.executor import run_query, QueryResult
from src.sql.guardrails import SqlGuardrailError
from src.llm.inference_client import get_llm_client
from src.llm.prompts import (
    build_document_prompt,
    build_combined_prompt,
    ANSWER_NOT_FOUND_ID,
    ANSWER_SQL_FAILED_ID,
)
from src.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AnswerResult:
    answer: str
    mode: AnswerMode
    doc_citations: list[DocumentCitation] = field(default_factory=list)
    sql_citation: SqlCitation | None = None
    error: str | None = None

    @property
    def has_sources(self) -> bool:
        return bool(self.doc_citations) or self.sql_citation is not None


def answer_question(question: str, top_k: int = 5) -> AnswerResult:
    """Full orchestration pipeline — classify, retrieve, answer, cite."""
    mode = classify_question(question)
    llm = get_llm_client()

    doc_chunks: list[RetrievedChunk] = []
    query_result: QueryResult | None = None

    # ── Document retrieval ──────────────────────────────────────────────
    if mode in ("dokumen", "gabungan"):
        doc_chunks = retrieve(question, top_k=top_k)

    # ── SQL retrieval ───────────────────────────────────────────────────
    if mode in ("data", "gabungan"):
        try:
            sql, _ = generate_sql(question)
            query_result = run_query(sql)
        except SqlGuardrailError as exc:
            logger.warning("SQL guardrail blocked query: %s", exc)
            query_result = None
        except Exception as exc:
            logger.error("SQL generation/execution failed: %s", exc)
            query_result = None

    # ── Answer synthesis ────────────────────────────────────────────────
    answer = _synthesize(mode, question, doc_chunks, query_result, llm)

    return AnswerResult(
        answer=answer,
        mode=mode,
        doc_citations=build_document_citations(doc_chunks),
        sql_citation=build_sql_citation(query_result),
    )


def _synthesize(
    mode: AnswerMode,
    question: str,
    doc_chunks: list[RetrievedChunk],
    query_result: QueryResult | None,
    llm,
) -> str:
    if mode == "dokumen":
        if not doc_chunks:
            return ANSWER_NOT_FOUND_ID
        context = _format_doc_context(doc_chunks)
        messages = build_document_prompt(context, question)
        return llm.chat(messages).content

    if mode == "data":
        if query_result is None or not query_result.succeeded:
            return ANSWER_SQL_FAILED_ID
        sql_summary = _format_sql_summary(query_result)
        messages = build_document_prompt(sql_summary, question)
        return llm.chat(messages).content

    # gabungan
    if not doc_chunks and (query_result is None or not query_result.succeeded):
        return ANSWER_NOT_FOUND_ID
    doc_context = _format_doc_context(doc_chunks) if doc_chunks else "_Tidak ada dokumen relevan._"
    sql_summary = _format_sql_summary(query_result) if query_result and query_result.succeeded else "_Data tidak tersedia._"
    messages = build_combined_prompt(doc_context, sql_summary, question)
    return llm.chat(messages).content


def _format_doc_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] {c.title}\n{c.text}")
    return "\n\n---\n\n".join(parts)


def _format_sql_summary(result: QueryResult) -> str:
    if result.is_empty:
        return "Tidak ada data yang cocok dengan permintaan."
    return result.to_markdown_table(max_rows=20)
