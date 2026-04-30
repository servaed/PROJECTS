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
import re
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import sys
import os

# Ensure project root is on sys.path so `src` imports resolve correctly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from src.config.logging import setup_logging
from src.config.settings import settings
from src.orchestration.answer_builder import prepare_answer, stream_synthesis, finalize_answer
from src.utils.metrics import log_inference as _log_inference

setup_logging()
logger = logging.getLogger(__name__)

_STATIC = Path(__file__).parent / "static"

# Server start time — used by /api/status to expose uptime for fast-poll logic
_STARTUP_TIME: float = time.monotonic()

# Persistent config override file — written by POST /api/configure,
# sourced by launch_app.sh on every restart.
_OVERRIDE_PATH = Path("data/.env.local")

# Services-ready sentinel written by entrypoint.sh after MinIO/Nessie/Trino/seed
# complete.  Only enforced in Docker/CML mode (QUERY_ENGINE=trino).
# In DuckDB mode this file is never written and the gate is bypassed.
_SERVICES_READY_FLAG = Path("/tmp/.cml_services_ready")

# ── Rate limiter (sliding window, no external dependency) ──────────────────

_rate_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX    = 30    # max requests per window
_RATE_LIMIT_WINDOW = 60.0  # window size in seconds


def _check_rate_limit(client_ip: str) -> bool:
    now    = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW
    times  = _rate_store[client_ip]
    _rate_store[client_ip] = [t for t in times if t > cutoff]
    if len(_rate_store[client_ip]) >= _RATE_LIMIT_MAX:
        return False
    _rate_store[client_ip].append(now)
    return True


# Strip control characters from configure values to prevent .env.local corruption
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")


def _sanitize_config_value(value: str) -> str:
    """Remove control characters that could corrupt .env.local or enable injection.

    Truncates at the first newline first — prevents KEY=val\\nINJECTED=evil attacks
    where stripping \\n would otherwise concatenate the injected content onto the value.
    """
    first_line = value.splitlines()[0] if value else value
    return _CONTROL_CHAR_RE.sub("", first_line).strip()


# Env-var keys that POST /api/configure is allowed to write.
_CONFIGURE_ALLOWED_KEYS = frozenset({
    "LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL_ID",
    # Azure OpenAI — provider-specific keys (not covered by generic LLM_* above)
    "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_VERSION",
    "EMBEDDINGS_PROVIDER", "EMBEDDINGS_MODEL",
    "QUERY_ENGINE", "DUCKDB_PARQUET_DIR", "TRINO_HOST", "SQL_APPROVED_TABLES",
    "DOCS_SOURCE_PATH", "VECTOR_STORE_PATH", "LOG_LEVEL",
})


