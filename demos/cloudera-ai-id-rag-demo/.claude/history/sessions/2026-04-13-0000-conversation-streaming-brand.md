# Session Log — 2026-04-13 00:00

## Objective
Continue from initial bootstrap. Close the three known gaps from the
previous session and apply Cloudera enterprise branding to the UI.

## Files Changed

| File | Change |
|------|--------|
| `src/llm/base.py` | Added `stream_chat()` with non-streaming fallback default |
| `src/llm/inference_client.py` | Implemented true OpenAI streaming in `stream_chat()` |
| `src/llm/prompts.py` | Added `SYSTEM_PROMPT_DATA`, `build_data_prompt()`, `_trim_history()`, `MAX_HISTORY_TURNS=3`; added `history` param to `build_document_prompt` and `build_combined_prompt` |
| `src/orchestration/answer_builder.py` | Full rewrite — two-phase API (`prepare_answer` / `stream_synthesis` / `finalize_answer`) + `AnswerPrep` dataclass; fixed SQL mode to use `build_data_prompt`; `answer_question` now accepts `history` |
| `app/main.py` | Uses two-phase streaming flow: spinner during retrieval, `st.write_stream` for synthesis, `render_citations` after |
| `app/ui.py` | Full Cloudera brand theme: CSS injection, SVG cloud logo, dark sidebar, orange/teal palette, styled chat bubbles, mode badges, citation cards, custom status indicators |
| `.streamlit/config.toml` | Streamlit theme config (primaryColor=#F96702, dark text, server port 8080) |
| `data/sample_docs/prosedur_kyc_nasabah.txt` | New sample document: KYC/APU-PPT procedure (banking compliance) |

## Decisions Made

### Two-Phase Answer Pipeline
`prepare_answer()` handles classify + retrieve; `stream_synthesis()` handles
LLM streaming; `finalize_answer()` assembles the result. This lets Streamlit
show a spinner during retrieval and stream tokens during synthesis —
a better UX than the original single-call pattern.

### Dedicated `SYSTEM_PROMPT_DATA` and `build_data_prompt()`
The original code used `build_document_prompt` for SQL results, which has
the wrong system prompt ("from documents"). Added a dedicated data prompt
that correctly frames the answer as coming from structured database results.

### Conversation History Design
- `MAX_HISTORY_TURNS = 3` (last 3 user+assistant pairs = up to 6 messages)
- History is trimmed and cleaned in `_trim_history()` before injection
- All prompt builders now accept an optional `history: list[dict] | None`
- In `main.py`, history is extracted from `st.session_state.messages`
  (only role + content, never the embedded AnswerResult object)

### Cloudera Brand Theme
- Primary: `#F96702` (Cloudera Orange)
- Accent: `#00A591` (Cloudera Teal)
- Sidebar: dark gradient `#1A2535 → #243144` with orange left border
- Chat user messages: warm orange tint (#FFF7F0 gradient)
- Mode badges: pill-style with matching color per mode
- CSS injected via `st.markdown(unsafe_allow_html=True)` for compatibility
  with Cloudera AI Applications (which may not allow custom static assets)

## Resolved Issues from Previous Session
- [x] No conversation memory across turns → FIXED: history passed through
- [x] SQL mode used wrong prompt → FIXED: `build_data_prompt` added
- [x] No PDF/DOCX sample document → PARTIAL: added KYC TXT doc; PDF requires
      binary generation (reportlab not in requirements)

## Remaining Known Issues
- [ ] No PDF sample document — reportlab not in requirements
- [ ] HDFS adapter is still a stub
- [ ] No embedding model caching across hot-reloads
- [ ] `render_status()` LLM check is URL presence only, not live ping
      (avoids slow sidebar renders — acceptable for demo)

## Next Steps
1. Run `python data/sample_tables/seed_database.py` to create demo.db
2. Run `python -m src.retrieval.document_loader` to build vector store
3. Configure `.env` with LLM endpoint
4. Test streaming: `streamlit run app/main.py --server.port 8080`
5. Optional: add reportlab to requirements.txt and generate a PDF demo doc
6. Optional: add live LLM ping to `render_status()` with `@st.cache_data(ttl=30)`
