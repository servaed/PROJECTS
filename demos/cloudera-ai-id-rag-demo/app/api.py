"""FastAPI backend for the Cloudera AI Enterprise Assistant.

Replaces the Streamlit entry point with a FastAPI server that:
  - Serves the React SPA from app/static/index.html
  - Streams chat responses via Server-Sent Events (POST /api/chat)
  - Exposes /api/status and /api/samples for the frontend

Run with:
    uvicorn app.api:app --host 0.0.0.0 --port 8080 --reload

Or via deployment/launch_app.sh which handles all startup steps.
"""

import asyncio
import json
import logging
import queue
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import sys
import os

# Ensure project root is on sys.path so `src` imports resolve correctly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text as sa_text

from src.config.logging import setup_logging
from src.config.settings import settings
from src.orchestration.answer_builder import prepare_answer, stream_synthesis, finalize_answer

setup_logging()
logger = logging.getLogger(__name__)

_STATIC = Path(__file__).parent / "static"

# Cache index.html content at startup — avoids a disk read on every GET /
_INDEX_HTML: str = ""

# Persistent config override file — written by POST /api/configure,
# sourced by launch_app.sh on every restart.
_OVERRIDE_PATH = Path("data/.env.local")

# Env-var keys that POST /api/configure is allowed to write.
_CONFIGURE_ALLOWED_KEYS = frozenset({
    "LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL_ID",
    "EMBEDDINGS_PROVIDER", "EMBEDDINGS_MODEL",
    "DATABASE_URL", "SQL_APPROVED_TABLES",
    "DOCS_SOURCE_PATH", "VECTOR_STORE_PATH", "LOG_LEVEL",
})


# ── Lifespan: startup validation + teardown ────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate required resources at startup and log a clear status summary."""
    global _INDEX_HTML

    # Cache SPA entry point
    index_path = _STATIC / "index.html"
    if index_path.exists():
        _INDEX_HTML = index_path.read_text(encoding="utf-8")
        logger.info("SPA index.html cached (%d bytes)", len(_INDEX_HTML))
    else:
        logger.error("app/static/index.html not found — GET / will return 404")

    # Check vector store
    vs_path = Path(settings.vector_store_path) / "index.faiss"
    if vs_path.exists():
        logger.info("Startup check — vector store: OK (%s)", settings.vector_store_path)
    else:
        logger.warning(
            "Startup check — vector store: NOT FOUND at %s. "
            "Run document ingestion before answering questions.",
            settings.vector_store_path,
        )

    # Check database
    try:
        from src.connectors.db_adapter import get_table_names
        tables = get_table_names()
        logger.info("Startup check — database: OK (%d tables)", len(tables))
    except Exception as exc:
        logger.warning("Startup check — database: FAILED — %s", exc)

    # Check LLM configuration (presence only — no live ping to avoid slow startup)
    if settings.llm_base_url or settings.llm_provider in ("bedrock", "anthropic"):
        logger.info(
            "Startup check — LLM: configured (provider=%s, model=%s)",
            settings.llm_provider,
            settings.llm_model_id,
        )
    else:
        logger.warning(
            "Startup check — LLM: provider '%s' has no base URL configured. "
            "Set the required environment variables before answering questions.",
            settings.llm_provider,
        )

    yield  # application runs here


# ── App factory ────────────────────────────────────────────────────────────

