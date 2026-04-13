"""Streamlit application entry point.

Run with:
    streamlit run app/main.py --server.port 8080 --server.address 0.0.0.0

All logic lives in src/. This file is the Streamlit entry point only.

Flow per question:
  1. prepare_answer()  — classify + retrieve (spinner)
  2. st.write_stream() — stream LLM tokens token-by-token
  3. finalize_answer() — assemble citations
  4. render_citations() — show expandable source panels
"""

import streamlit as st

from src.config.logging import setup_logging
from src.orchestration.answer_builder import prepare_answer, stream_synthesis, finalize_answer
from app.ui import (
    render_header,
    render_sidebar,
    render_answer,
    render_mode_badge,
    render_citations,
    render_error,
    get_chat_input,
)

setup_logging()

render_header()
render_sidebar()

# ── Session state ──────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Chat history display (replay from session state) ───────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            if "result" in msg:
                render_answer(msg["result"])
            else:
                st.markdown(msg.get("content", ""))
        else:
            st.markdown(msg["content"])

# ── Handle new question ────────────────────────────────────────────────────

question = get_chat_input()

if question:
    # Extract prior turns for conversation history (role + content only)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            # Phase 1 — classify + retrieve (fast, shown under spinner)
            with st.spinner("Mencari informasi yang relevan…"):
                prep = prepare_answer(question, history=history)

            # Show mode badge before streaming begins
            render_mode_badge(prep.mode)

            # Phase 2 — stream LLM synthesis token-by-token
            answer_text = st.write_stream(stream_synthesis(prep))

            # Phase 3 — citations and final result
            result = finalize_answer(prep, answer_text)
            render_citations(result)

            st.session_state.messages.append(
                {"role": "assistant", "content": answer_text, "result": result}
            )

        except Exception as exc:
            error_msg = f"Gagal memproses pertanyaan Anda: {exc}"
            render_error(error_msg)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg}
            )