# ── Lifespan: startup validation + teardown ────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate required resources at startup and log a clear status summary."""
    # Check vector store + verify SHA-256 integrity hash
    vs_path   = Path(settings.vector_store_path) / "index.faiss"
    hash_path = Path(settings.vector_store_path) / "index.sha256"
    if vs_path.exists():
        if hash_path.exists():
            import hashlib as _hashlib
            _vs_dir  = Path(settings.vector_store_path)
            combined = b""
            for _f in ("index.faiss", "index.pkl"):
                _fp = _vs_dir / _f
                if _fp.exists():
                    combined += _fp.read_bytes()
            actual   = _hashlib.sha256(combined).hexdigest()
            expected = hash_path.read_text(encoding="utf-8").strip()
            if actual == expected:
                logger.info("Startup check - vector store: OK, hash verified (%s)", settings.vector_store_path)
            else:
                logger.warning(
                    "Startup check - vector store: hash MISMATCH - index may be corrupt. "
                    "Re-run document ingestion to rebuild."
                )
        else:
            logger.info("Startup check - vector store: OK (%s)", settings.vector_store_path)
    else:
        logger.warning(
            "Startup check - vector store: NOT FOUND at %s. "
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

    # Check LLM configuration + fire a background warm-up ping
    if settings.llm_base_url or settings._live_provider in ("bedrock", "anthropic"):
        logger.info(
            "Startup check — LLM: configured (provider=%s, model=%s)",
            settings._live_provider,
            settings.llm_model_id,
        )
        import threading as _threading
        from concurrent.futures import ThreadPoolExecutor as _TPE

        def _warm_up_llm() -> None:
            try:
                from src.llm.inference_client import get_llm_client
                client = get_llm_client()
                with _TPE(max_workers=1) as ex:
                    fut = ex.submit(
                        client.chat,
                        [{"role": "user", "content": "ping"}],
                        1,   # temperature
                        1,   # max_tokens
                    )
                    fut.result(timeout=5)
                logger.info("Startup - LLM warm-up: OK (model cache primed)")
            except Exception as exc:
                logger.info("Startup - LLM warm-up: %s (non-critical, first response may be slower)", exc)

        _threading.Thread(target=_warm_up_llm, daemon=True).start()
    else:
        logger.warning(
            "Startup check — LLM: provider '%s' has no base URL configured. "
            "Set the required environment variables before answering questions.",
            settings._live_provider,
        )

    yield  # application runs here


# ── App factory ────────────────────────────────────────────────────────────

app = FastAPI(
    title="Cloudera AI Enterprise Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins.  This is safe because Cloudera AI Applications
# handles authentication at the platform level (SSO/LDAP proxy) before any
# request reaches this server.  For self-hosted / local dev, there is no
# sensitive data exposure beyond what the LLM already returns.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── SPA entry point ────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the React single-page application, read fresh from disk each request."""
    index_path = _STATIC / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>SPA not found</h1>", status_code=404)
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


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


@app.get("/explorer", response_class=HTMLResponse)
async def explorer_page():
    """Serve the SQL query editor and documents browser."""
    p = _STATIC / "explorer.html"
    if not p.exists():
        return HTMLResponse("<h1>explorer.html not found</h1>", status_code=404)
    return HTMLResponse(p.read_text(encoding="utf-8"))


@app.get("/upload", response_class=HTMLResponse)
async def upload_page():
    """Serve the document upload page."""
    p = _STATIC / "upload.html"
    if not p.exists():
        return HTMLResponse("<h1>upload.html not found</h1>", status_code=404)
    return HTMLResponse(p.read_text(encoding="utf-8"))


@app.get("/presentation", response_class=HTMLResponse)
async def presentation_page():
    """Serve the presales slide deck."""
    p = _STATIC / "presentation.html"
    if not p.exists():
        return HTMLResponse("<h1>presentation.html not found</h1>", status_code=404)
    return HTMLResponse(p.read_text(encoding="utf-8"))


app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


# ── Domain configuration ───────────────────────────────────────────────────

# Tables visible to SQL generation per domain.  Documents are filtered by the
# same domain key stored in chunk metadata (set during ingestion).
DOMAIN_CONFIG: dict[str, dict] = {
    "banking": {
        "label": "Banking",
        "tables": ["msme_credit", "customer", "branch"],
    },
    "telco": {
        "label": "Telco",
        "tables": ["subscriber", "data_usage", "network"],
    },
    "government": {
        "label": "Government",
        "tables": ["resident", "regional_budget", "public_service"],
    },
    "all": {
        "label": "All Domains",
        "tables": [
            "msme_credit", "customer", "branch",
            "subscriber", "data_usage", "network",
            "resident", "regional_budget", "public_service",
        ],
    },
}

_DEFAULT_DOMAIN = "banking"


# ── Sample prompts ─────────────────────────────────────────────────────────

# Each entry: domain, mode (routing hint), text_id (Bahasa), text_en (English)
_SAMPLES: list[dict] = [
    # ── Banking ───────────────────────────────────────────────────────────
    {"domain": "banking", "mode": "document",
     "text_id": "Apa saja syarat pengajuan kredit UMKM dan dokumen yang wajib dilengkapi?",
     "text_en": "What are the MSME credit requirements and mandatory documents?"},
    {"domain": "banking", "mode": "document",
     "text_id": "Bagaimana prosedur restrukturisasi kredit jika debitur mengalami kesulitan pembayaran?",
     "text_en": "What is the credit restructuring procedure when a debtor has payment difficulties?"},
    {"domain": "banking", "mode": "data",
     "text_id": "Berapa total outstanding kredit UMKM di Jakarta per Maret 2026?",
     "text_en": "What is the total outstanding MSME credit in Jakarta as of March 2026?"},
    {"domain": "banking", "mode": "data",
     "text_id": "Tampilkan 5 nasabah dengan total eksposur kredit tertinggi.",
     "text_en": "Show the top 5 customers by total credit exposure."},
    {"domain": "banking", "mode": "combined",
     "text_id": "Apakah outstanding kredit UMKM di Jakarta sudah sesuai target ekspansi 15% yang ditetapkan kebijakan 2026?",
     "text_en": "Does the Jakarta MSME credit outstanding align with the 15% expansion target set by the 2026 policy?"},
    {"domain": "banking", "mode": "combined",
     "text_id": "Bagaimana kualitas kredit di Bandung dibandingkan kondisi yang memenuhi syarat restrukturisasi menurut kebijakan bank?",
     "text_en": "How does Bandung's credit quality compare to the restructuring eligibility conditions per bank policy?"},
    # ── Telco ─────────────────────────────────────────────────────────────
    {"domain": "telco", "mode": "document",
     "text_id": "Apa saja standar waktu penanganan keluhan pelanggan yang ditetapkan dalam SLA?",
     "text_en": "What are the customer complaint resolution time standards defined in the SLA?"},
    {"domain": "telco", "mode": "document",
     "text_id": "Bagaimana kebijakan retensi pelanggan dan syarat mendapatkan diskon perpanjangan kontrak?",
     "text_en": "What is the customer retention policy and the conditions for contract renewal discounts?"},
    {"domain": "telco", "mode": "data",
     "text_id": "Tampilkan utilisasi jaringan per wilayah dan identifikasi wilayah yang mendekati kapasitas kritis.",
     "text_en": "Show network utilization by region and identify areas approaching critical capacity."},
    {"domain": "telco", "mode": "data",
     "text_id": "Berapa pelanggan dengan churn risk score di atas 70 dan di wilayah mana saja?",
     "text_en": "How many subscribers have a churn risk score above 70 and in which regions?"},
    {"domain": "telco", "mode": "combined",
     "text_id": "Apakah utilisasi jaringan di Bali sudah melampaui batas SLA ketersediaan yang ditetapkan dalam kebijakan?",
     "text_en": "Has network utilization in Bali exceeded the availability SLA threshold defined in the policy?"},
    {"domain": "telco", "mode": "combined",
     "text_id": "Pelanggan mana yang berisiko churn tinggi dan apakah mereka memenuhi syarat program retensi berdasarkan kebijakan?",
     "text_en": "Which high-churn-risk subscribers qualify for the retention program based on the policy criteria?"},
    # ── Government ────────────────────────────────────────────────────────
    {"domain": "government", "mode": "document",
     "text_id": "Berapa standar waktu penyelesaian layanan KTP elektronik dan apa kompensasi jika terlambat?",
     "text_en": "What is the processing time standard for electronic ID cards and what compensation is given for delays?"},
    {"domain": "government", "mode": "document",
     "text_id": "Apa saja kanal pengaduan yang tersedia dan bagaimana prosedur penanganannya?",
     "text_en": "What complaint channels are available and what is the handling procedure?"},
    {"domain": "government", "mode": "data",
     "text_id": "Tampilkan realisasi anggaran per satuan kerja dan identifikasi yang realisasinya di bawah target.",
     "text_en": "Show budget realization per work unit and identify those below target."},
    {"domain": "government", "mode": "data",
     "text_id": "Layanan publik mana yang memiliki tingkat kepuasan masyarakat terendah per Maret 2026?",
     "text_en": "Which public services have the lowest citizen satisfaction rate as of March 2026?"},
    {"domain": "government", "mode": "combined",
     "text_id": "Apakah layanan IMB sudah memenuhi standar waktu dan IKM yang ditetapkan dalam kebijakan pelayanan publik?",
     "text_en": "Does the building permit (IMB) service meet the processing time and satisfaction standards set by the public service policy?"},
    {"domain": "government", "mode": "combined",
     "text_id": "Satuan kerja mana yang realisasi anggarannya rendah dan apakah ada risiko penalti sesuai regulasi APBD?",
     "text_en": "Which work units have low budget realization and face penalty risk under the APBD regulation?"},
]


# ── Request model ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []
    domain: str = _DEFAULT_DOMAIN
    language: str = "id"
    style: str = "analyst"   # analyst | executive | compliance


# ── API routes ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health():
    """Liveness/readiness probe for Kubernetes, Docker, and Cloudera AI.

    Returns 200 when the app is fully operational, 503 when any critical
    component (vector store, database) is unavailable.
    """
    checks: dict[str, bool] = {}

    vs_path = Path(settings.vector_store_path) / "index.faiss"
    checks["vector_store"] = vs_path.exists()

    try:
        from src.connectors.db_adapter import get_table_names
        get_table_names()
        checks["database"] = True
    except Exception:
        checks["database"] = False

    checks["llm_configured"] = bool(
        settings.llm_base_url or settings._live_provider in ("bedrock", "anthropic")
    )

    # In Docker/CML mode report whether data services (Trino stack) are ready
    if settings.query_engine == "trino":
        checks["services_ready"] = _SERVICES_READY_FLAG.exists()

    all_ok = all(checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ok" if all_ok else "degraded",
            "checks": checks,
            "uptime_s": round(time.monotonic() - _STARTUP_TIME),
        },
    )


@app.get("/api/status", tags=["status"])
async def api_status():
    """Return live system status for the sidebar indicators."""
    result: dict = {}

    vs_path   = Path(settings.vector_store_path) / "index.faiss"
    hash_path = Path(settings.vector_store_path) / "index.sha256"
    vs_ok = vs_path.exists()
    hash_ok = hash_path.exists() if vs_ok else False
    result["vector_store"] = {"ok": vs_ok, "hash_verified": hash_ok}

    try:
        from src.connectors.db_adapter import get_table_names
        tables = get_table_names()
        result["database"] = {"ok": True, "tables": len(tables)}
    except Exception as exc:
        result["database"] = {"ok": False, "error": str(exc)}

    if settings.llm_base_url or settings._live_provider in ("bedrock", "anthropic"):
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
        from src.connectors.db_adapter import get_table_names, get_table_row_count, get_engine_label
        table_names = get_table_names()
        tables_info = [
            {"name": tname, "rows": get_table_row_count(tname)}
            for tname in table_names
        ]
        result["database"] = {
            "ok": True, "tables": tables_info,
            "engine": get_engine_label(), "fix": None,
        }
    except Exception as exc:
        result["database"] = {
            "ok": False, "tables": [],
            "fix": f"Check query engine config. Error: {exc}",
        }

    # ── LLM — live ping with 15 s timeout ────────────────────────────
    if settings.llm_base_url or settings._live_provider in ("bedrock", "anthropic"):
        t0 = time.monotonic()
        try:
            from src.llm.inference_client import get_llm_client
            client = get_llm_client()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(client.is_available)
                reachable = future.result(timeout=15.0)
            latency_ms = round((time.monotonic() - t0) * 1000)
            result["llm"] = {
                "ok": reachable,
                "provider": settings._live_provider,
                "model": settings.llm_model_id,
                "latency_ms": latency_ms if reachable else None,
                "fix": None if reachable else "Check LLM endpoint URL and API key.",
            }
        except Exception as exc:
            result["llm"] = {
                "ok": False, "provider": settings._live_provider,
                "model": settings.llm_model_id, "latency_ms": None,
                "fix": f"LLM ping failed: {exc}",
            }
    else:
        result["llm"] = {
            "ok": False, "provider": settings._live_provider, "model": None,
            "fix": f"Set the required env vars for LLM_PROVIDER={settings._live_provider}.",
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
        files = sorted(f.name for f in docs_path.rglob("*") if f.suffix.lower() in extensions)
        result["documents"] = {
            "ok": len(files) > 0, "path": str(docs_path),
            "files": files, "count": len(files),
            "fix": None if files else "Add at least one .txt/.pdf/.docx file to DOCS_SOURCE_PATH.",
        }
    else:
        result["documents"] = {
            "ok": False, "path": str(docs_path), "files": [], "count": 0,
            "fix": f"Create the directory or set DOCS_SOURCE_PATH. Path not found: {docs_path}",
        }

    return result


@app.get("/api/test/{component}")
async def api_test_component(component: str):
    """Test a single system component and return its status.

    component — one of: vector_store | database | llm | embeddings | documents
    """
    import concurrent.futures
    import time as _time
    from pathlib import Path as _Path

    allowed = {"vector_store", "database", "llm", "embeddings", "documents"}
    if component not in allowed:
        raise HTTPException(status_code=404, detail=f"Unknown component '{component}'. Choose from: {sorted(allowed)}")

    # ── Vector store ───────────────────────────────────────────────────
    if component == "vector_store":
        vs_path = _Path(settings.vector_store_path)
        faiss_file = vs_path / "index.faiss"
        hash_file  = vs_path / "index.sha256"
        if not faiss_file.exists():
            return {"ok": False, "path": str(vs_path),
                    "fix": "Run: python -m src.retrieval.document_loader"}
        size_kb = faiss_file.stat().st_size // 1024
        hash_ok = hash_file.exists()
        chunk_count: int | None = None
        try:
            import pickle
            pkl = vs_path / "index.pkl"
            if pkl.exists():
                data = pickle.loads(pkl.read_bytes())  # noqa: S301
                ds = getattr(data, "_dict", None) or (
                    data[1] if isinstance(data, tuple) and len(data) > 1 else None)
                if isinstance(ds, dict):
                    chunk_count = len(ds)
        except Exception:
            pass
        return {"ok": True, "path": str(vs_path), "index_size_kb": size_kb,
                "hash_verified": hash_ok, "chunk_count": chunk_count,
                "fix": None if hash_ok else "Re-run ingestion to regenerate the integrity hash."}

    # ── Database ───────────────────────────────────────────────────────
    if component == "database":
        t0 = _time.monotonic()
        try:
            from src.connectors.db_adapter import get_table_names, get_table_row_count, get_engine_label
            table_names = get_table_names()
            tables_info = [
                {"name": tname, "rows": get_table_row_count(tname)}
                for tname in table_names
            ]
            latency_ms = round((_time.monotonic() - t0) * 1000)
            return {
                "ok": True, "tables": tables_info,
                "engine": get_engine_label(), "latency_ms": latency_ms, "fix": None,
            }
        except Exception as exc:
            return {"ok": False, "tables": [], "latency_ms": None,
                    "fix": f"Check query engine config. Error: {exc}"}

    # ── LLM ────────────────────────────────────────────────────────────
    if component == "llm":
        live_provider = settings._live_provider
        model_id  = settings.llm_model_id
        t0 = _time.monotonic()
        try:
            from src.llm.inference_client import get_llm_client
            client = get_llm_client()

            def _ping():
                client.chat([{"role": "user", "content": "ping"}], max_tokens=1)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                ex.submit(_ping).result(timeout=15.0)
            latency_ms = round((_time.monotonic() - t0) * 1000)
            return {"ok": True, "provider": live_provider, "model": model_id,
                    "latency_ms": latency_ms, "fix": None}
        except concurrent.futures.TimeoutError:
            return {"ok": False, "provider": live_provider, "model": model_id,
                    "latency_ms": None, "fix": "Connection timed out (15 s). Check that the endpoint URL is reachable."}
        except Exception as exc:
            latency_ms = round((_time.monotonic() - t0) * 1000)
            return {"ok": False, "provider": live_provider, "model": model_id,
                    "latency_ms": latency_ms, "fix": f"{type(exc).__name__}: {exc}"}

    # ── Embeddings ─────────────────────────────────────────────────────
    if component == "embeddings":
        t0 = _time.monotonic()
        try:
            from src.retrieval.embeddings import get_embeddings
            emb = get_embeddings()
            # Smoke-test: embed a short string (5 s timeout to prevent thread exhaustion)
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, emb.embed_query, "test"),
                timeout=5.0,
            )
            latency_ms = round((_time.monotonic() - t0) * 1000)
            return {"ok": True, "provider": settings.embeddings_provider,
                    "model": settings.embeddings_model, "latency_ms": latency_ms, "fix": None}
        except Exception as exc:
            return {"ok": False, "provider": settings.embeddings_provider,
                    "model": settings.embeddings_model, "latency_ms": None,
                    "fix": f"Embeddings load failed: {exc}"}

    # ── Documents ──────────────────────────────────────────────────────
    if component == "documents":
        docs_path = _Path(settings.docs_source_path)
        if not docs_path.exists():
            return {"ok": False, "path": str(docs_path), "files": [], "count": 0,
                    "fix": f"Directory not found: {docs_path}"}
        extensions = {".pdf", ".docx", ".txt", ".md", ".html"}
        files = sorted(f.name for f in docs_path.rglob("*") if f.suffix.lower() in extensions)
        return {"ok": len(files) > 0, "path": str(docs_path), "files": files, "count": len(files),
                "fix": None if files else "Add at least one document file to DOCS_SOURCE_PATH."}


