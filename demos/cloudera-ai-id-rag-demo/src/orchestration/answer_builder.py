"""Answer builder — the main orchestration pipeline.

Exposes two APIs:
  1. answer_question()      — single-call blocking (for tests / non-streaming callers)
  2. prepare_answer()       — Phase 1: classify + retrieve (no LLM synthesis)
     stream_synthesis()     — Phase 2: stream LLM tokens from prepared context
     finalize_answer()      — Phase 3: wrap answer text + citations into AnswerResult

The two-phase API lets the Streamlit UI show a spinner during retrieval and then
stream the synthesis token-by-token via st.write_stream.
"""

from __future__ import annotations

from collections.abc import Generator
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
    build_data_prompt,
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


@dataclass
class AnswerPrep:
    """Intermediate retrieval state — ready for LLM synthesis."""
    mode: AnswerMode
    question: str
    doc_chunks: list[RetrievedChunk]
    query_result: QueryResult | None
    history: list[dict]


# ── Phase 1 ────────────────────────────────────────────────────────────────


def prepare_answer(
    question: str,
    history: list[dict] | None = None,
    top_k: int = 5,
) -> AnswerPrep:
    """Classify the question and retrieve all context. No LLM synthesis here.

    This is fast enough to run inside a spinner so the user sees retrieval
    progress before the (slower) streaming synthesis begins.
    """
    mode = classify_question(question)
    doc_chunks: list[RetrievedChunk] = []
    query_result: QueryResult | None = None

    if mode in ("dokumen", "gabungan"):
        doc_chunks = retrieve(question, top_k=top_k)

    if mode in ("data", "gabungan"):
        try:
            sql, _ = generate_sql(question)
            query_result = run_query(sql)
        except SqlGuardrailError as exc:
            logger.warning("SQL guardrail blocked query: %s", exc)
        except Exception as exc:
            logger.error("SQL generation/execution failed: %s", exc)

    return AnswerPrep(
        mode=mode,
        question=question,
        doc_chunks=doc_chunks,
        query_result=query_result,
        history=history or [],
    )


# ── Phase 2 ────────────────────────────────────────────────────────────────


def stream_synthesis(prep: AnswerPrep) -> Generator[str, None, None]:
    """Stream LLM answer tokens from a prepared context.

    Yields the fallback string directly (without calling the LLM) when no
    context was retrieved, so the caller always gets a complete response.
    """
    fallback = _get_fallback(prep)
    if fallback:
        yield fallback
        return

    messages = _build_messages(prep)
    llm = get_llm_client()
    yield from llm.stream_chat(messages)


# ── Phase 3 ────────────────────────────────────────────────────────────────


def finalize_answer(prep: AnswerPrep, answer_text: str) -> AnswerResult:
    """Assemble the final AnswerResult from retrieval prep and streamed text."""
    return AnswerResult(
        answer=answer_text,
        mode=prep.mode,
        doc_citations=build_document_citations(prep.doc_chunks),
        sql_citation=build_sql_citation(prep.query_result),
    )


# ── Single-call blocking API (backwards-compatible) ────────────────────────


def answer_question(
    question: str, history: list[dict] | None = None, top_k: int = 5
) -> AnswerResult:
    """Full orchestration pipeline — classify, retrieve, answer, cite.

    Blocking (non-streaming). Used by tests and any caller that does not
    need token-by-token streaming.
    """
    prep = prepare_answer(question, history=history, top_k=top_k)
    fallback = _get_fallback(prep)
    if fallback:
        return AnswerResult(
            answer=fallback,
            mode=prep.mode,
            doc_citations=[],
            sql_citation=None,
        )

    llm = get_llm_client()
    messages = _build_messages(prep)
    answer = llm.chat(messages).content
    return finalize_answer(prep, answer)


# ── Internal helpers ───────────────────────────────────────────────────────


def _get_fallback(prep: AnswerPrep) -> str | None:
    """Return a fallback string if no retrieval results are available, else None."""
    if prep.mode == "dokumen" and not prep.doc_chunks:
        return ANSWER_NOT_FOUND_ID
    if prep.mode == "data" and (prep.query_result is None or not prep.query_result.succeeded):
        return ANSWER_SQL_FAILED_ID
    if prep.mode == "gabungan":
        no_docs = not prep.doc_chunks
        no_data = prep.query_result is None or not prep.query_result.succeeded
        if no_docs and no_data:
            return ANSWER_NOT_FOUND_ID
    return None


def _build_messages(prep: AnswerPrep) -> list[dict]:
    """Build the LLM prompt messages from retrieved context."""
    if prep.mode == "dokumen":
        context = _format_doc_context(prep.doc_chunks)
        return build_document_prompt(context, prep.question, history=prep.history)

    if prep.mode == "data":
        sql_summary = _format_sql_summary(prep.query_result)
        return build_data_prompt(sql_summary, prep.question, history=prep.history)

    # gabungan — merge both sources
    doc_context = (
        _format_doc_context(prep.doc_chunks)
        if prep.doc_chunks
        else "_Tidak ada dokumen relevan._"
    )
    sql_summary = (
        _format_sql_summary(prep.query_result)
        if prep.query_result and prep.query_result.succeeded
        else "_Data tidak tersedia._"
    )
    return build_combined_prompt(doc_context, sql_summary, prep.question, history=prep.history)


def _format_doc_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] {c.title}\n{c.text}")
    return "\n\n---\n\n".join(parts)


def _format_sql_summary(result: QueryResult | None) -> str:
    if result is None or result.is_empty:
        return "Tidak ada data yang cocok dengan permintaan."
    return result.to_markdown_table(max_rows=20)