app = FastAPI(
    title="Cloudera AI Enterprise Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins so the React SPA can reach the API from any host
# (Cloudera AI Applications proxies everything; this also covers local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── SPA entry point ────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the React single-page application from the startup cache."""
    if not _INDEX_HTML:
        return HTMLResponse("<h1>SPA not found</h1>", status_code=404)
    return HTMLResponse(_INDEX_HTML)


@app.get("/setup", response_class=HTMLResponse)
async def setup_page():
    """Serve the setup health-check dashboard."""
    setup_path = _STATIC / "setup.html"
    if not setup_path.exists():
        return HTMLResponse("<h1>setup.html not found</h1>", status_code=404)
    return HTMLResponse(setup_path.read_text(encoding="utf-8"))


@app.get("/configure", response_class=HTMLResponse)
async def configure_page():
    """Serve the environment-variable configuration wizard."""
    cfg_path = _STATIC / "configure.html"
    if not cfg_path.exists():
        return HTMLResponse("<h1>configure.html not found</h1>", status_code=404)
    return HTMLResponse(cfg_path.read_text(encoding="utf-8"))


app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


# ── Request model ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []


# ── API routes ─────────────────────────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    """Return live system status for the sidebar indicators."""
    result: dict = {}

    vs_path = Path(settings.vector_store_path) / "index.faiss"
    result["vector_store"] = {"ok": vs_path.exists()}

    try:
        from src.connectors.db_adapter import get_table_names
        tables = get_table_names()
        result["database"] = {"ok": True, "tables": len(tables)}
    except Exception as exc:
        result["database"] = {"ok": False, "error": str(exc)}

    if settings.llm_base_url or settings.llm_provider in ("bedrock", "anthropic"):
        model_short = settings.llm_model_id.split("/")[-1][:30]
        result["llm"] = {"ok": True, "model": model_short}
    else:
        result["llm"] = {"ok": False, "model": None}

    return result


@app.get("/api/setup")
async def api_setup():
    """Return detailed setup status for every component — used by the /setup dashboard."""
    import concurrent.futures
    import os
    import time
    from pathlib import Path as _Path

    result: dict = {}

    # ── Vector store ──────────────────────────────────────────────────
    vs_path = _Path(settings.vector_store_path)
    faiss_file = vs_path / "index.faiss"
    hash_file  = vs_path / "index.sha256"
    if faiss_file.exists():
        size_kb = faiss_file.stat().st_size // 1024
        hash_ok = hash_file.exists()
        # Chunk count: FAISS index stores vectors; estimate from pkl
        chunk_count: int | None = None
        try:
            import pickle
            pkl = vs_path / "index.pkl"
            if pkl.exists():
                data = pickle.loads(pkl.read_bytes())  # noqa: S301
                # LangChain FAISS stores docstore._dict
                ds = getattr(data, "_dict", None) or (data[1] if isinstance(data, tuple) and len(data) > 1 else None)
                if isinstance(ds, dict):
                    chunk_count = len(ds)
        except Exception:
            pass
        result["vector_store"] = {
            "ok": True, "path": str(vs_path),
            "index_size_kb": size_kb, "hash_verified": hash_ok,
            "chunk_count": chunk_count,
            "fix": None if hash_ok else "Re-run document ingestion to generate the integrity hash.",
        }
    else:
        result["vector_store"] = {
            "ok": False, "path": str(vs_path),
            "fix": "Run: python -m src.retrieval.document_loader",
        }

    # ── Database ──────────────────────────────────────────────────────
    try:
        from src.connectors.db_adapter import get_engine, get_table_names
        engine = get_engine()
        table_names = get_table_names()
        tables_info = []
        with engine.connect() as conn:
            for tname in table_names:
                try:
                    row_count = conn.execute(sa_text(f"SELECT COUNT(*) FROM {tname}")).scalar()
                except Exception:
                    row_count = None
                tables_info.append({"name": tname, "rows": row_count})
        result["database"] = {"ok": True, "tables": tables_info, "fix": None}
    except Exception as exc:
        result["database"] = {
            "ok": False, "tables": [],
            "fix": f"Check DATABASE_URL. Error: {exc}",
        }

    # ── LLM — live ping with 5 s timeout ─────────────────────────────
    if settings.llm_base_url or settings.llm_provider in ("bedrock", "anthropic"):
        t0 = time.monotonic()
        try:
            from src.llm.inference_client import get_llm_client
            client = get_llm_client()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(client.is_available)
                reachable = future.result(timeout=5.0)
            latency_ms = round((time.monotonic() - t0) * 1000)
            result["llm"] = {
                "ok": reachable,
                "provider": settings.llm_provider,
                "model": settings.llm_model_id,
                "latency_ms": latency_ms if reachable else None,
                "fix": None if reachable else "Check LLM endpoint URL and API key.",
            }
        except Exception as exc:
            result["llm"] = {
                "ok": False, "provider": settings.llm_provider,
                "model": settings.llm_model_id, "latency_ms": None,
                "fix": f"LLM ping failed: {exc}",
            }
    else:
        result["llm"] = {
            "ok": False, "provider": settings.llm_provider, "model": None,
            "fix": f"Set the required env vars for LLM_PROVIDER={settings.llm_provider}.",
        }

    # ── Embeddings ────────────────────────────────────────────────────
    result["embeddings"] = {
        "ok": True,
        "provider": settings.embeddings_provider,
        "model": settings.embeddings_model,
        "fix": None,
    }

    # ── Documents ─────────────────────────────────────────────────────
    docs_path = _Path(settings.docs_source_path)
    if docs_path.exists():
        extensions = {".pdf", ".docx", ".txt", ".md", ".html"}
        files = [f.name for f in docs_path.iterdir() if f.suffix.lower() in extensions]
        result["documents"] = {
            "ok": len(files) > 0, "path": str(docs_path),
            "files": sorted(files), "count": len(files),
            "fix": None if files else "Add at least one .txt/.pdf/.docx file to DOCS_SOURCE_PATH.",
        }
    else:
        result["documents"] = {
            "ok": False, "path": str(docs_path), "files": [], "count": 0,
            "fix": f"Create the directory or set DOCS_SOURCE_PATH. Path not found: {docs_path}",
        }

    return result


@app.get("/api/samples")
async def api_samples():
    """Return sample prompts shown in the sidebar."""
    return [
        "Explain the credit restructuring terms from the latest policy document.",
        "What is the total outstanding MSME loans in Jakarta as of March 2026?",
        "Does that outstanding trend align with the MSME expansion policy?",
        "What are the KUR loan requirements for micro-businesses under current regulations?",
        "Show the top 10 customers by credit exposure in the corporate segment.",
        "Describe the customer identity verification (KYC) procedure per current regulations.",
    ]


def _read_override_file() -> dict[str, str]:
    """Parse data/.env.local into a key→value dict (ignores comments/blanks)."""
    result: dict[str, str] = {}
    if not _OVERRIDE_PATH.exists():
        return result
    try:
        for line in _OVERRIDE_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    except Exception:
        pass
    return result


def _write_override_file(data: dict[str, str]) -> None:
    """Serialise key→value pairs back to data/.env.local."""
    _OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.utcnow().isoformat(timespec="seconds")
    lines = [f"# Auto-generated by /configure — {ts}"]
    lines += [f"{k}={v}" for k, v in sorted(data.items())]
    _OVERRIDE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


@app.get("/api/configure")
async def api_configure_get():
    """Return current configuration state with secrets masked.

    Each key reports:
      value  — the effective value (masked for secrets, None if unset)
      source — 'env' (platform/shell), 'file' (data/.env.local), or None
    """
    overrides = _read_override_file()

    def _entry(key: str) -> dict:
        env_val  = os.environ.get(key)
        file_val = overrides.get(key)
        val    = env_val or file_val
        source = ("env" if env_val else "file") if val else None
        is_secret = any(tok in key.upper() for tok in ("KEY", "SECRET", "PASSWORD", "TOKEN"))
        return {
            "value":  ("●●●●●●●●" if is_secret else val) if val else None,
            "source": source,
        }

    return {k: _entry(k) for k in _CONFIGURE_ALLOWED_KEYS}


class ConfigureRequest(BaseModel):
    env_vars: dict[str, str]


@app.post("/api/configure")
async def api_configure_post(body: ConfigureRequest):
    """Validate, persist, and immediately apply environment-variable overrides.

    Values are written to data/.env.local (sourced by launch_app.sh on restart)
    and applied to os.environ for the current process so GET /api/status reflects
    the new config without a restart.

    Sending an empty string for a key removes it from the override file.
    Keys already set via platform environment variables cannot be overridden here;
    they are ignored with a warning in the response.
    """
    unknown = set(body.env_vars.keys()) - _CONFIGURE_ALLOWED_KEYS
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown config keys: {sorted(unknown)}")

    existing = _read_override_file()
    skipped_env: list[str] = []

    for key, value in body.env_vars.items():
        # Keys already set via real env vars (platform / shell) take precedence;
        # we skip them and warn rather than silently overwriting.
        if os.environ.get(key) and not existing.get(key):
            skipped_env.append(key)
            continue
        if value.strip():
            existing[key] = value.strip()
            os.environ[key] = value.strip()
        else:
            existing.pop(key, None)
            os.environ.pop(key, None)

    _write_override_file(existing)
    logger.info("Configuration updated via /api/configure: %s", sorted(body.env_vars.keys()))

    return {
        "saved": True,
        "file":  str(_OVERRIDE_PATH),
        "keys_updated": [k for k in body.env_vars if k not in skipped_env],
        "keys_skipped_env": skipped_env,
        "restart_required": True,
        "message": (
            "Configuration saved and applied to the current process. "
            "Restart the application for full effect (embeddings reload, "
            "vector store re-check, new DB connections)."
        ),
    }


@app.post("/api/chat")
async def api_chat(body: ChatRequest):
    """Stream a chat response via Server-Sent Events."""
    return StreamingResponse(
        _chat_sse(body.question, body.history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _chat_sse(question: str, history: list[dict]) -> AsyncGenerator[str, None]:
    """Run the three-phase RAG pipeline and yield SSE events.

    Events emitted:
      mode   — classification result (dokumen / data / gabungan)
      token  — one LLM output chunk
      done   — citations payload, marks end of stream
      error  — error message if pipeline fails
    """
    loop = asyncio.get_event_loop()
    try:
        # Phase 1 — classify + retrieve (blocking, run in thread pool)
        prep = await loop.run_in_executor(None, prepare_answer, question, history)
        yield _sse("mode", {"mode": prep.mode})

        # Phase 2 — stream LLM tokens from a producer thread via a queue
        token_q: queue.Queue[str | None] = queue.Queue()

        def _produce() -> None:
            try:
                for tok in stream_synthesis(prep):
                    token_q.put(tok)
            except Exception as exc:
                logger.error("stream_synthesis error: %s", exc)
            finally:
                token_q.put(None)  # sentinel — always signals completion

        thread = threading.Thread(target=_produce, daemon=True)
        thread.start()

        full_text = ""
        while True:
            tok = await loop.run_in_executor(None, token_q.get)
            if tok is None:
                break
            full_text += tok
            yield _sse("token", {"text": tok})

        thread.join(timeout=60)
        if thread.is_alive():
            logger.error("stream_synthesis producer thread did not finish within 60 s")

        # Phase 3 — assemble citations
        result = await loop.run_in_executor(None, finalize_answer, prep, full_text)

        # Build lookup so each citation can include the full retrieved chunk text
        chunk_text_lookup = {
            (c.source_path, c.chunk_index): c.text
            for c in prep.doc_chunks
        }

        doc_cits = [
            {
                "title": c.title,
                "source_path": c.source_path,
                "chunk_index": c.chunk_index,
                "ingest_timestamp": c.ingest_timestamp,
                "excerpt": c.excerpt,
                "full_text": chunk_text_lookup.get((c.source_path, c.chunk_index), c.excerpt),
            }
            for c in (result.doc_citations or [])
        ]

        sql_cit = None
        if result.sql_citation:
            sql_cit = {
                "sql": result.sql_citation.sql,
                "row_count": result.sql_citation.row_count,
                "latency_ms": result.sql_citation.latency_ms,
                "table_markdown": result.sql_citation.table_markdown,
            }

        yield _sse("done", {"doc_citations": doc_cits, "sql_citation": sql_cit})

    except Exception as exc:
        logger.exception("Chat SSE pipeline error")
        yield _sse("error", {"message": str(exc)})


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