_MODE_ORDER = {"document": 0, "data": 1, "combined": 2}


@app.get("/api/samples")
async def api_samples(domain: str = _DEFAULT_DOMAIN, lang: str = "id"):
    """Return sample prompts for the given domain and language.

    Query params:
      domain — banking | telco | government  (default: banking)
      lang   — id (Bahasa Indonesia) | en (English)  (default: id)

    Each item has:
      text  — the prompt string in the requested language
      mode  — expected routing mode: dokumen | data | gabungan

    Results are ordered by difficulty: dokumen -> data -> gabungan.
    """
    if domain not in DOMAIN_CONFIG:
        domain = _DEFAULT_DOMAIN
    text_key = "text_en" if lang == "en" else "text_id"
    filtered = sorted(
        [s for s in _SAMPLES if s["domain"] == domain],
        key=lambda s: _MODE_ORDER.get(s["mode"], 99),
    )
    return [{"text": s[text_key], "mode": s["mode"]} for s in filtered]


@app.get("/api/domains")
async def api_domains():
    """Return available domain configurations for the frontend dropdown.

    The "all" pseudo-domain is always last so the sidebar renders it after
    the individual domain tabs.
    """
    result = [
        {"id": k, "label": v["label"]}
        for k, v in DOMAIN_CONFIG.items()
        if k != "all"
    ]
    result.append({"id": "all", "label": DOMAIN_CONFIG["all"]["label"]})
    return result


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
    shadowed_by_env: list[str] = []

    for key, value in body.env_vars.items():
        sanitized = _sanitize_config_value(value)
        if sanitized:
            existing[key] = sanitized
            os.environ[key] = sanitized
        else:
            existing.pop(key, None)
            os.environ.pop(key, None)
        # Note keys where a platform env var is also present — it will shadow
        # the file value until the platform env var is cleared.
        if os.environ.get(key) and value.strip():
            # Check whether the platform originally set this (i.e. it was set
            # before we wrote it).  We approximate: if the env value differs
            # from what we just wrote, a platform var is shadowing it.
            pass  # already written above; just track for the warning below

    # Detect keys whose effective os.environ value was NOT set by this request
    # (i.e. a platform env var may override the file on restart)
    for key in body.env_vars:
        env_val = os.environ.get(key, "")
        file_val = existing.get(key, "")
        if env_val and env_val != file_val:
            shadowed_by_env.append(key)

    _write_override_file(existing)
    # Invalidate BM25 cache so next retrieval rebuilds with any new document path
    try:
        from src.retrieval.retriever import invalidate_bm25_cache
        invalidate_bm25_cache()
    except Exception:
        pass
    logger.info("Configuration updated via /api/configure: %s", sorted(body.env_vars.keys()))

    shadow_msg = (
        f" Note: {', '.join(shadowed_by_env)} are also set as platform environment "
        f"variables which will take precedence on restart. Clear the platform variable "
        f"to let the saved value take effect."
        if shadowed_by_env else ""
    )

    return {
        "saved": True,
        "file":  str(_OVERRIDE_PATH),
        "keys_updated": sorted(body.env_vars.keys()),
        "keys_shadowed_by_env": shadowed_by_env,
        "restart_required": True,
        "message": (
            "Configuration saved and applied to the current process. "
            "Restart the application for full effect (embeddings reload, "
            f"vector store re-check, new DB connections).{shadow_msg}"
        ),
    }


# ── LLM Profile storage ───────────────────────────────────────────────────
_PROFILES_PATH = Path("data/llm_profiles.json")


def _load_profiles() -> dict:
    if _PROFILES_PATH.exists():
        try:
            return json.loads(_PROFILES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"profiles": []}


def _save_profiles_file(data: dict) -> None:
    _PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PROFILES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class ProfileSaveRequest(BaseModel):
    name: str
    config: dict[str, str]


@app.get("/api/profiles", tags=["settings"])
async def api_profiles_list():
    """Return all saved LLM profiles."""
    return _load_profiles()


@app.post("/api/profiles", tags=["settings"])
async def api_profiles_save(body: ProfileSaveRequest):
    """Create or update a named LLM profile."""
    import datetime
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Profile name is required")
    safe_config = {k: v for k, v in body.config.items() if k in _CONFIGURE_ALLOWED_KEYS}
    data = _load_profiles()
    profiles = data.get("profiles", [])
    now = datetime.datetime.now().isoformat(timespec="seconds")
    existing = next((p for p in profiles if p["name"] == name), None)
    if existing:
        existing["config"] = safe_config
        existing["updated_at"] = now
    else:
        profiles.append({"name": name, "config": safe_config, "created_at": now})
    data["profiles"] = profiles
    _save_profiles_file(data)
    logger.info("LLM profile saved: %s", name)
    return {"ok": True, "name": name, "count": len(profiles)}


@app.delete("/api/profiles/{name}", tags=["settings"])
async def api_profiles_delete(name: str):
    """Delete a named LLM profile."""
    data = _load_profiles()
    before = len(data.get("profiles", []))
    data["profiles"] = [p for p in data.get("profiles", []) if p["name"] != name]
    _save_profiles_file(data)
    return {"ok": True, "deleted": len(data["profiles"]) < before}


@app.post("/api/profiles/{name}/activate", tags=["settings"])
async def api_profiles_activate(name: str):
    """Apply a saved profile: writes its config to data/.env.local and os.environ."""
    data = _load_profiles()
    profile = next((p for p in data.get("profiles", []) if p["name"] == name), None)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    config = {k: v for k, v in profile.get("config", {}).items() if k in _CONFIGURE_ALLOWED_KEYS}
    existing = _read_override_file()
    for key, value in config.items():
        sanitized = _sanitize_config_value(value)
        if sanitized:
            existing[key] = sanitized
            os.environ[key] = sanitized
        else:
            existing.pop(key, None)
            os.environ.pop(key, None)
    _write_override_file(existing)
    logger.info("LLM profile activated: %s", name)
    return {"ok": True, "name": name, "config": config}


# ── Follow-up question suggestions ────────────────────────────────────────

class FollowupRequest(BaseModel):
    question: str
    answer: str
    mode: str = "document"
    domain: str = "banking"
    language: str = "id"


# ── Agent: Planner + Executor + Synthesizer ───────────────────────────────

