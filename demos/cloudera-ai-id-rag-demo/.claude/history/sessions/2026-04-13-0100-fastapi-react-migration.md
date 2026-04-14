# Session Log — 2026-04-13 01:00

## Objective
Replace the Streamlit production entry point with a FastAPI backend serving a
React SPA, enabling proper Server-Sent Events streaming and a fully custom UI
without Streamlit rendering constraints.

## Files Changed

| File | Change |
|------|--------|
| `app/api.py` | **New** — FastAPI app: `GET /` (React SPA), `POST /api/chat` (SSE stream), `GET /api/status`, `GET /api/samples` |
| `app/static/index.html` | **New** — React SPA entry point with Cloudera brand design |
| `app/static/cloudera-logo.png` | **New** — Cloudera logo asset |
| `app/static/cloudera-mark.svg` | **New** — Cloudera mark SVG asset |
| `requirements.txt` | Added `fastapi>=0.111.0`, `uvicorn[standard]>=0.29.0` as primary deps; `streamlit` moved to fallback comment |
| `deployment/launch_app.sh` | Step 5 now runs `uvicorn app.api:app` instead of `streamlit run`; banner updated |
| `app/main.py` | Retained as Streamlit fallback for local/notebook use (no production use) |

## Decisions Made

### FastAPI replaces Streamlit as the production entry point
Streamlit's component model wraps `st.write_stream` in a synchronous render loop
that is incompatible with true async SSE. FastAPI + uvicorn allows:
- Native async `StreamingResponse` with `text/event-stream`
- Full control of the frontend (React SPA in `app/static/`)
- Clean REST API (`/api/chat`, `/api/status`, `/api/samples`) that the React
  frontend and any future client can consume

### SSE event protocol
The `/api/chat` endpoint emits four named SSE events:
- `mode`  — classification result (`dokumen` / `data` / `gabungan`)
- `token` — one LLM output chunk (text delta)
- `done`  — final citations payload (doc_citations + sql_citation)
- `error` — error message if the pipeline fails

### Thread-based producer for synchronous `stream_synthesis`
`stream_synthesis()` is a synchronous generator (OpenAI SDK constraint).
It is run in a daemon thread that pushes tokens into a `queue.Queue`. The
async FastAPI handler drains the queue with `loop.run_in_executor`, keeping the
event loop unblocked.

### Streamlit entry point retained
`app/main.py` (Streamlit) is kept for local development convenience and
notebook-style demos. It is NOT the production entry point and is not launched
by `deployment/launch_app.sh`.

## Resolved Issues from Previous Session
- [x] No true SSE streaming from Streamlit → FIXED: FastAPI SSE endpoint
- [x] Streamlit rendering constraints on custom UI → FIXED: React SPA

## Remaining Known Issues
- [ ] No PDF sample document — reportlab not in requirements
- [ ] HDFS adapter is still a stub
- [ ] No embedding model caching across hot-reloads
- [ ] `render_status()` in Streamlit UI (app/ui.py) is URL presence only — acceptable for fallback

## Next Steps
1. Run `bash deployment/launch_app.sh` to verify the full startup sequence
2. Test all three SSE events: mode, token, done
3. Test `/api/status` returns correct state for vector_store, database, llm
4. Optional: add reportlab to requirements.txt and generate a PDF demo document
5. Optional: add live LLM ping to `/api/status` with a timeout
