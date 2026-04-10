"""UI components for the Streamlit chat application.

Renders: chat panel, source panel, SQL trace, mode badge, and disclaimer.
"""

from __future__ import annotations

import streamlit as st
from src.orchestration.answer_builder import AnswerResult
from src.utils.language import mode_label, mode_badge_color

SAMPLE_PROMPTS = [
    "Jelaskan ketentuan restrukturisasi kredit berdasarkan dokumen kebijakan terbaru.",
    "Berapa total outstanding pinjaman UMKM wilayah Jakarta pada Maret 2026?",
    "Apakah tren outstanding tersebut sejalan dengan kebijakan ekspansi UMKM dalam dokumen strategi?",
    "Apa syarat pengajuan KUR untuk usaha mikro berdasarkan regulasi terbaru?",
    "Tunjukkan 10 nasabah dengan eksposur kredit tertinggi di segmen korporasi.",
]

DISCLAIMER = (
    "Answers are grounded on enterprise documents and data. "
    "Always verify with official sources before making business decisions."
)


def render_header() -> None:
    st.set_page_config(
        page_title="Cloudera AI Enterprise Assistant",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Cloudera AI Enterprise Assistant")
    st.caption("Powered by Cloudera AI · Answers from your enterprise documents and data")
    st.info(DISCLAIMER, icon="ℹ️")


def render_sidebar() -> None:
    with st.sidebar:
        st.header("About")
        st.markdown(
            """
This assistant answers in **Bahasa Indonesia** based on:
- Document RAG (PDF, DOCX, TXT)
- Structured data queries (SQL)
- Combined document + data answers

**Answer modes:**
- **Document** — from policy/regulatory documents
- **Structured Data** — from database tables
- **Combined** — from both sources
            """
        )
        st.divider()
        st.header("Sample Prompts")
        for prompt in SAMPLE_PROMPTS:
            label = prompt[:60] + "…" if len(prompt) > 60 else prompt
            if st.button(label, key=prompt):
                st.session_state["prefill_prompt"] = prompt
                st.rerun()


def render_mode_badge(mode: str) -> None:
    color = mode_badge_color(mode)
    label = mode_label(mode)
    st.markdown(
        f'<span style="background:{color};color:white;padding:2px 10px;'
        f'border-radius:12px;font-size:0.8em;font-weight:bold">{label}</span>',
        unsafe_allow_html=True,
    )


def render_answer(result: AnswerResult) -> None:
    """Render the full answer with mode badge, sources, and SQL trace."""
    render_mode_badge(result.mode)
    st.markdown(result.answer)

    if result.doc_citations:
        with st.expander(f"Source Documents ({len(result.doc_citations)} found)", expanded=False):
            for i, cit in enumerate(result.doc_citations, 1):
                st.markdown(f"**[{i}] {cit.title}**")
                st.caption(
                    f"Source: `{cit.source_path}` · Chunk {cit.chunk_index + 1} · "
                    f"Indexed: {cit.ingest_timestamp[:10]}"
                )
                st.markdown(f"> {cit.excerpt}")
                st.divider()

    if result.sql_citation:
        with st.expander("Structured Data Query", expanded=False):
            st.caption(
                f"Rows returned: {result.sql_citation.row_count} · "
                f"Latency: {result.sql_citation.latency_ms:.1f} ms"
            )
            st.markdown("**Executed SQL (system-generated):**")
            st.code(result.sql_citation.sql, language="sql")
            st.markdown("**Results (first 10 rows):**")
            st.markdown(result.sql_citation.table_markdown)


def render_error(message: str) -> None:
    st.error(f"Error: {message}")


def get_chat_input() -> str | None:
    """Return the submitted question or None."""
    prefill = st.session_state.pop("prefill_prompt", None)
    question = st.chat_input("Type your question here…", key="chat_input")
    return prefill or question