_AGENT_PLAN_SYSTEM = """\
You are a research planner for an enterprise AI assistant.
Given a user question, create a focused research plan with 2-4 steps.

Available tools:
- "docs": Search internal policy/regulation/procedure documents
- "data": Query structured database tables (banking, telco, government)

Output ONLY a valid JSON array — no other text, no markdown fences:
[{"type":"docs"|"data","query":"specific search string","label":"Short description"},...]

Rules:
- Maximum 4 steps, minimum 2
- Each query must be specific and self-contained
- Use "docs" for policy/procedure/regulation/eligibility questions
- Use "data" for numbers, counts, rankings, current metrics
- If the question needs policy AND data: include both types
- Keep labels concise (< 8 words)"""


def _plan_research(question: str, domain: str, language: str) -> list[dict]:
    """Ask the LLM to produce a 2-4 step research plan as JSON."""
    from src.llm.inference_client import get_llm_client
    lang_hint = "in Bahasa Indonesia" if language == "id" else "in English"
    user_msg = (
        f"Domain context: {domain}. Language: {lang_hint}.\n\nQuestion: {question}"
    )
    try:
        llm = get_llm_client()
        resp = llm.chat(
            [{"role": "system", "content": _AGENT_PLAN_SYSTEM},
             {"role": "user",   "content": user_msg}],
            temperature=0.2, max_tokens=400,
        )
        raw = resp.content.strip()
        # Strip markdown fences if the LLM added them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        plan = json.loads(raw.strip())
        # Validate structure
        steps = []
        for s in plan[:4]:
            if isinstance(s, dict) and "type" in s and "query" in s:
                steps.append({
                    "type":  s["type"] if s["type"] in ("docs", "data") else "docs",
                    "query": str(s.get("query", ""))[:300],
                    "label": str(s.get("label", s.get("query", "")[:40]))[:60],
                })
        return steps if len(steps) >= 1 else [{"type": "docs", "query": question, "label": "Search documents"}]
    except Exception as exc:
        logger.warning("Agent planner failed (%s) — falling back to single doc step", exc)
        return [{"type": "docs", "query": question, "label": "Search documents"}]


_AGENT_SYNTH_SYSTEM = """\
You are an enterprise AI assistant that synthesizes research results into a clear answer.
You have been given a question and the results of several research steps.
Write a comprehensive, well-structured answer using ALL the provided research.
Cite which step each fact comes from using [Step N] markers.
{lang_rule}"""


async def _agent_sse(
    question: str,
    history: list[dict],
    domain: str,
    retrieval_domain: str | None,
    domain_tables: list[str] | None,
    language: str,
    style: str,
) -> AsyncGenerator[str, None]:
    """Three-phase agent: Plan → Execute steps → Synthesize."""
    from src.retrieval.retriever import retrieve
    from src.orchestration.answer_builder import _generate_sql_with_retry, _format_doc_context, _format_sql_summary
    from src.llm.inference_client import get_llm_client
    from src.llm.prompts import _lang_rule, _style_rule
    from src.orchestration.citations import build_document_citations, build_sql_citation
    import dataclasses

    loop = asyncio.get_event_loop()
    _t_start = time.monotonic()

    try:
        # ── Phase 1: Plan ──────────────────────────────────────────────
        yield _sse("agent_thinking", {"label": "Planning research approach…"})
        steps = await loop.run_in_executor(None, _plan_research, question, domain, language)
        yield _sse("agent_plan", {"steps": steps})

        # ── Phase 2: Execute each step ─────────────────────────────────
        step_results: list[dict] = []
        all_doc_chunks = []
        all_sql_results = []

        for i, step in enumerate(steps):
            yield _sse("agent_step_start", {"index": i, "type": step["type"],
                                            "query": step["query"], "label": step["label"]})
            t_step = time.monotonic()

            if step["type"] == "docs":
                chunks = await loop.run_in_executor(
                    None, retrieve, step["query"], 3, retrieval_domain, language
                )
                result_text = _format_doc_context(chunks)
                summary = f"{len(chunks)} chunks"
                all_doc_chunks.extend(chunks)
            else:  # data
                qr = await loop.run_in_executor(
                    None, _generate_sql_with_retry, step["query"], domain_tables
                )
                result_text = _format_sql_summary(qr) if qr else "_No data retrieved._"
                row_count = qr.row_count if qr and qr.succeeded else 0
                summary = f"{row_count} rows"
                if qr and qr.succeeded:
                    all_sql_results.append(qr)

            elapsed_ms = int((time.monotonic() - t_step) * 1000)
            step_results.append({"step": step, "index": i, "result": result_text})
            yield _sse("agent_step_done", {"index": i, "summary": summary, "latency_ms": elapsed_ms})

        # ── Phase 3: Synthesize ────────────────────────────────────────
        yield _sse("agent_synthesis", {})

        # Build synthesis context
        research_context = "\n\n".join(
            f"[Step {r['index']+1} — {r['step']['label']}]\n{r['result']}"
            for r in step_results
        )
        sr = _style_rule(style)
        system = _AGENT_SYNTH_SYSTEM.format(lang_rule=_lang_rule(language))
        if sr:
            system += f"\n{sr}"

        messages = [{"role": "system", "content": system}]
        messages.extend(history[-(5*2):] if history else [])
        messages.append({"role": "user", "content":
            f"Research results:\n{research_context}\n\nQuestion: {question}"})

        llm = get_llm_client()
        full_text = ""
        token_q: queue.Queue = queue.Queue()

        def _produce():
            try:
                for tok in llm.stream_chat(messages):
                    token_q.put(tok)
            except Exception as exc:
                token_q.put(("__error__", str(exc)))
            finally:
                token_q.put(None)

        thread = threading.Thread(target=_produce, daemon=True)
        thread.start()
        while True:
            try:
                item = token_q.get(timeout=30)
            except queue.Empty:
                break
            if item is None:
                break
            if isinstance(item, tuple) and item[0] == "__error__":
                yield _sse("error", {"message": item[1]})
                break
            full_text += item
            yield _sse("token", {"text": item})
        thread.join(timeout=5)

        # Build citations from accumulated chunks/results
        doc_cits = build_document_citations(all_doc_chunks) if all_doc_chunks else []
        sql_cit  = build_sql_citation(all_sql_results[0]) if all_sql_results else None

        total_ms = int((time.monotonic() - _t_start) * 1000)
        yield _sse("done", {
            "doc_citations": [dataclasses.asdict(c) for c in doc_cits] if doc_cits else [],
            "sql_citation":  dataclasses.asdict(sql_cit) if sql_cit else None,
            "latency_ms": total_ms,
        })

    except Exception as exc:
        logger.exception("Agent pipeline error")
        yield _sse("error", {"message": str(exc)})


