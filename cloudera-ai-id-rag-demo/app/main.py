"""Streamlit application entry point.

Run with:
    streamlit run app/main.py --server.port 8080 --server.address 0.0.0.0

All logic lives in src/. This file is the Streamlit entry point only.
"""

import streamlit as st

from src.config.logging import setup_logging
from src.orchestration.answer_builder import answer_question
from app.ui import render_header, render_sidebar, render_answer, render_error, get_chat_input

setup_logging()

# Page setup
render_header()
render_sidebar()

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Chat history display
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and "result" in msg:
            render_answer(msg["result"])
        else:
            st.markdown(msg["content"])

# Handle new question
question = get_chat_input()

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving answer…"):
            try:
                result = answer_question(question)
                render_answer(result)
                st.session_state.messages.append(
                    {"role": "assistant", "content": result.answer, "result": result}
                )
            except Exception as exc:
                error_msg = f"Failed to process your question: {exc}"
                render_error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
