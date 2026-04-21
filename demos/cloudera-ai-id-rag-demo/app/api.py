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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from sqlalchemy import text as sa_text

from src.config.logging import setup_logging
from src.config.settings import settings
from src.orchestration.answer_builder import prepare_answer, stream_synthesis, finalize_answer

setup_logging()
logger = logging.getLogger(__name__)

_STATIC = Path(__file__).parent / "static"

# Cache index.html content at startup — avoids a disk read on every GET /
_INDEX_HTML: str = ""

# Server start time — used by /api/status to expose uptime for fast-poll logic
_STARTUP_TIME: float = time.monotonic()

# Persistent config override file — written by POST /api/configure,
# sourced by launch_app.sh on every restart.
_OVERRIDE_PATH = Path("data/.env.local")

# Services-ready sentinel written by entrypoint.sh after MinIO/Nessie/Trino/seed
# complete.  Only enforced in Docker/CML mode (QUERY_ENGINE=trino).
# In SQLite mode this file is never written and the gate is bypassed.
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


# ── Domain configuration ───────────────────────────────────────────────────

# Tables visible to SQL generation per domain.  Documents are filtered by the
# same domain key stored in chunk metadata (set during ingestion).
DOMAIN_CONFIG: dict[str, dict] = {
    "banking": {
        "label": "Banking",
        "tables": ["kredit_umkm", "nasabah", "cabang"],
    },
    "telco": {
        "label": "Telco",
        "tables": ["pelanggan", "penggunaan_data", "jaringan"],
    },
    "government": {
        "label": "Government",
        "tables": ["penduduk", "anggaran_daerah", "layanan_publik"],
    },
}

_DEFAULT_DOMAIN = "banking"


# ── Sample prompts ─────────────────────────────────────────────────────────

# Each entry: domain, mode (routing hint), text_id (Bahasa), text_en (English)
_SAMPLES: list[dict] = [
    # ── Banking ───────────────────────────────────────────────────────────
    {"domain": "banking", "mode": "dokumen",
     "text_id": "Apa saja syarat pengajuan kredit UMKM dan dokumen yang wajib dilengkapi?",
     "text_en": "What are the MSME credit requirements and mandatory documents?"},
    {"domain": "banking", "mode": "dokumen",
     "text_id": "Bagaimana prosedur restrukturisasi kredit jika debitur mengalami kesulitan pembayaran?",
     "text_en": "What is the credit restructuring procedure when a debtor has payment difficulties?"},
    {"domain": "banking", "mode": "data",
     "text_id": "Berapa total outstanding kredit UMKM di Jakarta per Maret 2026?",
     "text_en": "What is the total outstanding MSME credit in Jakarta as of March 2026?"},
    {"domain": "banking", "mode": "data",
     "text_id": "Tampilkan 5 nasabah dengan total eksposur kredit tertinggi.",
     "text_en": "Show the top 5 customers by total credit exposure."},
    {"domain": "banking", "mode": "gabungan",
     "text_id": "Apakah outstanding kredit UMKM di Jakarta sudah sesuai target ekspansi 15% yang ditetapkan kebijakan 2026?",
     "text_en": "Does the Jakarta MSME credit outstanding align with the 15% expansion target set by the 2026 policy?"},
    {"domain": "banking", "mode": "gabungan",
     "text_id": "Bagaimana kualitas kredit di Bandung dibandingkan kondisi yang memenuhi syarat restrukturisasi menurut kebijakan bank?",
     "text_en": "How does Bandung's credit quality compare to the restructuring eligibility conditions per bank policy?"},
    # ── Telco ─────────────────────────────────────────────────────────────
    {"domain": "telco", "mode": "dokumen",
     "text_id": "Apa saja standar waktu penanganan keluhan pelanggan yang ditetapkan dalam SLA?",
     "text_en": "What are the customer complaint resolution time standards defined in the SLA?"},
    {"domain": "telco", "mode": "dokumen",
     "text_id": "Bagaimana kebijakan retensi pelanggan dan syarat mendapatkan diskon perpanjangan kontrak?",
     "text_en": "What is the customer retention policy and the conditions for contract renewal discounts?"},
    {"domain": "telco", "mode": "data",
     "text_id": "Tampilkan utilisasi jaringan per wilayah dan identifikasi wilayah yang mendekati kapasitas kritis.",
     "text_en": "Show network utilization by region and identify areas approaching critical capacity."},
    {"domain": "telco", "mode": "data",
     "text_id": "Berapa pelanggan dengan churn risk score di atas 70 dan di wilayah mana saja?",
     "text_en": "How many subscribers have a churn risk score above 70 and in which regions?"},
    {"domain": "telco", "mode": "gabungan",
     "text_id": "Apakah utilisasi jaringan di Bali sudah melampaui batas SLA ketersediaan yang ditetapkan dalam kebijakan?",
     "text_en": "Has network utilization in Bali exceeded the availability SLA threshold defined in the policy?"},
    {"domain": "telco", "mode": "gabungan",
     "text_id": "Pelanggan mana yang berisiko churn tinggi dan apakah mereka memenuhi syarat program retensi berdasarkan kebijakan?",
     "text_en": "Which high-churn-risk subscribers qualify for the retention program based on the policy criteria?"},
    # ── Government ────────────────────────────────────────────────────────
    {"domain": "government", "mode": "dokumen",
     "text_id": "Berapa standar waktu penyelesaian layanan KTP elektronik dan apa kompensasi jika terlambat?",
     "text_en": "What is the processing time standard for electronic ID cards and what compensation is given for delays?"},
    {"domain": "government", "mode": "dokumen",
     "text_id": "Apa saja kanal pengaduan yang tersedia dan bagaimana prosedur penanganannya?",
     "text_en": "What complaint channels are available and what is the handling procedure?"},
    {"domain": "government", "mode": "data",
     "text_id": "Tampilkan realisasi anggaran per satuan kerja dan identifikasi yang realisasinya di bawah target.",
     "text_en": "Show budget realization per work unit and identify those below target."},
    {"domain": "government", "mode": "data",
     "text_id": "Layanan publik mana yang memiliki tingkat kepuasan masyarakat terendah per Maret 2026?",
     "text_en": "Which public services have the lowest citizen satisfaction rate as of March 2026?"},
    {"domain": "government", "mode": "gabungan",
     "text_id": "Apakah layanan IMB sudah memenuhi standar waktu dan IKM yang ditetapkan dalam kebijakan pelayanan publik?",
     "text_en": "Does the building permit (IMB) service meet the processing time and satisfaction standards set by the public service policy?"},
    {"domain": "government", "mode": "gabungan",
     "text_id": "Satuan kerja mana yang realisasi anggarannya rendah dan apakah ada risiko penalti sesuai regulasi APBD?",
     "text_en": "Which work units have low budget realization and face penalty risk under the APBD regulation?"},
]


