"""UI components for the Streamlit chat application.

Cloudera AI brand theme:
  Primary   : #F96702  (Cloudera Orange)
  Accent    : #00A591  (Cloudera Teal)
  Dark      : #1B2022
  Sidebar   : #1A2535 → #243144 (dark gradient)

Renders: branded header, styled sidebar, chat messages, mode badges,
source citations, SQL trace, and live system status indicators.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from src.orchestration.answer_builder import AnswerResult
from src.utils.language import mode_label, mode_badge_color

# ── Sample prompts shown in sidebar ───────────────────────────────────────

SAMPLE_PROMPTS = [
    "Explain the credit restructuring conditions based on the latest policy document.",
    "What is the total outstanding MSME loan balance in Jakarta as of March 2026?",
    "Does the outstanding trend align with the MSME expansion policy?",
    "What are the KUR application requirements for micro businesses under the latest regulation?",
    "Show the top 10 customers by credit exposure in the corporate segment.",
    "Explain the customer identity verification (KYC) procedure per current regulations.",
]

# ── Brand CSS ─────────────────────────────────────────────────────────────

_CLOUDERA_CSS = """
<style>
/* ═══════════════════════════════════════════════════════════════════════
   Cloudera AI Enterprise Assistant — Brand Theme v2
   Primary  : #F96702   Cloudera Orange
   Accent   : #00A591   Cloudera Teal
   Dark     : #1B2022
   Sidebar  : #1A2535 → #243144
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Fonts ──────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    -webkit-font-smoothing: antialiased;
}

/* ── App background ─────────────────────────────────────────────────── */
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section[data-testid="stMain"] > div {
    background-color: #F8F9FB !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #1A2535 0%, #243144 100%) !important;
    border-right: 2px solid #F96702 !important;
}
[data-testid="stSidebar"] > div {
    padding-top: 1.5rem;
}
/* Sidebar text override */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {
    color: #CBD5E0 !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #F96702 !important;
    font-weight: 700 !important;
    letter-spacing: -0.3px;
}
[data-testid="stSidebar"] hr {
    border-color: #2D3F5A !important;
    margin: 12px 0 !important;
}

/* Sidebar markdown links and code */
[data-testid="stSidebar"] a { color: #F96702 !important; }
[data-testid="stSidebar"] code {
    background: #2D3F5A !important;
    color: #90CDF4 !important;
}

/* ── Sidebar buttons (sample prompts) ──────────────────────────────── */
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.04) !important;
    color: #CBD5E0 !important;
    border: 1px solid #2D3F5A !important;
    border-radius: 8px !important;
    font-size: 0.78rem !important;
    text-align: left !important;
    padding: 8px 12px !important;
    width: 100% !important;
    white-space: normal !important;
    height: auto !important;
    line-height: 1.45 !important;
    transition: all 0.18s ease !important;
    margin-bottom: 4px !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(249,103,2,0.18) !important;
    border-color: #F96702 !important;
    color: #FFFFFF !important;
    transform: translateX(3px) !important;
    box-shadow: 0 2px 8px rgba(249,103,2,0.25) !important;
}

/* ── Chat messages ──────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 14px !important;
    padding: 16px 18px !important;
    margin-bottom: 10px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
    transition: box-shadow 0.2s ease;
}
[data-testid="stChatMessage"]:hover {
    box-shadow: 0 3px 10px rgba(0,0,0,0.08) !important;
}
/* User messages — warm orange tint */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: linear-gradient(135deg, #FFF7F0 0%, #FFFFFF 100%) !important;
    border-color: #FFD4B0 !important;
}

/* ── Chat input bar ─────────────────────────────────────────────────── */
[data-testid="stChatInput"] textarea {
    border: 2px solid #E5E7EB !important;
    border-radius: 12px !important;
    background: #FFFFFF !important;
    font-size: 0.95rem !important;
    padding: 12px 16px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: #F96702 !important;
    box-shadow: 0 0 0 3px rgba(249,103,2,0.15) !important;
    outline: none !important;
}

