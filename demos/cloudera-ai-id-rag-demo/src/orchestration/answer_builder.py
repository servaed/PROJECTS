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

import concurrent.futures
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
    style: str = "analyst"   # analyst | executive | compliance
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
                "Data extraction: '%s...' -> '%s...'",
                question[:50], extracted[:50],
            )
            return extracted
    except Exception as exc:
        logger.warning("Data question extraction failed: %s — using original", exc)
    return question


# ── SQL helpers ────────────────────────────────────────────────────────────


def _generate_sql_with_retry(
    question: str,
    domain_tables: list[str] | None,
    max_retries: int = 1,
) -> "QueryResult | None":
    """Try SQL generation, retry once with a simplified rephrase on failure.

    On the first attempt the question is used verbatim.  On the retry a brief
    prefix is prepended to nudge the LLM toward a simpler aggregation phrasing,
    which reduces TIDAK_DAPAT_DIJAWAB errors on policy-heavy combined questions.
    """
    attempts = [question]
    if max_retries > 0:
        # Simple rephrase: strip comparative/conditional framing
        rephrased = f"Tampilkan data: {question}" if len(question) > 30 else question
        if rephrased != question:
            attempts.append(rephrased)

    for i, q in enumerate(attempts):
        try:
            sql, _ = generate_sql(q, approved_tables=domain_tables)
            result = run_query(sql)
            if i > 0:
                logger.info("SQL retry %d succeeded for: %.60s", i, question)
            return result
        except SqlGuardrailError as exc:
            logger.warning("SQL guardrail (attempt %d): %s", i + 1, exc)
        except Exception as exc:
            logger.error("SQL generation/execution (attempt %d): %s", i + 1, exc)
    return None


# ── Phase 1 ────────────────────────────────────────────────────────────────


def prepare_answer(
    question: str,
    history: list[dict] | None = None,
    top_k: int = 5,
    domain: str = "banking",
    domain_tables: list[str] | None = None,
    language: str = "id",
    style: str = "analyst",
) -> AnswerPrep:
    """Classify the question and retrieve all context. No LLM synthesis here.

    domain         — restricts document retrieval to that domain's chunks.
    domain_tables  — overrides the approved SQL tables for this domain.

    This is fast enough to run inside a spinner so the user sees retrieval
    progress before the (slower) streaming synthesis begins.
    """
    mode = classify_question(question, history=history)
    doc_chunks: list[RetrievedChunk] = []
    query_result: QueryResult | None = None
    sql_question = question

    if mode == "combined":
        # Extract the pure data component once — reused for both SQL gen and
        # the second retrieval pass below.
        sql_question = _extract_data_question(question)

    if mode == "combined":
        # Run doc retrieval (two-pass) and SQL generation in parallel — they are
        # independent so there is no reason to wait for one before starting the other.
        doc_top_k = top_k + 2

        def _retrieve_docs() -> list[RetrievedChunk]:
            chunks = retrieve(question, top_k=doc_top_k, domain=domain, language=language)
            if sql_question != question:
                extra = retrieve(sql_question, top_k=top_k, domain=domain, language=language)
                seen: set[tuple] = {(c.source_path, c.chunk_index) for c in chunks}
                for chunk in extra:
                    key = (chunk.source_path, chunk.chunk_index)
                    if key not in seen:
                        chunks.append(chunk)
                        seen.add(key)
                chunks = chunks[: doc_top_k + top_k]
            return chunks

        def _run_sql() -> QueryResult | None:
            return _generate_sql_with_retry(sql_question, domain_tables)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            doc_future = pool.submit(_retrieve_docs)
            sql_future = pool.submit(_run_sql)
            doc_chunks   = doc_future.result()
            query_result = sql_future.result()

    elif mode == "document":
        doc_chunks = retrieve(question, top_k=top_k, domain=domain, language=language)

    elif mode == "data":
        query_result = _generate_sql_with_retry(sql_question, domain_tables)

    return AnswerPrep(
        mode=mode,
        question=question,
        doc_chunks=doc_chunks,
        query_result=query_result,
        history=history or [],
        domain=domain,
        language=language,
        style=style,
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

    # Vision: if an image was attached, replace the last user message content
    # with a multimodal content list (OpenAI vision format).
    vision_content = getattr(prep, "_vision_content", None)
    if vision_content:
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                messages[i] = {"role": "user", "content": vision_content}
                break

    prep.synthesis_input_chars = sum(
        len(m["content"]) if isinstance(m.get("content"), str)
        else sum(len(str(c)) for c in m.get("content", []))
        for m in messages
    )

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
    if prep.mode == "document" and not prep.doc_chunks:
        return get_answer_not_found(lang)
    if prep.mode == "data" and (prep.query_result is None or not prep.query_result.succeeded):
        return get_answer_sql_failed(lang)
    if prep.mode == "combined":
        no_docs = not prep.doc_chunks
        no_data = prep.query_result is None or not prep.query_result.succeeded
        if no_docs and no_data:
            return get_answer_not_found(lang)
    return None


def _build_messages(prep: AnswerPrep) -> list[dict]:
    """Build the LLM prompt messages from retrieved context."""
    lang = prep.language

    sty = prep.style

    if prep.mode == "document":
        context = _format_doc_context(prep.doc_chunks)
        return build_document_prompt(context, prep.question, history=prep.history, language=lang, style=sty)

    if prep.mode == "data":
        sql_summary = _format_sql_summary(prep.query_result)
        return build_data_prompt(sql_summary, prep.question, history=prep.history, language=lang, style=sty)

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
        doc_context, sql_summary, prep.question, history=prep.history, language=lang, style=sty
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