# ── Request model ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []
    domain: str = _DEFAULT_DOMAIN
    language: str = "id"


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
            latency_ms = round((_time.monotonic() - t0) * 1000)
            return {"ok": True, "tables": tables_info, "latency_ms": latency_ms, "fix": None}
        except Exception as exc:
            return {"ok": False, "tables": [], "latency_ms": None,
                    "fix": f"Check DATABASE_URL. Error: {exc}"}

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


_MODE_ORDER = {"dokumen": 0, "data": 1, "gabungan": 2}


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
    """Return available domain configurations for the frontend dropdown."""
    return [
        {"id": k, "label": v["label"]}
        for k, v in DOMAIN_CONFIG.items()
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


_ingest_state: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "last_result": None,
}
_ingest_lock = threading.Lock()


class IngestRequest(BaseModel):
    reseed_db: bool = False


@app.post("/api/ingest")
async def api_ingest(body: IngestRequest = IngestRequest()):
    """Rebuild the FAISS vector store from source documents in the background.

    Source documents (in MinIO or local filesystem) are NOT deleted — only the
    FAISS index files are overwritten.  Optionally also re-seeds the SQLite
    database when reseed_db=true and QUERY_ENGINE != trino.

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

            if body.reseed_db and settings.query_engine != "trino":
                logger.info("Ingest API: re-seeding SQLite database...")
                import importlib.util as _ilu
                _seed_path = Path(__file__).parent.parent / "data/sample_tables/seed_database.py"
                _spec = _ilu.spec_from_file_location("_seed_db", _seed_path)
                _mod = _ilu.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                _mod.seed()
                logger.info("Ingest API: database re-seeded.")

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
            detail="Terlalu banyak permintaan. Tunggu sebentar sebelum mengirim pertanyaan berikutnya.",
        )

    # Gate: in Docker/CML mode, block chat until MinIO/Nessie/Trino are ready.
    # Emit a friendly SSE error rather than a silent connection failure.
    if _services_starting_up():
        uptime = round(time.monotonic() - _STARTUP_TIME)
        msg = (
            f"Layanan data sedang disiapkan ({uptime}s sejak mulai). "
            "Trino, MinIO, dan Nessie memerlukan 3–5 menit untuk startup pertama. "
            "Buka /setup untuk melihat status komponen secara langsung."
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
    return StreamingResponse(
        _chat_sse(body.question, body.history, domain=domain, domain_tables=domain_tables, language=body.language),
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
    domain_tables: list[str] | None = None,
    language: str = "id",
) -> AsyncGenerator[str, None]:
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
        prep = await loop.run_in_executor(
            None, prepare_answer, question, history, 5, domain, domain_tables, language
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