@app.post("/api/agent/chat", tags=["chat"])
async def api_agent_chat(body: ChatRequest, request: Request):
    """Agentic chat: Plan → Execute → Synthesize with visible step trace."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    domain = body.domain if body.domain in DOMAIN_CONFIG else _DEFAULT_DOMAIN
    domain_tables = DOMAIN_CONFIG[domain]["tables"]
    retrieval_domain: str | None = None if domain == "all" else domain

    return StreamingResponse(
        _agent_sse(body.question, body.history, domain=domain,
                   retrieval_domain=retrieval_domain,
                   domain_tables=domain_tables, language=body.language,
                   style=body.style),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.post("/api/followup", tags=["chat"])
async def api_followup(body: FollowupRequest):
    """Generate 3 contextual follow-up question suggestions via a lightweight LLM call."""
    from src.llm.inference_client import get_llm_client
    lang_hint = "in Bahasa Indonesia" if body.language == "id" else "in English"
    prompt = (
        f"Given this Q&A exchange, suggest exactly 3 short follow-up questions {lang_hint} "
        f"that a user would naturally ask next. Return only the 3 questions, one per line, "
        f"no numbering, no extra text.\n\n"
        f"Q: {body.question}\nA: {body.answer[:600]}"
    )
    try:
        llm = get_llm_client()
        resp = llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=200,
        )
        lines = [l.strip().lstrip("-•→").strip() for l in resp.content.strip().splitlines() if l.strip()]
        suggestions = [l for l in lines if len(l) > 5][:3]
        return {"suggestions": suggestions}
    except Exception as exc:
        logger.warning("follow-up generation failed: %s", exc)
        return {"suggestions": []}


# ── Demo self-test ─────────────────────────────────────────────────────────

_SELFTEST_QUESTIONS = [
    {"label": "Document RAG",    "question": "Apa syarat pengajuan kredit UMKM?",            "domain": "banking",    "language": "id"},
    {"label": "Structured Data", "question": "Show top 5 customers by credit exposure",      "domain": "banking",    "language": "en"},
    {"label": "Combined",        "question": "Apakah utilisasi jaringan di Bali melebihi batas SLA?", "domain": "telco", "language": "id"},
]


@app.post("/api/selftest", tags=["ops"])
async def api_selftest():
    """Run 3 quick test questions through the live pipeline and return pass/fail + latency."""
    results = []
    for t in _SELFTEST_QUESTIONS:
        t0 = time.monotonic()
        try:
            prep = prepare_answer(
                t["question"], history=[], top_k=3,
                domain=t["domain"], language=t["language"],
            )
            full_text = ""
            for tok in __import__("src.orchestration.answer_builder", fromlist=["stream_synthesis"]).stream_synthesis(prep):
                full_text += tok
                if len(full_text) > 50:
                    break
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            passed = bool(full_text and len(full_text) > 10)
            results.append({"label": t["label"], "passed": passed, "latency_ms": elapsed_ms, "error": None})
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            results.append({"label": t["label"], "passed": False, "latency_ms": elapsed_ms, "error": str(exc)[:120]})
    return {"tests": results, "all_passed": all(r["passed"] for r in results)}


# ── Mini evaluation suite ──────────────────────────────────────────────────

_EVAL_QUESTIONS = [
    # Banking ID
    {"domain":"banking","language":"id","mode":"document","question":"Apa syarat restrukturisasi kredit UMKM?"},
    {"domain":"banking","language":"id","mode":"data",    "question":"Berapa total outstanding kredit UMKM di Jakarta?"},
    {"domain":"banking","language":"id","mode":"combined","question":"Apakah outstanding kredit UMKM Jakarta sudah sesuai target ekspansi 15% kebijakan 2026?"},
    # Telco EN
    {"domain":"telco","language":"en","mode":"document","question":"What are the SLA tiers for customer service?"},
    {"domain":"telco","language":"en","mode":"data",    "question":"Show top 5 subscribers by churn risk score"},
    {"domain":"telco","language":"en","mode":"combined","question":"Which subscribers have high churn risk and qualify for the retention program?"},
    # Government ID
    {"domain":"government","language":"id","mode":"document","question":"Apa ketentuan penalti APBD yang berlaku?"},
    {"domain":"government","language":"id","mode":"data",    "question":"Tampilkan realisasi anggaran per satuan kerja"},
    {"domain":"government","language":"id","mode":"combined","question":"Satuan kerja mana yang berisiko kena penalti sesuai regulasi APBD?"},
]

_eval_state: dict = {"running": False, "results": None, "completed": 0, "total": len(_EVAL_QUESTIONS)}
_eval_lock = threading.Lock()
_EVAL_RESULTS_PATH = Path("data/eval_results.json")


def _run_eval_background() -> None:
    """Execute mini eval in a background thread, writing results to disk."""
    from src.orchestration.answer_builder import stream_synthesis as _stream
    results = []
    by_domain: dict = {}
    passed_total = 0
    for i, q in enumerate(_EVAL_QUESTIONS):
        t0 = time.monotonic()
        try:
            prep = prepare_answer(q["question"], top_k=3, domain=q["domain"], language=q["language"])
            full_text = ""
            for tok in _stream(prep):
                full_text += tok
                if len(full_text) > 200:
                    break
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            passed = bool(full_text and len(full_text) > 10)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            passed = False
            full_text = ""
        if passed:
            passed_total += 1
        d = q["domain"]
        if d not in by_domain:
            by_domain[d] = {"passed": 0, "total": 0}
        by_domain[d]["total"] += 1
        if passed:
            by_domain[d]["passed"] += 1
        results.append({
            "domain": d, "language": q["language"], "mode": q.get("mode",""),
            "question": q["question"], "passed": passed, "latency_ms": elapsed_ms,
        })
        with _eval_lock:
            _eval_state["completed"] = i + 1
    data = {
        "running": False, "results": results, "by_domain": by_domain,
        "passed": passed_total, "total": len(results),
        "completed_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }
    _EVAL_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _EVAL_RESULTS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    with _eval_lock:
        _eval_state.update(data)
    logger.info("Mini eval complete: %d/%d passed", passed_total, len(results))


@app.post("/api/eval/run", tags=["ops"])
async def api_eval_run():
    """Start the 9-question mini evaluation in the background."""
    with _eval_lock:
        if _eval_state["running"]:
            return {"ok": False, "message": "Eval already running"}
        _eval_state["running"] = True
        _eval_state["completed"] = 0
        _eval_state["results"] = None
    t = threading.Thread(target=_run_eval_background, daemon=True)
    t.start()
    return {"ok": True, "total": len(_EVAL_QUESTIONS)}


@app.get("/api/eval/status", tags=["ops"])
async def api_eval_status():
    """Return current eval status — running/completed/results."""
    with _eval_lock:
        state = dict(_eval_state)
    if state.get("results") is None and _EVAL_RESULTS_PATH.exists():
        try:
            cached = json.loads(_EVAL_RESULTS_PATH.read_text())
            state.update(cached)
        except Exception:
            pass
    return state


@app.get("/api/stats", tags=["ops"])
async def api_stats():
    """Return session-level token usage counters (reset on restart)."""
    with _stats_lock:
        snap = dict(_session_stats)
    snap["uptime_s"] = round(time.monotonic() - _STARTUP_TIME)
    return snap


_ingest_state: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "last_result": None,
}
_ingest_lock = threading.Lock()

# ── Session token counters (in-memory, reset on restart) ──────────────────
_stats_lock = threading.Lock()
_session_stats: dict = {
    "total_requests": 0,
    "input_tokens":   0,
    "output_tokens":  0,
    "total_tokens":   0,
    "since": time.time(),
}


# ── SQL Explorer ───────────────────────────────────────────────────────────

@app.get("/api/sql/tables")
async def api_sql_tables():
    """Return all queryable tables with their column schemas."""
    from src.connectors.db_adapter import get_table_names, get_table_schema
    tables = []
    for name in get_table_names():
        schema = get_table_schema(name)
        tables.append({"name": name, "columns": schema})
    return {"tables": tables, "engine": settings.query_engine}


class SQLQueryRequest(BaseModel):
    sql: str


@app.post("/api/sql/query")
async def api_sql_query(body: SQLQueryRequest):
    """Execute a read-only SQL query and return rows as JSON.

    Passes through the same guardrails used by the chat pipeline but
    without the approved-table restriction — the explorer is an admin tool.
    """
    from src.sql.guardrails import validate_sql, ensure_limit, SqlGuardrailError
    from src.connectors.db_adapter import execute_read_query

    try:
        sql = validate_sql(body.sql)
        sql = ensure_limit(sql, 500)
        rows = execute_read_query(sql)
        return {"ok": True, "rows": rows, "count": len(rows), "sql": sql}
    except SqlGuardrailError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.warning("SQL Explorer query failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


# ── Documents API ──────────────────────────────────────────────────────────

@app.get("/api/docs/list")
async def api_docs_list():
    """List all documents in the knowledge-base source directory."""
    from src.connectors.files_adapter import FilesAdapter

    adapter = FilesAdapter(settings.docs_source_path)
    base = Path(settings.docs_source_path)
    docs = []
    for path in sorted(adapter.list_documents(), key=lambda p: str(p)):
        try:
            rel = path.relative_to(base)
        except ValueError:
            rel = path
        parts = rel.parts
        domain = parts[0] if len(parts) >= 2 and parts[0] in {"banking", "telco", "government"} else "general"
        language = "en" if path.stem.endswith("_en") else "id"
        size = path.stat().st_size
        docs.append({
            "name": path.name,
            "path": str(rel).replace("\\", "/"),
            "domain": domain,
            "language": language,
            "file_type": path.suffix.lstrip(".").upper(),
            "size_bytes": size,
        })
    return {"docs": docs, "count": len(docs)}


_ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
_ALLOWED_DOMAINS = {"banking", "telco", "government"}


@app.post("/api/docs/upload")
async def api_docs_upload(
    file: UploadFile = File(...),
    domain: str = Form(...),
    language: str = Form("id"),
    auto_ingest: bool = Form(True),
):
    """Upload a document to the knowledge base.

    Saves to data/sample_docs/{domain}/{filename} and optionally triggers
    a full vector store rebuild.  English files get an _en suffix injected
    if not already present so language detection works correctly.
    """
    if domain not in _ALLOWED_DOMAINS:
        raise HTTPException(400, f"domain must be one of: {', '.join(sorted(_ALLOWED_DOMAINS))}")

    original_name = Path(file.filename or "upload.txt")
    ext = original_name.suffix.lower()
    if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(400, f"File type '{ext}' is not supported. Use: {', '.join(sorted(_ALLOWED_UPLOAD_EXTENSIONS))}")

    stem = original_name.stem
    if language == "en" and not stem.endswith("_en"):
        stem = stem + "_en"
    filename = stem + ext

    dest_dir = Path(settings.docs_source_path) / domain
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    data = await file.read()
    dest.write_bytes(data)
    logger.info("Document uploaded: %s (%d bytes)", dest, len(data))

    ingest_triggered = False
    if auto_ingest:
        with _ingest_lock:
            already_running = _ingest_state["running"]
        if not already_running:
            with _ingest_lock:
                _ingest_state["running"] = True
                _ingest_state["started_at"] = time.time()
                _ingest_state["finished_at"] = None
                _ingest_state["last_result"] = None

            def _run():
                result: dict = {}
                try:
                    from src.retrieval.document_loader import load_documents
                    from src.retrieval.chunking import chunk_documents
                    from src.retrieval.embeddings import get_embeddings
                    from src.retrieval.vector_store import build_vector_store
                    docs = load_documents()
                    chunks = chunk_documents(docs)
                    embeddings = get_embeddings()
                    build_vector_store(chunks, embeddings)
                    result = {"ok": True, "docs": len(docs), "chunks": len(chunks)}
                except Exception as exc:
                    logger.exception("Upload ingest failed")
                    result = {"ok": False, "error": str(exc)}
                finally:
                    with _ingest_lock:
                        _ingest_state["running"] = False
                        _ingest_state["finished_at"] = time.time()
                        _ingest_state["last_result"] = result

            threading.Thread(target=_run, daemon=True, name="upload-ingest-worker").start()
            ingest_triggered = True

    return {
        "ok": True,
        "saved_as": filename,
        "domain": domain,
        "language": language,
        "size_bytes": len(data),
        "ingest_triggered": ingest_triggered,
    }


# ── Ingest ─────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    reseed_db: bool = False


@app.post("/api/ingest")
async def api_ingest(body: IngestRequest = IngestRequest()):
    """Rebuild the FAISS vector store from source documents in the background.

    Source documents (in MinIO or local filesystem) are NOT deleted — only the
    FAISS index files are overwritten.  Optionally also re-seeds the Parquet
    files when reseed_db=true and QUERY_ENGINE == duckdb.

    Returns immediately with status=started.  Poll GET /api/ingest/status.
    """
    with _ingest_lock:
        if _ingest_state["running"]:
            return JSONResponse(
                {"status": "running", "message": "Ingestion already in progress — check /api/ingest/status."},
                status_code=409,
            )
        _ingest_state["running"] = True
        _ingest_state["started_at"] = time.time()
        _ingest_state["finished_at"] = None
        _ingest_state["last_result"] = None

    def _run_ingest() -> None:
        result: dict = {}
        try:
            from src.retrieval.document_loader import load_documents
            from src.retrieval.chunking import chunk_documents
            from src.retrieval.embeddings import get_embeddings
            from src.retrieval.vector_store import build_vector_store

            logger.info("Ingest API: loading documents...")
            docs = load_documents()
            logger.info("Ingest API: loaded %d documents — chunking...", len(docs))
            chunks = chunk_documents(docs)
            logger.info("Ingest API: %d chunks — building vector store...", len(chunks))
            embeddings = get_embeddings()
            build_vector_store(chunks, embeddings)
            logger.info("Ingest API: vector store rebuilt — %d chunks indexed.", len(chunks))

            if body.reseed_db and settings.query_engine == "duckdb":
                logger.info("Ingest API: re-seeding Parquet files...")
                import importlib.util as _ilu
                _seed_path = Path(__file__).parent.parent / "data/sample_tables/seed_parquet.py"
                _spec = _ilu.spec_from_file_location("_seed_parquet", _seed_path)
                _mod = _ilu.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                _mod.seed_parquet()
                logger.info("Ingest API: Parquet files re-seeded.")

            result = {"ok": True, "docs": len(docs), "chunks": len(chunks)}
        except Exception as exc:
            logger.exception("Ingest API: ingestion failed")
            result = {"ok": False, "error": str(exc)}
        finally:
            with _ingest_lock:
                _ingest_state["running"] = False
                _ingest_state["finished_at"] = time.time()
                _ingest_state["last_result"] = result

    threading.Thread(target=_run_ingest, daemon=True, name="ingest-worker").start()
    return {"status": "started", "message": "Vector store rebuild started. Poll /api/ingest/status for progress."}


@app.get("/api/ingest/status")
async def api_ingest_status():
    """Return the current or last ingest job status."""
    started = _ingest_state["started_at"]
    finished = _ingest_state["finished_at"]
    return {
        "running":     _ingest_state["running"],
        "started_at":  started,
        "finished_at": finished,
        "elapsed_s":   round(time.time() - started) if started and not finished else (
                       round(finished - started) if started and finished else None
                       ),
        "last_result": _ingest_state["last_result"],
    }


@app.get("/api/ingest/stream")
async def api_ingest_stream():
    """Stream ingest progress as SSE events.  Polls _ingest_state every 500 ms.

    Events emitted:
      progress  — {step, message, elapsed_s}
      done      — {ok, docs, chunks, elapsed_s}
      idle      — emitted when no ingest is running (use for polling to confirm state)
    """
    async def _generate() -> AsyncGenerator[str, None]:
        last_step = ""
        for _ in range(360):          # max 3-minute stream
            state = dict(_ingest_state)
            elapsed = round(time.time() - state["started_at"]) if state["started_at"] else 0
            if state["running"]:
                step = state.get("step", "running")
                if step != last_step:
                    last_step = step
                    yield _sse("progress", {"step": step, "message": step, "elapsed_s": elapsed})
                else:
                    yield _sse("progress", {"step": step, "message": step, "elapsed_s": elapsed})
            elif state["last_result"]:
                res = state["last_result"]
                yield _sse("done", {
                    "ok": res.get("ok", False),
                    "docs": res.get("docs", 0),
                    "chunks": res.get("chunks", 0),
                    "elapsed_s": round(state["finished_at"] - state["started_at"])
                    if state["finished_at"] and state["started_at"] else 0,
                })
                return
            else:
                yield _sse("idle", {"message": "No ingest running"})
            await asyncio.sleep(0.5)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Document management ────────────────────────────────────────────────────

@app.delete("/api/docs/{filename:path}")
async def api_docs_delete(filename: str):
    """Delete a document from the knowledge base by relative path.

    filename — relative path under DOCS_SOURCE_PATH (e.g. banking/policy.txt).
    Triggers BM25 cache invalidation.  Re-ingest via POST /api/ingest to rebuild
    the vector store without the deleted document.
    """
    base = Path(settings.docs_source_path)
    # Prevent path traversal
    target = (base / filename).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(400, "Invalid path")
    if not target.exists():
        raise HTTPException(404, f"File not found: {filename}")
    if not target.is_file():
        raise HTTPException(400, "Path is not a file")

    target.unlink()
    logger.info("Document deleted: %s", target)

    try:
        from src.retrieval.retriever import invalidate_bm25_cache
        invalidate_bm25_cache()
    except Exception:
        pass

    return {"ok": True, "deleted": filename}


# ── URL scrape-and-ingest ──────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url: str
    domain: str = "banking"
    language: str = "id"
    auto_ingest: bool = True

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: str) -> str:
        if v not in {"banking", "telco", "government"}:
            raise ValueError("domain must be banking | telco | government")
        return v


@app.post("/api/docs/scrape")
async def api_docs_scrape(body: ScrapeRequest):
    """Fetch a URL, extract its text, save as a .txt document, and optionally re-ingest."""
    import re as _re
    import httpx
    from bs4 import BeautifulSoup

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(body.url, headers={"User-Agent": "ClouderaRAG/1.0"})
            resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(400, f"Failed to fetch URL: {exc}")

    soup = BeautifulSoup(resp.content, "html.parser")
    # Remove script/style/nav/footer tags
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Collapse blank lines
    text = _re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) < 100:
        raise HTTPException(400, "Scraped content too short — page may require JavaScript")

    # Build filename from URL slug
    from urllib.parse import urlparse as _urlparse
    slug = _urlparse(body.url).path.strip("/").replace("/", "_")[:60] or "scraped"
    slug = _re.sub(r"[^a-zA-Z0-9_-]", "_", slug)
    if body.language == "en" and not slug.endswith("_en"):
        slug += "_en"
    filename = f"{slug}.txt"

    dest_dir = Path(settings.docs_source_path) / body.domain
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_text(f"Source: {body.url}\n\n{text}", encoding="utf-8")
    logger.info("Scraped URL saved: %s (%d chars)", dest, len(text))

    ingest_triggered = False
    if body.auto_ingest:
        with _ingest_lock:
            already = _ingest_state["running"]
        if not already:
            with _ingest_lock:
                _ingest_state.update({"running": True, "started_at": time.time(),
                                      "finished_at": None, "last_result": None})
            def _run():
                try:
                    from src.retrieval.document_loader import load_documents
                    from src.retrieval.chunking import chunk_documents
                    from src.retrieval.embeddings import get_embeddings
                    from src.retrieval.vector_store import build_vector_store
                    docs = load_documents()
                    chunks = chunk_documents(docs)
                    build_vector_store(chunks, get_embeddings())
                    with _ingest_lock:
                        _ingest_state.update({"running": False, "finished_at": time.time(),
                                              "last_result": {"ok": True, "docs": len(docs), "chunks": len(chunks)}})
                except Exception as exc:
                    logger.exception("Scrape ingest failed")
                    with _ingest_lock:
                        _ingest_state.update({"running": False, "finished_at": time.time(),
                                              "last_result": {"ok": False, "error": str(exc)}})
            threading.Thread(target=_run, daemon=True, name="scrape-ingest").start()
            ingest_triggered = True

    return {
        "ok": True, "saved_as": filename, "domain": body.domain,
        "language": body.language, "chars": len(text),
        "ingest_triggered": ingest_triggered,
    }


# ── CSV / Excel → new queryable table ─────────────────────────────────────

@app.post("/api/docs/upload-table")
async def api_upload_table(
    file: UploadFile = File(...),
    table_name: str = Form(...),
    overwrite: bool = Form(False),
):
    """Upload a CSV or Excel file and register it as a new DuckDB-queryable table.

    The file is saved as a Parquet file under DUCKDB_PARQUET_DIR so the
    DuckDB adapter auto-discovers it on next query.  Only available when
    QUERY_ENGINE=duckdb.
    """
    if settings.query_engine != "duckdb":
        raise HTTPException(400, "Table upload is only supported when QUERY_ENGINE=duckdb")

    import re as _re
    if not _re.match(r"^[a-z][a-z0-9_]{0,59}$", table_name):
        raise HTTPException(400, "table_name must be lowercase letters/digits/underscores, max 60 chars")

    fname = Path(file.filename or "upload")
    ext = fname.suffix.lower()
    if ext not in {".csv", ".xlsx"}:
        raise HTTPException(400, "Only .csv and .xlsx files are supported")

    data = await file.read()
    import pandas as pd
    import io

    try:
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(data))
        else:
            df = pd.read_excel(io.BytesIO(data), engine="openpyxl")
    except Exception as exc:
        raise HTTPException(400, f"Failed to parse file: {exc}")

    # Sanitize column names
    df.columns = [_re.sub(r"[^a-z0-9_]", "_", c.lower().strip()) for c in df.columns]

    parquet_dir = Path(settings.duckdb_parquet_dir)
    parquet_dir.mkdir(parents=True, exist_ok=True)
    dest = parquet_dir / f"{table_name}.parquet"

    if dest.exists() and not overwrite:
        raise HTTPException(409, f"Table '{table_name}' already exists. Pass overwrite=true to replace.")

    df.to_parquet(dest, index=False)
    logger.info("Table uploaded: %s (%d rows, %d cols) -> %s", table_name, len(df), len(df.columns), dest)

    # Invalidate DuckDB connection cache so the new table is discovered
    try:
        from src.connectors.duckdb_adapter import reset_connection
        reset_connection()
    except Exception:
        pass

    return {
        "ok": True, "table_name": table_name, "rows": len(df),
        "columns": list(df.columns), "parquet_path": str(dest),
    }


# ── Metrics ────────────────────────────────────────────────────────────────

@app.get("/metrics", response_class=HTMLResponse)
async def metrics_page():
    """Serve the MLflow/inference metrics dashboard."""
    p = _STATIC / "metrics.html"
    if not p.exists():
        return HTMLResponse("<h1>metrics.html not found</h1>", status_code=404)
    return HTMLResponse(p.read_text(encoding="utf-8"))


@app.get("/api/metrics")
async def api_metrics(limit: int = 100):
    """Return recent inference records and session summary."""
    from src.utils.metrics import get_recent_runs, get_summary
    return {
        "summary": get_summary(),
        "runs": get_recent_runs(limit=min(limit, _RING_SIZE)),
    }


_RING_SIZE = 500  # matches src/utils/metrics.py _RING_SIZE

# ── LLM provider comparison ────────────────────────────────────────────────

class CompareRequest(BaseModel):
    question: str
    domain: str = _DEFAULT_DOMAIN
    language: str = "id"
    provider_a: str = ""
    model_a: str = ""
    base_url_a: str = ""
    api_key_a: str = ""
    provider_b: str = ""
    model_b: str = ""
    base_url_b: str = ""
    api_key_b: str = ""


@app.post("/api/compare")
async def api_compare(body: CompareRequest):
    """Run the same question against two LLM provider configs and return both answers.

    Used by the provider comparison panel in the Data Explorer.
    Runs both providers in parallel via ThreadPoolExecutor.
    """
    import concurrent.futures
    from src.orchestration.answer_builder import prepare_answer, finalize_answer
    from src.llm.inference_client import get_llm_client
    from src.llm.base import BaseLLMClient

    domain = body.domain if body.domain in DOMAIN_CONFIG else _DEFAULT_DOMAIN
    domain_tables = DOMAIN_CONFIG[domain]["tables"]

    # Build an ad-hoc LLM client from explicit provider config
    def _make_client(provider: str, model: str, base_url: str, api_key: str) -> BaseLLMClient:
        if not provider:
            return get_llm_client()  # use configured default
        import os as _os
        # Temporarily inject env vars for this thread
        saved = {k: _os.environ.get(k) for k in ("LLM_PROVIDER", "LLM_MODEL_ID", "LLM_BASE_URL", "LLM_API_KEY")}
        _os.environ["LLM_PROVIDER"] = provider
        if model:     _os.environ["LLM_MODEL_ID"]  = model
        if base_url:  _os.environ["LLM_BASE_URL"]  = base_url
        if api_key:   _os.environ["LLM_API_KEY"]   = api_key
        try:
            client = get_llm_client()
        finally:
            for k, v in saved.items():
                if v is None: _os.environ.pop(k, None)
                else: _os.environ[k] = v
        return client

    def _run_one(label: str, provider: str, model: str, base_url: str, api_key: str) -> dict:
        t0 = time.monotonic()
        try:
            client = _make_client(provider, model, base_url, api_key)
            prep = prepare_answer(body.question, domain=domain, domain_tables=domain_tables, language=body.language)
            from src.orchestration.answer_builder import _build_messages
            messages = _build_messages(prep)
            resp = client.chat(messages, temperature=0.2, max_tokens=1024)
            result = finalize_answer(prep, resp.content)
            return {
                "label": label, "ok": True,
                "answer": resp.content,
                "mode": prep.mode,
                "latency_ms": round((time.monotonic() - t0) * 1000),
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "model": resp.model or model or "unknown",
            }
        except Exception as exc:
            return {"label": label, "ok": False, "error": str(exc),
                    "latency_ms": round((time.monotonic() - t0) * 1000)}

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(_run_one, "A", body.provider_a, body.model_a, body.base_url_a, body.api_key_a)
        fut_b = pool.submit(_run_one, "B", body.provider_b, body.model_b, body.base_url_b, body.api_key_b)
        result_a = await loop.run_in_executor(None, fut_a.result)
        result_b = await loop.run_in_executor(None, fut_b.result)

    return {"a": result_a, "b": result_b, "question": body.question}


@app.get("/api/logs")
async def api_logs(level: str = "DEBUG", limit: int = 200):
    """Return recent in-memory log entries for the troubleshooting panel.

    Query params:
      level  — minimum log level: DEBUG | INFO | WARNING | ERROR  (default: DEBUG)
      limit  — max number of entries to return, newest first  (default: 200)
    """
    from src.config.logging import get_log_entries
    entries = get_log_entries(min_level=level, limit=min(limit, 500))
    return {"entries": entries, "total": len(entries)}


def _services_starting_up() -> bool:
    """True when running in Docker/CML mode and data services are not yet ready."""
    return settings.query_engine == "trino" and not _SERVICES_READY_FLAG.exists()


@app.post("/api/chat", tags=["chat"])
async def api_chat(body: ChatRequest, request: Request):
    """Stream a chat response via Server-Sent Events."""
    client_ip = (request.client.host if request.client else "unknown")
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment before sending another question.",
        )

    # Gate: in Docker/CML mode, block chat until MinIO/Nessie/Trino are ready.
    # Emit a friendly SSE error rather than a silent connection failure.
    if _services_starting_up():
        uptime = round(time.monotonic() - _STARTUP_TIME)
        msg = (
            f"Data services are starting up ({uptime}s since launch). "
            "Trino, MinIO, and Nessie require 3-5 minutes on first startup. "
            "Open /setup to view live component status."
        )
        async def _starting_up_sse():
            yield _sse("error", {"message": msg})
        return StreamingResponse(
            _starting_up_sse(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    domain = body.domain if body.domain in DOMAIN_CONFIG else _DEFAULT_DOMAIN
    domain_tables = DOMAIN_CONFIG[domain]["tables"]
    # "all" domain: pass None so retrieve() skips domain filtering
    retrieval_domain: str | None = None if domain == "all" else domain
    return StreamingResponse(
        _chat_sse(body.question, body.history, domain=domain,
                  retrieval_domain=retrieval_domain,
                  domain_tables=domain_tables, language=body.language,
                  style=body.style),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _chat_sse(
    question: str,
    history: list[dict],
    domain: str = _DEFAULT_DOMAIN,
    retrieval_domain: str | None = _DEFAULT_DOMAIN,
    domain_tables: list[str] | None = None,
    language: str = "id",
    style: str = "analyst",
) -> AsyncGenerator[str, None]:
    """Run the three-phase RAG pipeline and yield SSE events.

    Events emitted:
      mode   — classification result (dokumen / data / gabungan)
      token  — one LLM output chunk
      done   — citations payload, marks end of stream
      error  — error message if pipeline fails
    """
    _t_start = time.monotonic()
    loop = asyncio.get_event_loop()
    try:
        # Phase 1 — classify + retrieve (blocking, run in thread pool)
        prep = await loop.run_in_executor(
            None, prepare_answer, question, history, 5, retrieval_domain, domain_tables, language, style
        )
        yield _sse("mode", {"mode": prep.mode})

        # Phase 2 — stream LLM tokens from a producer thread via a queue
        token_q: queue.Queue[str | None] = queue.Queue()

        def _produce() -> None:
            try:
                for tok in stream_synthesis(prep):
                    token_q.put(tok)
            except Exception as exc:
                logger.error("stream_synthesis error: %s", exc)
                # Put error tuple before the done-sentinel so the consumer can
                # emit an error SSE event instead of silently ending the stream.
                token_q.put(("__error__", str(exc)))
            finally:
                token_q.put(None)  # sentinel — always signals completion

        thread = threading.Thread(target=_produce, daemon=True)
        thread.start()

        think_filter = _ThinkingFilter()
        full_text = ""
        was_thinking = False
        while True:
            item = await loop.run_in_executor(None, token_q.get)
            if item is None:
                break
            # Error sentinel emitted by _produce on mid-stream failure
            if isinstance(item, tuple) and item[0] == "__error__":
                yield _sse("error", {"message": item[1]})
                break
            tok = item
            full_text += tok
            visible = think_filter.feed(tok)
            # Notify frontend when model enters or exits a thinking block
            if think_filter.thinking and not was_thinking:
                yield _sse("thinking", {"active": True})
            elif not think_filter.thinking and was_thinking:
                yield _sse("thinking", {"active": False})
            was_thinking = think_filter.thinking
            if visible:
                yield _sse("token", {"text": visible})

        # Flush any text held in the lookahead buffer
        tail = think_filter.flush()
        if tail:
            yield _sse("token", {"text": tail})

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
                "score": round(c.score, 3),
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

        # Token-usage estimate — 1 token ≈ 4 characters (rough but consistent).
        # synthesis_input_chars is set by stream_synthesis before streaming begins.
        estimated_input  = prep.synthesis_input_chars // 4
        estimated_output = len(full_text) // 4
        usage = {
            "input_tokens":  estimated_input,
            "output_tokens": estimated_output,
            "total_tokens":  estimated_input + estimated_output,
        }

        with _stats_lock:
            _session_stats["total_requests"] += 1
            _session_stats["input_tokens"]   += usage["input_tokens"]
            _session_stats["output_tokens"]  += usage["output_tokens"]
            _session_stats["total_tokens"]   += usage["total_tokens"]

        # Fire-and-forget MLflow + in-memory metrics logging
        _log_inference(
            domain=domain,
            language=language,
            mode=result.mode,
            provider=settings._live_provider,
            model=settings.llm_model_id,
            latency_ms=round((time.monotonic() - _t_start) * 1000),
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            doc_citations=len(result.doc_citations or []),
            has_sql=result.sql_citation is not None,
        )

        yield _sse("done", {
            "doc_citations": doc_cits,
            "sql_citation":  sql_cit,
            "usage":         usage,
        })

    except Exception as exc:
        logger.exception("Chat SSE pipeline error")
        yield _sse("error", {"message": str(exc)})


@app.post("/api/restart")
async def api_restart():
    """Restart the uvicorn server by spawning a fully detached launcher process.

    Windows strategy: use PowerShell Start-Process, which creates a top-level
    process independent of any Windows Job Object that may be attached to the
    current uvicorn process.  A Start-Sleep 3 inside the PowerShell command
    gives the current process time to exit and release the port before the new
    server starts.

    Linux/macOS strategy: sh -c with sleep + start_new_session=True.

    The current process exits via os._exit(0) after the launcher is confirmed
    running, releasing the port for the new server.
    """
    import subprocess as _sp

    cwd      = str(Path.cwd())
    port     = settings.app_port
    exe      = sys.executable

    def _do_restart() -> None:
        import time
        time.sleep(0.4)   # let the HTTP response flush before we exit

        # When uvicorn runs with --reload there is a parent reloader process that
        # holds the TCP socket.  If we only exit the worker (os._exit), the reloader
        # immediately spawns a replacement worker, keeps the port, and the new
        # uvicorn launched by PowerShell/sh below cannot bind — the restart silently
        # fails.  The fix: tell the launcher script to also kill the parent (reloader)
        # PID before starting the fresh server.
        parent_pid = os.getppid()

        try:
            if sys.platform == "win32":
                # Kill the current worker + its reloader parent, then start fresh.
                #
                # Sequence:
                #   1. Start-Sleep 1 — give the worker time to exit via os._exit(0)
                #   2. taskkill /F /PID <ppid> /T — kill reloader + any new worker it
                #      might have spawned; /T kills the whole process tree
                #   3. Start-Sleep 1 — let the port release
                #   4. Start-Process — launch fresh uvicorn (no --reload in prod mode)
                #
                # Flag rationale:
                #   CREATE_NO_WINDOW (0x08000000) — hides the window but keeps an
                #     internal console context so PowerShell can execute normally.
                #     DETACHED_PROCESS must NOT be used — PowerShell exits immediately
                #     if no console is attached.
                #   CREATE_NEW_PROCESS_GROUP (0x00000200) — new Ctrl-C group.
                #   CREATE_BREAKAWAY_FROM_JOB (0x01000000) — escapes VS Code / CI
                #     Job Objects so the process survives parent exit.
                ps_cmd = (
                    f"Start-Sleep -Seconds 1; "
                    f"taskkill /F /PID {parent_pid} /T 2>$null; "
                    f"Start-Sleep -Seconds 1; "
                    f"Start-Process "
                    f"-FilePath '{exe}' "
                    f"-ArgumentList '-m uvicorn app.api:app --host 0.0.0.0 --port {port}' "
                    f"-WorkingDirectory '{cwd}' "
                    f"-NoNewWindow"
                )
                flags = 0x08000000 | 0x00000200 | 0x01000000
                try:
                    _sp.Popen(
                        ['powershell', '-NoProfile', '-NonInteractive', '-Command', ps_cmd],
                        stdin=_sp.DEVNULL, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                        creationflags=flags,
                    )
                except OSError:
                    # CREATE_BREAKAWAY_FROM_JOB denied — retry without it.
                    _sp.Popen(
                        ['powershell', '-NoProfile', '-NonInteractive', '-Command', ps_cmd],
                        stdin=_sp.DEVNULL, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                        creationflags=0x08000000 | 0x00000200,
                    )
            else:
                # Unix: kill the reloader (parent) and start fresh.
                sh_cmd = (
                    f"sleep 1 && "
                    f"kill -9 {parent_pid} 2>/dev/null; "
                    f"sleep 1 && "
                    f"cd '{cwd}' && "
                    f"'{exe}' -m uvicorn app.api:app --host 0.0.0.0 --port {port}"
                )
                _sp.Popen(
                    ['sh', '-c', sh_cmd],
                    stdin=_sp.DEVNULL, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                    start_new_session=True,
                )
            logger.info("Restart launcher spawned; shutting down current process")
        except Exception as exc:
            logger.error("Failed to launch restart helper: %s", exc)
            return
        os._exit(0)

    threading.Thread(target=_do_restart, daemon=True).start()
    return {"restarting": True, "message": "Application is restarting. Page will reload automatically."}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class _ThinkingFilter:
    """Strip <think>…</think> blocks from a streamed token sequence.

    Some reasoning models (e.g. Nemotron, DeepSeek-R1) emit their chain-of-thought
    inside <think> tags before the actual answer.  This filter discards those blocks
    so only the final answer reaches the frontend.

    Nesting is handled via a depth counter so nested <think> blocks (produced by
    some o1-class models) are fully discarded rather than leaking inner open tags.

    Usage — call feed(tok) for each incoming token; it returns the text to emit
    (may be empty string while inside a thinking block).  Call flush() after the
    last token to release any text held in the lookahead buffer.
    """

    _OPEN  = "<think>"
    _CLOSE = "</think>"

    def __init__(self) -> None:
        self._buf   = ""
        self._depth = 0   # nesting depth; 0 = normal output

    @property
    def thinking(self) -> bool:
        return self._depth > 0

    @staticmethod
    def _tail_overlap(s: str, tag: str) -> int:
        """Return the length of the longest suffix of s that is a prefix of tag."""
        for n in range(min(len(tag) - 1, len(s)), 0, -1):
            if s.endswith(tag[:n]):
                return n
        return 0

    def feed(self, tok: str) -> str:
        self._buf += tok
        out = ""
        while self._buf:
            if self._depth > 0:
                close_idx = self._buf.find(self._CLOSE)
                open_idx  = self._buf.find(self._OPEN)
                # Handle whichever tag comes first
                if close_idx >= 0 and (open_idx < 0 or close_idx <= open_idx):
                    self._depth -= 1
                    after = self._buf[close_idx + len(self._CLOSE):]
                    self._buf = after.lstrip("\n") if self._depth == 0 else after
                elif open_idx >= 0:
                    self._depth += 1
                    self._buf = self._buf[open_idx + len(self._OPEN):]
                else:
                    # Hold back any potential partial tag at the tail
                    hold = max(
                        self._tail_overlap(self._buf, self._CLOSE),
                        self._tail_overlap(self._buf, self._OPEN),
                    )
                    self._buf = self._buf[-hold:] if hold else ""
                    break
            else:
                idx = self._buf.find(self._OPEN)
                if idx >= 0:
                    out += self._buf[:idx]
                    self._depth += 1
                    self._buf = self._buf[idx + len(self._OPEN):]
                else:
                    hold = self._tail_overlap(self._buf, self._OPEN)
                    if hold:
                        out += self._buf[:-hold]
                        self._buf = self._buf[-hold:]
                    else:
                        out += self._buf
                        self._buf = ""
                    break
        return out

    def flush(self) -> str:
        """Release any buffered text that isn't inside a thinking block."""
        if self._depth == 0:
            result, self._buf = self._buf, ""
            return result
        return ""