/* ── Alert / info box (disclaimer) ─────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border: none !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
/* Info variant — teal accent */
div[data-testid="stAlert"][kind="info"],
div[data-baseweb="notification"][kind="info"] {
    background: linear-gradient(135deg, #E6F7F5 0%, #F0FBF9 100%) !important;
    border-left: 4px solid #00A591 !important;
}

/* ── Expanders ──────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #E5E7EB !important;
    border-radius: 10px !important;
    background: #FFFFFF !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    margin-top: 8px !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: #374151 !important;
    padding: 10px 14px !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary:hover {
    color: #F96702 !important;
    background: #FFF7F0 !important;
}
[data-testid="stExpander"] summary svg {
    color: #F96702 !important;
}

/* ── Code blocks ────────────────────────────────────────────────────── */
[data-testid="stCode"] {
    border-radius: 8px !important;
    border: 1px solid #E5E7EB !important;
    background: #1A2535 !important;
}
code {
    background: #F3F4F6 !important;
    border-radius: 4px !important;
    padding: 1px 5px !important;
    font-size: 0.85em !important;
    color: #E85D04 !important;
}

/* ── Spinner ────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] {
    color: #F96702 !important;
}
[data-testid="stSpinner"] > div > div {
    border-top-color: #F96702 !important;
}

/* ── Success/Warning/Error boxes in sidebar ─────────────────────────── */
[data-testid="stSidebar"] .stSuccess {
    background: rgba(0,165,145,0.12) !important;
    border: 1px solid rgba(0,165,145,0.4) !important;
    border-radius: 8px !important;
    color: #A7F3D0 !important;
}
[data-testid="stSidebar"] .stWarning {
    background: rgba(249,103,2,0.12) !important;
    border: 1px solid rgba(249,103,2,0.4) !important;
    border-radius: 8px !important;
    color: #FCD9B0 !important;
}
[data-testid="stSidebar"] .stError {
    background: rgba(239,68,68,0.12) !important;
    border: 1px solid rgba(239,68,68,0.4) !important;
    border-radius: 8px !important;
    color: #FCA5A5 !important;
}

/* ── Headings in main area ──────────────────────────────────────────── */
.stApp h1 { color: #1B2022 !important; font-weight: 700 !important; }
.stApp h2 { color: #2D3748 !important; font-weight: 600 !important; }
.stApp h3 { color: #4A5568 !important; font-weight: 600 !important; }

/* Caption / small text */
.stApp [data-testid="stCaptionContainer"] { color: #6B7280 !important; }

/* ── Blockquote (used for excerpt previews) ─────────────────────────── */
blockquote {
    border-left: 3px solid #F96702 !important;
    padding-left: 12px !important;
    color: #6B7280 !important;
    font-style: italic !important;
    margin: 6px 0 !important;
}

/* ── Divider ────────────────────────────────────────────────────────── */
[data-testid="stDivider"] hr {
    border-color: #F3F4F6 !important;
}

/* ── Custom scrollbar ───────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #F1F5F9; }
::-webkit-scrollbar-thumb { background: #CBD5E0; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #F96702; }

/* ── Footer — hide Streamlit branding ──────────────────────────────── */
footer { visibility: hidden !important; }
#MainMenu { visibility: hidden !important; }
</style>
"""

# ── Branded header HTML ───────────────────────────────────────────────────

_CLOUDERA_HEADER_HTML = """
<div style="
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 0 18px 0;
    border-bottom: 2px solid #F2F3F5;
    margin-bottom: 6px;
">
    <!-- Cloudera cloud mark SVG -->
    <div style="flex-shrink:0;">
        <svg width="52" height="52" viewBox="0 0 52 52" fill="none"
             xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Cloudera">
            <rect width="52" height="52" rx="13" fill="#F96702"/>
            <path d="M38 31a7 7 0 00-1.4-13.8 10.5 10.5 0 00-20.6 2.8H15a6 6 0 000 12h23a4 4 0 000-8z"
                  fill="#FFFFFF"/>
            <circle cx="15" cy="32" r="1.5" fill="#F96702" opacity="0.4"/>
        </svg>
    </div>
    <!-- Wordmark and tagline -->
    <div style="line-height:1.15;">
        <div style="
            font-family:'Inter',sans-serif;
            font-size:1.65rem;
            font-weight:700;
            color:#1B2022;
            letter-spacing:-0.5px;
        ">
            Cloudera&nbsp;<span style="color:#F96702;">AI</span>
            &nbsp;<span style="
                background: linear-gradient(90deg,#F96702,#FF8C42);
                -webkit-background-clip:text;
                -webkit-text-fill-color:transparent;
                font-weight:800;
            ">Enterprise&nbsp;Assistant</span>
        </div>
        <div style="
            font-size:0.82rem;
            color:#6B7280;
            font-weight:400;
            margin-top:3px;
            letter-spacing:0.1px;
        ">
            Powered by&nbsp;
            <strong style="color:#00A591;">Cloudera AI Inference</strong>
            &nbsp;·&nbsp; Document RAG&nbsp;+&nbsp;SQL Data
            &nbsp;·&nbsp; Bilingual (ID / EN)
        </div>
    </div>
</div>
"""

_DISCLAIMER_HTML = """
<div style="
    background: linear-gradient(135deg,#E6F7F5 0%,#F0FBF9 100%);
    border: 1px solid rgba(0,165,145,0.3);
    border-left: 4px solid #00A591;
    border-radius: 10px;
    padding: 10px 16px;
    margin-bottom: 18px;
    font-size: 0.84rem;
    color: #1B2022;
    display: flex;
    align-items: center;
    gap: 10px;
">
    <span style="font-size:1.2em;">ℹ️</span>
    <span>
        Answers are based on company documents and data.
        <strong>Always verify with authoritative sources</strong>
        before making business decisions.
    </span>
</div>
"""

# ── Sidebar logo mark ─────────────────────────────────────────────────────

_SIDEBAR_LOGO_HTML = """
<div style="
    display:flex;align-items:center;gap:10px;
    padding:0 4px 16px 4px;
    border-bottom:1px solid rgba(255,255,255,0.08);
    margin-bottom:12px;
">
    <svg width="32" height="32" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="52" height="52" rx="13" fill="#F96702"/>
        <path d="M38 31a7 7 0 00-1.4-13.8 10.5 10.5 0 00-20.6 2.8H15a6 6 0 000 12h23a4 4 0 000-8z"
              fill="#FFFFFF"/>
    </svg>
    <div>
        <div style="color:#F96702;font-weight:700;font-size:1rem;line-height:1.1;">Cloudera AI</div>
        <div style="color:#718096;font-size:0.7rem;">Enterprise Assistant</div>
    </div>
</div>
"""


# ─────────────────────────────────────────────────────────────────────────
# Public render functions
# ─────────────────────────────────────────────────────────────────────────


def render_header() -> None:
    """Configure page and render the branded Cloudera header."""
    st.set_page_config(
        page_title="Cloudera AI Enterprise Assistant",
        page_icon="🟠",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    # Inject global CSS
    st.markdown(_CLOUDERA_CSS, unsafe_allow_html=True)
    # Branded header
    st.markdown(_CLOUDERA_HEADER_HTML, unsafe_allow_html=True)
    # Disclaimer banner
    st.markdown(_DISCLAIMER_HTML, unsafe_allow_html=True)


def render_sidebar() -> None:
    """Render the styled Cloudera sidebar with status, about, and prompts."""
    with st.sidebar:
        st.markdown(_SIDEBAR_LOGO_HTML, unsafe_allow_html=True)

        # ── About section ──────────────────────────────────────────────
        st.markdown("### About the Assistant")
        st.markdown(
            """
The assistant answers in the **same language as your question** (ID or EN) based on:
- 📄 Document RAG (PDF, DOCX, TXT)
- 🗄️ Structured data queries (SQL)
- 🔀 Combined document + data answers
            """,
            unsafe_allow_html=False,
        )

        st.divider()
        render_status()
        st.divider()

        # ── Sample prompts ─────────────────────────────────────────────
        st.markdown("### 💬 Sample Questions")
        for prompt in SAMPLE_PROMPTS:
            label = prompt[:58] + "…" if len(prompt) > 58 else prompt
            if st.button(label, key=f"prompt_{prompt[:30]}", use_container_width=True):
                st.session_state["prefill_prompt"] = prompt
                st.rerun()


def render_status() -> None:
    """Render live system status indicators."""
    st.markdown("### 🔌 System Status")

    from src.config.settings import settings

    # ── Vector store ───────────────────────────────────────────────────
    vs_ok = (Path(settings.vector_store_path) / "index.faiss").exists()
    if vs_ok:
        st.success("Vector Store: Active", icon="✅")
    else:
        st.warning("Vector Store: Not ingested", icon="⚠️")

    # ── Database ───────────────────────────────────────────────────────
    try:
        from src.connectors.db_adapter import get_table_names
        tables = get_table_names()
        st.success(f"Database: {len(tables)} tables", icon="✅")
    except Exception:
        st.error("Database: Not connected", icon="❌")

    # ── LLM endpoint ──────────────────────────────────────────────────
    if settings.llm_base_url:
        model_short = settings.llm_model_id.split("/")[-1][:22]
        st.success(f"LLM: {model_short}", icon="✅")
    else:
        st.error("LLM: URL not configured", icon="❌")


def render_mode_badge(mode: str) -> None:
    """Render a pill badge showing the answer mode."""
    badge_styles = {
        "dokumen": ("🗂️", "#00A591", "#E6F7F5", "Document RAG"),
        "data":    ("🗄️", "#6366F1", "#EEF2FF", "Structured Data"),
        "gabungan":("🔀", "#F96702", "#FFF7F0", "Combined"),
    }
    icon, border, bg, label_text = badge_styles.get(
        mode, ("❓", "#6B7280", "#F3F4F6", mode)
    )
    st.markdown(
        f"""
        <div style="
            display:inline-flex;align-items:center;gap:6px;
            background:{bg};
            border:1.5px solid {border};
            color:{border};
            padding:4px 12px;
            border-radius:20px;
            font-size:0.78rem;
            font-weight:700;
            letter-spacing:0.3px;
            margin-bottom:10px;
            text-transform:uppercase;
        ">{icon}&nbsp;{label_text}</div>
        """,
        unsafe_allow_html=True,
    )


def render_citations(result: AnswerResult) -> None:
    """Render expandable source documents and SQL trace panels."""
    if result.doc_citations:
        with st.expander(
            f"📄 Source Documents — {len(result.doc_citations)} citations found",
            expanded=False,
        ):
            for i, cit in enumerate(result.doc_citations, 1):
                st.markdown(
                    f"""<div style="
                        background:#F8F9FB;border-radius:8px;
                        padding:10px 14px;margin-bottom:8px;
                        border-left:3px solid #F96702;
                    ">
                    <span style="font-weight:600;color:#1B2022;">[{i}]&nbsp;{cit.title}</span><br>
                    <span style="font-size:0.75rem;color:#6B7280;">
                        📁 <code>{cit.source_path}</code>
                        &nbsp;·&nbsp; Chunk {cit.chunk_index + 1}
                        &nbsp;·&nbsp; Indexed: {cit.ingest_timestamp[:10]}
                    </span>
                    </div>""",
                    unsafe_allow_html=True,
                )
                st.markdown(f"> {cit.excerpt}")
                if i < len(result.doc_citations):
                    st.divider()

    if result.sql_citation:
        with st.expander("🗄️ Structured Data Query — Execution Details", expanded=False):
            col1, col2 = st.columns(2)
            col1.metric("Rows Returned", result.sql_citation.row_count)
            col2.metric("Query Latency", f"{result.sql_citation.latency_ms:.1f} ms")
            st.markdown(
                "<p style='font-size:0.82rem;color:#6B7280;font-weight:600;"
                "text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;'>"
                "SQL Executed (system-generated):</p>",
                unsafe_allow_html=True,
            )
            st.code(result.sql_citation.sql, language="sql")
            st.markdown(
                "<p style='font-size:0.82rem;color:#6B7280;font-weight:600;"
                "text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;'>"
                "Results (first 10 rows):</p>",
                unsafe_allow_html=True,
            )
            st.markdown(result.sql_citation.table_markdown)


def render_answer(result: AnswerResult) -> None:
    """Render a complete answer (non-streaming replay from session history)."""
    render_mode_badge(result.mode)
    st.markdown(result.answer)
    render_citations(result)


def render_error(message: str) -> None:
    st.markdown(
        f"""
        <div style="
            background:#FEF2F2;border:1.5px solid #EF4444;
            border-radius:10px;padding:12px 16px;
            color:#991B1B;font-size:0.9rem;
        ">⚠️&nbsp; <strong>Error:</strong> {message}</div>
        """,
        unsafe_allow_html=True,
    )


def get_chat_input() -> str | None:
    """Return the submitted question or None."""
    prefill = st.session_state.pop("prefill_prompt", None)
    question = st.chat_input("Type your question here…", key="chat_input")
    return prefill or question
