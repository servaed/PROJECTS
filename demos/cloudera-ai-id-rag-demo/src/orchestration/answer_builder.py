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

from src.orchestration.router import classify_question, AnswerMode, _strip_thinking
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
    build_data_extraction_prompt,
    get_answer_not_found,
    get_answer_sql_failed,
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
    domain: str = "banking"
    language: str = "id"
    # Populated by stream_synthesis so _chat_sse can include token estimates in the
    # done event without re-building the messages or calling the LLM a second time.
    synthesis_input_chars: int = 0


# ── Gabungan helpers ───────────────────────────────────────────────────────


def _extract_data_question(question: str) -> str:
    """Rephrase a combined (gabungan) question into a pure data/SQL query.

    Combined questions often contain policy-comparison phrasing such as
    "apakah X sudah sesuai target kebijakan Y?" that confuses the SQL generator
    into returning TIDAK_DAPAT_DIJAWAB.  This step strips the policy framing so
    the SQL generator receives a clean aggregation request like "Berapa total X?"

    Falls back to the original question on any error.
    """
    try:
        llm = get_llm_client()
        messages = build_data_extraction_prompt(question)
        response = llm.chat(messages, temperature=0.0, max_tokens=150)
        extracted = _strip_thinking(response.content).strip()
        if extracted and len(extracted) > 5:
            logger.debug(
                "Data extraction: '%s...' → '%s...'",
                question[:50], extracted[:50],
            )
            return extracted
    except Exception as exc:
        logger.warning("Data question extraction failed: %s — using original", exc)
    return question


# ── Phase 1 ────────────────────────────────────────────────────────────────


def prepare_answer(
    question: str,
    history: list[dict] | None = None,
    top_k: int = 5,
    domain: str = "banking",
    domain_tables: list[str] | None = None,
    language: str = "id",
) -> AnswerPrep:
    """Classify the question and retrieve all context. No LLM synthesis here.

    domain         — restricts document retrieval to that domain's chunks.
    domain_tables  — overrides the approved SQL tables for this domain.

    This is fast enough to run inside a spinner so the user sees retrieval
    progress before the (slower) streaming synthesis begins.
    """
    mode = classify_question(question)
    doc_chunks: list[RetrievedChunk] = []
    query_result: QueryResult | None = None
    sql_question = question

    if mode == "gabungan":
        # Extract the pure data component once — reused for both SQL gen and
        # the second retrieval pass below.
        sql_question = _extract_data_question(question)

    if mode in ("dokumen", "gabungan"):
        # Gabungan retrieval uses two passes then deduplicates:
        #   Pass 1 — original question  → retrieves policy/standard chunks
        #   Pass 2 — data-only question → retrieves quantitative metric chunks
        # This ensures both the "target" side (policy) and the "actual" side
        # (data-flavoured text) are represented in the context.
        doc_top_k = top_k + 2 if mode == "gabungan" else top_k
        doc_chunks = retrieve(question, top_k=doc_top_k, domain=domain, language=language)

        if mode == "gabungan" and sql_question != question:
            extra = retrieve(sql_question, top_k=top_k, domain=domain, language=language)
            # Deduplicate by (source_path, chunk_index) — keep first occurrence
            seen: set[tuple] = {(c.source_path, c.chunk_index) for c in doc_chunks}
            for chunk in extra:
                key = (chunk.source_path, chunk.chunk_index)
                if key not in seen:
                    doc_chunks.append(chunk)
                    seen.add(key)
            doc_chunks = doc_chunks[: doc_top_k + top_k]   # cap total

    if mode in ("data", "gabungan"):
        try:
            sql, _ = generate_sql(sql_question, approved_tables=domain_tables)
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
        domain=domain,
        language=language,
    )


# ── Phase 2 ────────────────────────────────────────────────────────────────


def stream_synthesis(prep: AnswerPrep) -> Generator[str, None, None]:
    """Stream LLM answer tokens from a prepared context.

    Yields the fallback string directly (without calling the LLM) when no
    context was retrieved, so the caller always gets a complete response.

    Side-effect: sets prep.synthesis_input_chars so the caller can estimate
    input token usage for the done event.
    """
    fallback = _get_fallback(prep)
    if fallback:
        yield fallback
        return

    messages = _build_messages(prep)
    # Record total character length of messages for input-token estimation.
    # This is set before streaming so the done-event builder can read it even
    # if the stream is cancelled mid-way.
    prep.synthesis_input_chars = sum(len(m.get("content", "")) for m in messages)

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
    """Return a language-appropriate fallback string if no retrieval results are available."""
    lang = prep.language
    if prep.mode == "dokumen" and not prep.doc_chunks:
        return get_answer_not_found(lang)
    if prep.mode == "data" and (prep.query_result is None or not prep.query_result.succeeded):
        return get_answer_sql_failed(lang)
    if prep.mode == "gabungan":
        no_docs = not prep.doc_chunks
        no_data = prep.query_result is None or not prep.query_result.succeeded
        if no_docs and no_data:
            return get_answer_not_found(lang)
    return None


def _build_messages(prep: AnswerPrep) -> list[dict]:
    """Build the LLM prompt messages from retrieved context."""
    lang = prep.language

    if prep.mode == "dokumen":
        context = _format_doc_context(prep.doc_chunks)
        return build_document_prompt(context, prep.question, history=prep.history, language=lang)

    if prep.mode == "data":
        sql_summary = _format_sql_summary(prep.query_result)
        return build_data_prompt(sql_summary, prep.question, history=prep.history, language=lang)

    # gabungan — merge both sources
    doc_context = (
        _format_doc_context(prep.doc_chunks)
        if prep.doc_chunks
        else "_No relevant documents found._"
    )
    sql_summary = (
        _format_sql_summary(prep.query_result)
        if prep.query_result and prep.query_result.succeeded
        else "_No data available._"
    )
    return build_combined_prompt(
        doc_context, sql_summary, prep.question, history=prep.history, language=lang
    )


def _format_doc_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] {c.title}\n{c.text}")
    return "\n\n---\n\n".join(parts)


def _format_sql_summary(result: QueryResult | None) -> str:
    if result is None or result.error or result.is_empty:
        return "No data matching the request."
    header = f"SQL: {result.sql}\n\nResult ({result.row_count} rows):\n"
    return header + result.to_markdown_table(max_rows=20)
