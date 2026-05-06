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
        "tables": ["msme_credit", "customer", "branch", "loan_application"],
    },
    "telco": {
        "label": "Telco",
        "tables": ["subscriber", "data_usage", "network", "network_incident"],
    },
    "government": {
        "label": "Government",
        "tables": ["resident", "regional_budget", "public_service"],
    },
    "all": {
        "label": "All Domains",
        "tables": [
            "msme_credit", "customer", "branch", "loan_application",
            "subscriber", "data_usage", "network", "network_incident",
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
     "text_id": "Apa syarat restrukturisasi kredit UMKM dan bagaimana prosedur pengajuannya?",
     "text_en": "What are the MSME credit restructuring conditions and how is the application process?"},
    {"domain": "banking", "mode": "data",
     "text_id": "Tampilkan peta risiko NPL kredit UMKM per kota seluruh Indonesia bulan Maret 2026.",
     "text_en": "Show the MSME credit NPL risk heatmap by city across Indonesia for March 2026."},
    {"domain": "banking", "mode": "data",
     "text_id": "Kota mana yang memiliki NPL di atas 8% DAN volume kredit di atas 5 triliun? Tampilkan dual-risk hotspot.",
     "text_en": "Which cities have NPL above 8% AND credit volume above 5 trillion? Show dual-risk hotspots."},
    {"domain": "banking", "mode": "data",
     "text_id": "Bandingkan ROI cabang vs NPL rate — cabang mana yang paling dan paling tidak efisien?",
     "text_en": "Compare branch ROI versus NPL rate — which branches are most and least efficient?"},
    {"domain": "banking", "mode": "data",
     "text_id": "Tampilkan tingkat persetujuan KUR per kota dan jenis pinjaman — identifikasi kota dengan backlog tinggi.",
     "text_en": "Show KUR loan approval rate by city and type — identify cities with processing backlogs."},
    {"domain": "banking", "mode": "data",
     "text_id": "Nasabah dengan debt service ratio di atas 45% dan rating B atau B- — siapa yang paling berisiko?",
     "text_en": "Customers with debt service ratio above 45% and rating B or B- — who faces the highest systemic risk?"},
    {"domain": "banking", "mode": "combined",
     "text_id": "Kota mana yang NPL-nya melebihi ambang batas 5% OJK? Berapa potensi kerugian yang harus dicadangkan?",
     "text_en": "Which cities breach the OJK 5% NPL threshold? What is the estimated provision requirement?"},
    {"domain": "banking", "mode": "combined",
     "text_id": "Apakah outstanding kredit UMKM di Jakarta sudah sesuai target ekspansi 15% kebijakan 2026?",
     "text_en": "Does Jakarta MSME credit outstanding meet the 15% expansion target set by the 2026 policy?"},
    {"domain": "banking", "mode": "combined",
     "text_id": "Bagaimana kualitas kredit di Bandung dibandingkan syarat restrukturisasi menurut kebijakan bank?",
     "text_en": "How does Bandung credit quality compare to the restructuring eligibility conditions per bank policy?"},
    # ── Telco ─────────────────────────────────────────────────────────────
    {"domain": "telco", "mode": "document",
     "text_id": "Apa saja standar SLA penanganan keluhan P1 dan P2, dan apa sanksi pelanggarannya?",
     "text_en": "What are the P1 and P2 complaint SLA standards and what are the penalty provisions?"},
    {"domain": "telco", "mode": "data",
     "text_id": "Tampilkan composite risk score jaringan: utilisasi × packet loss per kota — identifikasi hotspot kritis.",
     "text_en": "Show network composite risk score: utilization × packet loss by city — identify critical hotspots."},
    {"domain": "telco", "mode": "data",
     "text_id": "Hitung revenue at risk: total ARPU pelanggan churn score >70 per kota, beserta rata-rata tenure mereka.",
     "text_en": "Calculate revenue at risk: total ARPU of high-churn subscribers (score >70) per city with average tenure."},
    {"domain": "telco", "mode": "data",
     "text_id": "Tampilkan insiden jaringan dan pelanggaran SLA per kota — kota mana yang MTTR-nya paling buruk?",
     "text_en": "Show network incidents and SLA breaches by city — which cities have the worst mean time to resolve?"},
    {"domain": "telco", "mode": "combined",
     "text_id": "Kota mana yang utilisasi jaringan kritis DAN banyak pelanggan Corporate/Postpaid yang berisiko churn?",
     "text_en": "Which cities have critical network utilization AND significant Corporate/Postpaid churn risk — compounding threat?"},
    {"domain": "telco", "mode": "combined",
     "text_id": "Pelanggan baru (<12 bulan) dengan churn risk >70 — berapa total revenue yang terancam dan apakah memenuhi syarat retensi?",
     "text_en": "New subscribers (<12 months tenure) with churn risk >70 — total revenue threatened and do they qualify for retention?"},
    # ── Government ────────────────────────────────────────────────────────
    {"domain": "government", "mode": "document",
     "text_id": "Berapa standar waktu layanan IMB dan KTP, dan apa kompensasi jika melewati batas?",
     "text_en": "What are the IMB and KTP service time standards, and what compensation applies for delays?"},
    {"domain": "government", "mode": "data",
     "text_id": "Tampilkan layanan publik dengan backlog tertinggi dan kepuasan terendah — identifikasi bottleneck operasional.",
     "text_en": "Show public services with highest backlog and lowest satisfaction — identify operational bottlenecks."},
    {"domain": "government", "mode": "data",
     "text_id": "Realisasi anggaran per satuan kerja: identifikasi yang di bawah target Q3 70% dan berisiko penalti.",
     "text_en": "Budget realization per work unit: identify those below the Q3 70% target and at penalty risk."},
    {"domain": "government", "mode": "combined",
     "text_id": "Layanan IMB: apakah waktu proses dan skor IKM sudah memenuhi standar kebijakan pelayanan publik 2026?",
     "text_en": "IMB service: do processing time and IKM satisfaction score meet the 2026 public service policy standards?"},
    {"domain": "government", "mode": "combined",
     "text_id": "Satuan kerja mana yang realisasinya rendah DAN memiliki pengaduan layanan tertinggi — risiko ganda?",
     "text_en": "Which work units have low budget realization AND highest service complaints — compounding governance risk?"},
    # ── All domains — cross-domain intelligence ───────────────────────────
    {"domain": "all", "mode": "data",
     "text_id": "Tampilkan economic stress index per kota: gabungkan NPL kredit, churn risk telco, dan keluhan layanan publik.",
     "text_en": "Show economic stress index by city: combine MSME NPL, telco churn risk, and public service complaints."},
    {"domain": "all", "mode": "data",
     "text_id": "Kota mana yang infrastruktur digitalnya (jaringan) paling tertinggal dibanding aktivitas ekonomi (kredit UMKM)?",
     "text_en": "Which cities have the biggest gap between digital infrastructure (network) and economic activity (MSME credit)?"},
]


# ── Request model ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []
    domain: str = _DEFAULT_DOMAIN
    language: str = "id"
    style: str = "analyst"   # analyst | executive | compliance
    thinking: bool = False   # stream chain-of-thought via thinking_token SSE events
    image_b64: str | None = None  # base64-encoded image for vision queries


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


# ── Debate: Researcher + Critic + Synthesis ──────────────────────────────

_DEBATE_RESEARCHER_SYSTEM = """\
You are a thorough Research Agent. Summarise the retrieved evidence below into a \
clear, structured briefing of 3-5 bullet points. Be factual and cite specific numbers.
Reply in {lang_rule}."""

_DEBATE_CRITIC_SYSTEM = """\
You are a rigorous Critic Agent. You have received a researcher's briefing. \
Your role is to challenge assumptions, highlight data gaps, flag alternative \
interpretations, and ask probing follow-up questions. Be concise: 3-4 crisp points.
Reply in {lang_rule}."""

_DEBATE_SYNTHESIS_SYSTEM = """\
You are a wise Synthesis Agent. You have both a researcher's briefing and a \
critic's challenges. Produce a final, balanced answer that:
- Acknowledges the strongest points from both perspectives
- Resolves genuine conflicts with clear reasoning
- Ends with a concrete recommendation or conclusion
Reply in {lang_rule}."""

_AGENT_SYNTH_SYSTEM = """\
You are a senior enterprise analyst. Using the multi-step research below, \
synthesise a comprehensive, well-structured answer. Cite specific steps with [Step N].
Reply in {lang_rule}."""


async def _debate_sse(
    question: str,
    history: list[dict],
    domain: str,
    retrieval_domain: str | None,
    domain_tables: list[str] | None,
    language: str,
    style: str,
) -> AsyncGenerator[str, None]:
    """Three-phase debate: Researcher → Critic → Synthesis."""
    from src.retrieval.retriever import retrieve
    from src.orchestration.answer_builder import _generate_sql_with_retry, _format_doc_context, _format_sql_summary
    from src.llm.inference_client import get_llm_client
    from src.llm.prompts import _lang_rule, _style_rule
    from src.orchestration.citations import build_document_citations, build_sql_citation
    import dataclasses

    loop = asyncio.get_event_loop()
    _t_start = time.monotonic()

    try:
        # ── Phase 1: Gather evidence (same as agent research) ─────────────
        yield _sse("debate_researcher_thinking", {"label": "Gathering and analysing evidence…"})

        doc_chunks = await loop.run_in_executor(None, retrieve, question, 5, retrieval_domain, language)
        qr = await loop.run_in_executor(None, _generate_sql_with_retry, question, domain_tables)

        doc_context = _format_doc_context(doc_chunks) if doc_chunks else "_No documents found._"
        sql_summary = _format_sql_summary(qr) if qr and qr.succeeded else "_No data found._"

        evidence = f"DOCUMENTS:\n{doc_context}\n\nDATA:\n{sql_summary}"
        lang_rule = _lang_rule(language)

        # Researcher LLM call (non-streaming for conciseness)
        llm = get_llm_client()
        researcher_resp = await loop.run_in_executor(
            None, lambda: llm.chat(
                [{"role": "system", "content": _DEBATE_RESEARCHER_SYSTEM.format(lang_rule=lang_rule)},
                 {"role": "user", "content": f"Evidence:\n{evidence}\n\nQuestion: {question}"}],
                temperature=0.2, max_tokens=600,
            )
        )
        researcher_text = researcher_resp.content.strip()
        yield _sse("debate_researcher_done", {"text": researcher_text})

        # ── Phase 2: Critic challenges the researcher ──────────────────────
        yield _sse("debate_critic_start", {})
        critic_text = ""
        critic_q: queue.Queue = queue.Queue()

        def _critic_produce():
            try:
                for tok in llm.stream_chat(
                    [{"role": "system", "content": _DEBATE_CRITIC_SYSTEM.format(lang_rule=lang_rule)},
                     {"role": "user", "content": f"Researcher's briefing:\n{researcher_text}\n\nOriginal question: {question}"}],
                    temperature=0.3, max_tokens=400,
                ):
                    critic_q.put(tok)
            except Exception as exc:
                critic_q.put(("__error__", str(exc)))
            finally:
                critic_q.put(None)

        critic_thread = threading.Thread(target=_critic_produce, daemon=True)
        critic_thread.start()
        while True:
            item = await loop.run_in_executor(None, critic_q.get)
            if item is None:
                break
            if isinstance(item, tuple) and item[0] == "__error__":
                break
            critic_text += item
            yield _sse("debate_critic_token", {"text": item})
        critic_thread.join(timeout=30)

        # ── Phase 3: Synthesis ─────────────────────────────────────────────
        yield _sse("debate_synthesis_start", {})
        sr = _style_rule(style)
        synth_system = _DEBATE_SYNTHESIS_SYSTEM.format(lang_rule=lang_rule)
        if sr:
            synth_system += f"\n{sr}"

        synth_messages = [
            {"role": "system", "content": synth_system},
            {"role": "user", "content": (
                f"Researcher's briefing:\n{researcher_text}\n\n"
                f"Critic's challenges:\n{critic_text}\n\n"
                f"Question: {question}"
            )},
        ]

        full_text = ""
        synth_q: queue.Queue = queue.Queue()

        def _synth_produce():
            try:
                for tok in llm.stream_chat(synth_messages, temperature=0.2, max_tokens=900):
                    synth_q.put(tok)
            except Exception as exc:
                synth_q.put(("__error__", str(exc)))
            finally:
                synth_q.put(None)

        synth_thread = threading.Thread(target=_synth_produce, daemon=True)
        synth_thread.start()
        while True:
            item = await loop.run_in_executor(None, synth_q.get)
            if item is None:
                break
            if isinstance(item, tuple) and item[0] == "__error__":
                yield _sse("error", {"message": item[1]})
                break
            full_text += item
            yield _sse("token", {"text": item})
        synth_thread.join(timeout=60)

        # Build citations
        doc_cits = build_document_citations(doc_chunks) if doc_chunks else []
        sql_cit  = build_sql_citation(qr) if qr and qr.succeeded else None

        input_est  = (len(evidence) + len(researcher_text) + len(critic_text)) // 4
        output_est = len(full_text) // 4
        usage = {"input_tokens": input_est, "output_tokens": output_est,
                 "total_tokens": input_est + output_est}

        with _stats_lock:
            _session_stats["total_requests"] += 1
            _session_stats["input_tokens"]   += usage["input_tokens"]
            _session_stats["output_tokens"]  += usage["output_tokens"]
            _session_stats["total_tokens"]   += usage["total_tokens"]

        total_ms = int((time.monotonic() - _t_start) * 1000)
        yield _sse("done", {
            "doc_citations": [dataclasses.asdict(c) for c in doc_cits] if doc_cits else [],
            "sql_citation":  dataclasses.asdict(sql_cit) if sql_cit else None,
            "latency_ms": total_ms,
            "usage": usage,
        })

    except Exception as exc:
        logger.exception("Debate pipeline error")
        yield _sse("error", {"message": str(exc)})


# ── Agent: Planner + Executor + Synthesizer ───────────────────────────────

_AGENT_PLAN_SYSTEM = """\
You are a research planner for an enterprise AI assistant.
Given a user question, create a focused research plan with 2-4 steps.

Available tools:
- "docs": Search internal policy/regulation/procedure documents
- "data": Query structured database tables (banking, telco, government)

Output ONLY a valid JSON array — no other text, no markdown fences:
[{"type":"docs"|"data","query":"natural language question in same language as user","label":"Short label"},...]

CRITICAL RULES:
- "query" field must be a NATURAL LANGUAGE QUESTION — NEVER write SQL in the query field
- Good data query example: "What is total outstanding credit by city in March 2026?"
- Good data query example: "Show network utilization per city"
- Bad data query example: "SELECT city, SUM(outstanding) FROM msme_credit GROUP BY city" — NEVER do this
- Maximum 4 steps, minimum 2
- Use "docs" for policy/procedure/regulation questions
- Use "data" for numbers, counts, rankings, current metrics
- Keep labels concise (< 8 words)
- Write queries in the same language as the user's question"""


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

        # Token-usage estimate for agent mode (1 token ≈ 4 chars)
        input_est  = (len(research_context) + len(messages[-1]["content"])) // 4
        output_est = len(full_text) // 4
        usage = {
            "input_tokens":  input_est,
            "output_tokens": output_est,
            "total_tokens":  input_est + output_est,
        }

        with _stats_lock:
            _session_stats["total_requests"] += 1
            _session_stats["input_tokens"]   += usage["input_tokens"]
            _session_stats["output_tokens"]  += usage["output_tokens"]
            _session_stats["total_tokens"]   += usage["total_tokens"]

        total_ms = int((time.monotonic() - _t_start) * 1000)
        yield _sse("done", {
            "doc_citations": [dataclasses.asdict(c) for c in doc_cits] if doc_cits else [],
            "sql_citation":  dataclasses.asdict(sql_cit) if sql_cit else None,
            "latency_ms": total_ms,
            "usage": usage,
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


@app.post("/api/debate/chat", tags=["chat"])
async def api_debate_chat(body: ChatRequest, request: Request):
    """Debate chat: Researcher gathers evidence → Critic challenges → Synthesis."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    domain = body.domain if body.domain in DOMAIN_CONFIG else _DEFAULT_DOMAIN
    domain_tables = DOMAIN_CONFIG[domain]["tables"]
    retrieval_domain: str | None = None if domain == "all" else domain

    return StreamingResponse(
        _debate_sse(body.question, body.history, domain=domain,
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


# ── Anomaly Detection ─────────────────────────────────────────────────────

_ANOMALY_SYSTEM = """\
You are an anomaly detection agent for enterprise data. Given a SQL query result table \
and the question that generated it, identify statistically notable anomalies, \
outliers, or concerning values.

Output ONLY a valid JSON array — no other text, no markdown fences:
[{"field":"<column>","value":"<value>","city":"<city or entity>","severity":"critical"|"warning"|"info","message":"<one sentence>"},...]

Severity guide:
- critical: breaches a known industry threshold or is >3x the average
- warning: unusually high/low compared to peers (1.5–3x)
- info: interesting but not alarming

Industry benchmarks to use when no explicit threshold is given:
- NPL rate: warning >5%, critical >10%
- Network utilization: warning >75%, critical >90%
- Budget absorption (Q4): warning <70%, critical <50%
- Churn risk score: warning >60, critical >80
- Packet loss: warning >1%, critical >2%
- Loan approval rate: warning <60%, critical <40%

Return [] if no genuine anomalies exist. Maximum 5 anomalies.
"""


class AnomalyRequest(BaseModel):
    table_markdown: str
    sql: str
    question: str
    domain: str = "banking"


# ── Forecast helpers ──────────────────────────────────────────────────────


def _linear_regression(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """Return (slope, intercept, r_squared) via ordinary least squares."""
    n = len(x)
    if n < 2:
        return 0.0, y[0] if y else 0.0, 0.0
    sum_x  = sum(x); sum_y  = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi ** 2 for xi in x)
    denom  = n * sum_x2 - sum_x ** 2
    if denom == 0:
        return 0.0, sum_y / n, 0.0
    slope     = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    y_mean    = sum_y / n
    ss_tot    = sum((yi - y_mean) ** 2 for yi in y)
    ss_res    = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
    r_sq      = max(0.0, 1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    return slope, intercept, round(r_sq, 3)


def _generate_future_labels(last_label: str, n: int) -> list[str]:
    """Extrapolate n period labels from the last one (YYYY-MM, YYYY-QN, or numeric)."""
    m = re.match(r"(\d{4})-(\d{2})$", last_label)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        out = []
        for _ in range(n):
            month += 1
            if month > 12:
                month = 1; year += 1
            out.append(f"{year:04d}-{month:02d}")
        return out
    m = re.match(r"(\d{4})-Q(\d)$", last_label)
    if m:
        year, q = int(m.group(1)), int(m.group(2))
        out = []
        for _ in range(n):
            q += 1
            if q > 4:
                q = 1; year += 1
            out.append(f"{year:04d}-Q{q}")
        return out
    return [f"{last_label}+{i + 1}" for i in range(n)]


@app.post("/api/forecast", tags=["analytics"])
async def api_forecast(body: dict):
    """Run linear regression on a time-series SQL result and project N periods ahead.

    Accepts:
      table_markdown — markdown table string from a sql_citation
      periods        — number of periods to project (default 3, max 6)
    """
    table_markdown = body.get("table_markdown", "")
    periods = min(int(body.get("periods", 3)), 6)

    lines = [l for l in table_markdown.strip().splitlines() if l.strip().startswith("|")]
    if len(lines) < 4:
        return {"ok": False, "error": "Need at least 2 data rows for forecasting"}

    def parse_cells(line: str) -> list[str]:
        return [c.strip() for c in line.split("|")[1:-1]]

    headers = parse_cells(lines[0])
    rows    = [parse_cells(l) for l in lines[2:]]

    # Locate time column
    time_col = next(
        (i for i, h in enumerate(headers) if re.search(r"month|year|date|period|quarter|bulan|tahun", h, re.I)),
        -1,
    )
    if time_col == -1:
        return {"ok": False, "error": "No time column detected"}

    # Locate first numeric column
    val_col = -1
    skip = {"lat", "lon", "id", "year"}
    for i, h in enumerate(headers):
        if i == time_col or h.lower() in skip:
            continue
        try:
            float(rows[0][i].replace(",", ""))
            val_col = i; break
        except Exception:
            pass
    if val_col == -1:
        return {"ok": False, "error": "No numeric column detected"}

    time_labels = [r[time_col] for r in rows if time_col < len(r)]
    values: list[float | None] = []
    for r in rows:
        try:
            values.append(float(r[val_col].replace(",", ""))) if val_col < len(r) else values.append(None)
        except Exception:
            values.append(None)

    clean = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(clean) < 2:
        return {"ok": False, "error": "Not enough numeric data points"}

    xs, ys = [p[0] for p in clean], [p[1] for p in clean]
    slope, intercept, r_squared = _linear_regression(xs, ys)

    avg = sum(ys) / len(ys)
    threshold = max(abs(avg) * 0.005, 1e-6)
    trend = "up" if slope > threshold else ("down" if slope < -threshold else "flat")

    future_labels = _generate_future_labels(time_labels[-1] if time_labels else "", periods)
    n = len(values)

    historical = [
        {"label": time_labels[i] if i < len(time_labels) else str(i),
         "value": values[i], "is_forecast": False}
        for i in range(n)
    ]
    forecast = [
        {"label": future_labels[j],
         "value": round(slope * (n + j) + intercept, 4),
         "is_forecast": True}
        for j in range(periods)
    ]

    return {
        "ok":           True,
        "historical":   historical,
        "forecast":     forecast,
        "combined":     historical + forecast,
        "trend":        trend,
        "slope":        round(slope, 6),
        "r_squared":    r_squared,
        "value_column": headers[val_col] if val_col < len(headers) else "value",
        "time_column":  headers[time_col] if time_col < len(headers) else "period",
        "periods":      periods,
    }


@app.post("/api/anomaly", tags=["chat"])
async def api_anomaly(body: AnomalyRequest):
    """Scan a SQL result table for anomalies using a fast LLM call."""
    try:
        from src.llm.inference_client import get_llm_client
        llm = get_llm_client()
        user_msg = (
            f"Question: {body.question}\n\n"
            f"SQL: {body.sql}\n\n"
            f"Result table:\n{body.table_markdown}"
        )
        resp = llm.chat(
            [{"role": "system", "content": _ANOMALY_SYSTEM},
             {"role": "user",   "content": user_msg}],
            temperature=0.1, max_tokens=600,
        )
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.splitlines()[1:])
            raw = raw.rsplit("```", 1)[0]
        import json as _json
        anomalies = _json.loads(raw.strip())
        if not isinstance(anomalies, list):
            anomalies = []
        return {"anomalies": anomalies[:5]}
    except Exception as exc:
        logger.warning("Anomaly detection failed: %s", exc)
        return {"anomalies": []}


# ── Executive Dashboard KPIs ───────────────────────────────────────────────

_DASHBOARD_EXEC_SYSTEM = """\
You are a CFO-level AI analyst. Given real-time KPI data from three enterprise domains \
(banking, telco, government), write a concise executive briefing of 3–4 paragraphs. \
Focus on the most critical signals, compare against benchmarks, and end with 2–3 \
prioritized recommendations. Be direct, data-driven, and avoid filler phrases.
Reply in English."""


def _run_kpi_query(sql: str, label: str) -> dict:
    """Run a single KPI query and return {label, value, ok, table}."""
    try:
        from src.sql.executor import run_query
        result = run_query(sql)
        if result.succeeded and result.rows:
            first = result.rows[0]
            # rows may be dicts (DuckDB default) or tuples — handle both
            if isinstance(first, dict):
                value = next(iter(first.values()), None)
            else:
                value = first[0] if first else None
            return {"label": label, "value": value, "ok": True,
                    "table": result.to_markdown_table(max_rows=5)}
        return {"label": label, "value": None, "ok": False, "table": ""}
    except Exception as exc:
        logger.warning("KPI query failed for '%s': %s", label, exc)
        return {"label": label, "value": None, "ok": False, "table": ""}


@app.get("/api/dashboard/kpis", tags=["dashboard"])
def api_dashboard_kpis():
    """Compute real-time KPIs across all three domains for the executive dashboard.

    Synchronous so FastAPI runs it in a thread pool, keeping the async event loop free.
    DuckDB uses a shared connection so queries run sequentially.
    """

    kpi_queries = [
        # Banking
        ("banking_npl_pct",
         "SELECT ROUND(SUM(CASE WHEN credit_quality IN ('Kurang Lancar','Macet') THEN outstanding ELSE 0 END)*100.0/NULLIF(SUM(outstanding),0),2) FROM msme_credit WHERE month='2026-03'",
         "Overall NPL Rate (%)"),
        ("banking_outstanding_t",
         "SELECT ROUND(SUM(outstanding)/1e12,2) FROM msme_credit WHERE month='2026-03'",
         "Total Outstanding (Trillion IDR)"),
        ("banking_branch_achievement",
         "SELECT ROUND(SUM(credit_realization)*100.0/NULLIF(SUM(credit_target),0),1) FROM branch",
         "Branch Credit Achievement (%)"),
        ("banking_high_npl_cities",
         "SELECT COUNT(*) FROM (SELECT region FROM msme_credit WHERE month='2026-03' GROUP BY region HAVING SUM(CASE WHEN credit_quality IN ('Kurang Lancar','Macet') THEN outstanding ELSE 0 END)*100.0/NULLIF(SUM(outstanding),0)>8) t",
         "Cities with NPL > 8%"),
        ("banking_kur_avg_approval",
         "SELECT ROUND(AVG(approval_rate_pct),1) FROM loan_application WHERE month>='2026-01'",
         "Avg KUR Approval Rate (%)"),
        # Telco
        ("telco_revenue_at_risk",
         "SELECT ROUND(SUM(CASE WHEN churn_risk_score>=70 THEN arpu_monthly ELSE 0 END)/1e6,1) FROM subscriber WHERE status='Active'",
         "Revenue at Risk (Million IDR/mo)"),
        ("telco_critical_networks",
         "SELECT COUNT(*) FROM network WHERE status='Critical'",
         "Critical Network Stations"),
        ("telco_avg_latency",
         "SELECT ROUND(AVG(avg_latency_ms),1) FROM network",
         "Avg Network Latency (ms)"),
        ("telco_sla_breach_total",
         "SELECT SUM(sla_breach_count) FROM network_incident WHERE month>='2026-01'",
         "SLA Breaches (Last 3 Months)"),
        ("telco_high_churn_count",
         "SELECT COUNT(*) FROM subscriber WHERE churn_risk_score>=70 AND status='Active'",
         "Active High-Risk Churn Subscribers"),
        # Government
        ("gov_budget_absorption",
         "SELECT ROUND(SUM(realization)*100.0/NULLIF(SUM(budget_ceiling),0),1) FROM regional_budget WHERE year=2025 AND quarter='Q4'",
         "Budget Absorption Q4 2025 (%)"),
        ("gov_min_satisfaction",
         "SELECT ROUND(AVG(satisfaction_pct),1) FROM public_service WHERE month='2026-03' GROUP BY service_type ORDER BY AVG(satisfaction_pct) LIMIT 1",
         "Lowest Service Satisfaction (%)"),
        ("gov_total_pending",
         "SELECT SUM(pending_count) FROM public_service WHERE month='2026-03'",
         "Total Pending Applications"),
    ]

    # DuckDB uses a single shared connection — run queries sequentially
    results = {}
    for key, sql, label in kpi_queries:
        results[key] = _run_kpi_query(sql, label)

    return {"kpis": results, "timestamp": time.time()}


@app.post("/api/dashboard/summary", tags=["dashboard"])
async def api_dashboard_summary(body: dict):
    """Generate a streaming LLM executive summary from the KPI payload."""
    kpis = body.get("kpis", {})

    kpi_text = "\n".join(
        f"- {v['label']}: {v['value'] if v['value'] is not None else 'N/A'}"
        for v in kpis.values() if v.get("ok")
    )
    user_msg = f"Enterprise KPI snapshot:\n{kpi_text}\n\nWrite the executive briefing."

    async def _generate() -> AsyncGenerator[str, None]:
        try:
            from src.llm.inference_client import get_llm_client
            llm = get_llm_client()
            token_q: queue.Queue = queue.Queue()

            def _produce():
                try:
                    for tok in llm.stream_chat(
                        [{"role": "system", "content": _DASHBOARD_EXEC_SYSTEM},
                         {"role": "user",   "content": user_msg}],
                        temperature=0.3, max_tokens=600,
                    ):
                        token_q.put(tok)
                finally:
                    token_q.put(None)

            threading.Thread(target=_produce, daemon=True).start()
            loop = asyncio.get_event_loop()
            while True:
                item = await loop.run_in_executor(None, token_q.get)
                if item is None:
                    break
                yield _sse("token", {"text": item})
            yield _sse("done", {})
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Monitoring Agent ───────────────────────────────────────────────────────

# Default thresholds — overridable via POST /api/monitor/thresholds
_MONITOR_THRESHOLDS: dict = {
    "banking_npl_warning":      5.0,   # NPL % warning threshold
    "banking_npl_critical":    10.0,   # NPL % critical threshold
    "telco_util_warning":      75.0,   # network utilization warning
    "telco_util_critical":     90.0,   # network utilization critical
    "telco_churn_warning":     60,     # churn risk score warning
    "telco_churn_critical":    80,     # churn risk score critical
    "gov_absorption_warning":  70.0,   # Q4 budget absorption warning (<)
    "gov_absorption_critical": 50.0,   # Q4 budget absorption critical (<)
    "gov_satisfaction_warning": 84.0,  # IKM satisfaction warning (<)
}

_MONITOR_QUERIES = [
    {
        "id":     "npl_hotspots",
        "domain": "banking",
        "label":  "NPL Hotspots",
        "sql":    "SELECT region AS city, ROUND(SUM(CASE WHEN credit_quality IN ('Kurang Lancar','Macet') THEN outstanding ELSE 0 END)*100.0/NULLIF(SUM(outstanding),0),2) AS npl_pct FROM msme_credit WHERE month='2026-03' GROUP BY region HAVING npl_pct>{thr} ORDER BY npl_pct DESC LIMIT 10",
        "thr_key": "banking_npl_warning",
        "metric":  "npl_pct",
        "unit":    "% NPL",
        "critical_key": "banking_npl_critical",
    },
    {
        "id":     "critical_networks",
        "domain": "telco",
        "label":  "Critical Network Stations",
        "sql":    "SELECT city, utilization_pct, avg_latency_ms, packet_loss_pct, status FROM network WHERE utilization_pct>{thr} ORDER BY utilization_pct DESC LIMIT 10",
        "thr_key": "telco_util_warning",
        "metric":  "utilization_pct",
        "unit":    "% util",
        "critical_key": "telco_util_critical",
    },
    {
        "id":     "high_churn_cities",
        "domain": "telco",
        "label":  "High Churn Risk Concentrations",
        "sql":    "SELECT region AS city, COUNT(*) AS high_risk_count, ROUND(SUM(arpu_monthly)/1e6,2) AS revenue_at_risk_M FROM subscriber WHERE churn_risk_score>={thr} AND status='Active' GROUP BY region ORDER BY revenue_at_risk_M DESC LIMIT 10",
        "thr_key": "telco_churn_warning",
        "metric":  "high_risk_count",
        "unit":    "subscribers",
        "critical_key": "telco_churn_critical",
    },
    {
        "id":     "budget_underperformers",
        "domain": "government",
        "label":  "Budget Absorption Underperformers",
        "sql":    "SELECT work_unit, ROUND(SUM(realization)*100.0/NULLIF(SUM(budget_ceiling),0),1) AS absorption_pct FROM regional_budget WHERE year=2025 AND quarter='Q4' GROUP BY work_unit HAVING absorption_pct<{thr} ORDER BY absorption_pct LIMIT 10",
        "thr_key": "gov_absorption_warning",
        "metric":  "absorption_pct",
        "unit":    "% absorbed",
        "critical_key": "gov_absorption_critical",
    },
    {
        "id":     "low_satisfaction",
        "domain": "government",
        "label":  "Low Citizen Satisfaction",
        "sql":    "SELECT service_type, agency, ROUND(AVG(satisfaction_pct),1) AS avg_satisfaction, SUM(complaint_count) AS total_complaints FROM public_service WHERE month='2026-03' GROUP BY service_type, agency HAVING avg_satisfaction<{thr} ORDER BY avg_satisfaction LIMIT 10",
        "thr_key": "gov_satisfaction_warning",
        "metric":  "avg_satisfaction",
        "unit":    "% satisfaction",
        "critical_key": None,
    },
]


@app.get("/api/monitor/thresholds", tags=["monitor"])
async def api_monitor_get_thresholds():
    return {"thresholds": _MONITOR_THRESHOLDS}


@app.post("/api/monitor/thresholds", tags=["monitor"])
async def api_monitor_set_thresholds(body: dict):
    for k, v in body.items():
        if k in _MONITOR_THRESHOLDS:
            _MONITOR_THRESHOLDS[k] = float(v)
    return {"thresholds": _MONITOR_THRESHOLDS}


@app.post("/api/monitor/run", tags=["monitor"])
async def api_monitor_run():
    """Stream monitoring checks across all domains as SSE alert events."""
    from src.sql.executor import run_query

    _loop = asyncio.get_event_loop()

    async def _generate() -> AsyncGenerator[str, None]:
        yield _sse("monitor_start", {"checks": len(_MONITOR_QUERIES)})
        all_alerts = []

        for check in _MONITOR_QUERIES:
            thr = _MONITOR_THRESHOLDS.get(check["thr_key"], 0)
            critical_thr = _MONITOR_THRESHOLDS.get(check.get("critical_key") or "", None)
            sql = check["sql"].format(thr=thr)
            yield _sse("monitor_check_start", {"id": check["id"], "label": check["label"]})
            try:
                # run_query is synchronous — offload to thread pool
                result = await _loop.run_in_executor(None, run_query, sql)
                alerts = []
                if result.succeeded and not result.is_empty:
                    for row in result.rows[:10]:
                        # rows may be dicts or tuples
                        if isinstance(row, dict):
                            vals = list(row.values())
                            entity = str(vals[0]) if vals else ''
                            val = vals[1] if len(vals) > 1 else vals[0] if vals else None
                        else:
                            entity = str(row[0])
                            val = row[1] if len(row) > 1 else row[0]
                        try:
                            num_val = float(str(val).replace(",", ""))
                        except (ValueError, TypeError):
                            num_val = None

                        severity = "warning"
                        if critical_thr is not None and num_val is not None:
                            # For absorption/satisfaction, critical is BELOW the threshold
                            if check["id"] in ("budget_underperformers", "low_satisfaction"):
                                if num_val < critical_thr:
                                    severity = "critical"
                            else:
                                if num_val > critical_thr:
                                    severity = "critical"

                        if not isinstance(row, dict):
                            entity = str(row[0])
                        alerts.append({
                            "entity":   entity,
                            "value":    val,
                            "unit":     check["unit"],
                            "severity": severity,
                            "domain":   check["domain"],
                            "check":    check["label"],
                        })
                    all_alerts.extend(alerts)
                yield _sse("monitor_check_done", {
                    "id":     check["id"],
                    "label":  check["label"],
                    "domain": check["domain"],
                    "alert_count": len(alerts),
                    "alerts": alerts,
                    "table_markdown": result.to_markdown_table(max_rows=10) if result.succeeded else "",
                })
            except Exception as exc:
                logger.error("Monitor check '%s' failed: %s", check["id"], exc)
                yield _sse("monitor_check_done", {
                    "id": check["id"], "label": check["label"],
                    "domain": check["domain"], "alert_count": 0, "alerts": [], "table_markdown": "",
                })

        yield _sse("monitor_done", {
            "total_alerts":    len(all_alerts),
            "critical_count":  sum(1 for a in all_alerts if a["severity"] == "critical"),
            "warning_count":   sum(1 for a in all_alerts if a["severity"] == "warning"),
        })

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Dashboard page route ───────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse, tags=["pages"])
async def dashboard_page():
    """Executive AI Dashboard — real-time KPIs + LLM briefing."""
    p = _STATIC / "dashboard.html"
    if p.exists():
        return HTMLResponse(p.read_text(encoding="utf-8"))
    raise HTTPException(404, "dashboard.html not found")


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

    # PDF table extraction — run synchronously (fast for typical report PDFs)
    extracted_tables: list[str] = []
    if ext == ".pdf":
        try:
            from src.retrieval.table_extractor import extract_tables_from_pdf, register_tables_as_views
            tables = extract_tables_from_pdf(dest)
            if tables:
                parquet_dir = Path(settings.parquet_dir) if hasattr(settings, "parquet_dir") else Path("data/parquet")
                extracted_tables = register_tables_as_views(tables, stem, parquet_dir)
                logger.info("Extracted %d table(s) from PDF: %s", len(extracted_tables), filename)
        except Exception as exc:
            logger.warning("PDF table extraction skipped: %s", exc)

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
        "extracted_tables": extracted_tables,
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
                  style=body.style, thinking=body.thinking,
                  image_b64=body.image_b64),
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
    thinking: bool = False,
    image_b64: str | None = None,
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

        # Vision: if an image was attached, rewrite prep.history so the last
        # user turn becomes a multimodal content list (OpenAI vision format).
        if image_b64:
            try:
                mime = "image/jpeg"
                if image_b64.startswith("data:"):
                    mime, _, image_b64 = image_b64.partition(";base64,")
                    mime = mime.removeprefix("data:")
                vision_content = [
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{image_b64}", "detail": "high"}},
                    {"type": "text", "text": question},
                ]
                # Patch the last user message in the synthesis prompt at stream time
                prep._vision_content = vision_content   # type: ignore[attr-defined]
            except Exception:
                pass  # fall back to text-only if image handling fails

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
            visible, think_chunk = think_filter.feed(tok)
            # Notify frontend when model enters or exits a thinking block
            if think_filter.thinking and not was_thinking:
                yield _sse("thinking", {"active": True})
            elif not think_filter.thinking and was_thinking:
                yield _sse("thinking", {"active": False})
            was_thinking = think_filter.thinking
            if visible:
                yield _sse("token", {"text": visible})
            # Stream thinking content when reasoning mode is on
            if think_chunk and thinking:
                yield _sse("thinking_token", {"text": think_chunk})

        # Flush any text held in the lookahead buffer
        tail_vis, tail_thk = think_filter.flush()
        if tail_vis:
            yield _sse("token", {"text": tail_vis})
        if tail_thk and thinking:
            yield _sse("thinking_token", {"text": tail_thk})

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

    def feed(self, tok: str) -> tuple[str, str]:
        """Return (visible_text, thinking_text).

        visible_text  — answer content (non-empty when NOT inside <think> block).
        thinking_text — chain-of-thought content (non-empty when INSIDE <think> block).
        """
        self._buf += tok
        out_vis = ""
        out_thk = ""
        while self._buf:
            if self._depth > 0:
                close_idx = self._buf.find(self._CLOSE)
                open_idx  = self._buf.find(self._OPEN)
                if close_idx >= 0 and (open_idx < 0 or close_idx <= open_idx):
                    out_thk += self._buf[:close_idx]
                    self._depth -= 1
                    after = self._buf[close_idx + len(self._CLOSE):]
                    self._buf = after.lstrip("\n") if self._depth == 0 else after
                elif open_idx >= 0:
                    out_thk += self._buf[:open_idx]
                    self._depth += 1
                    self._buf = self._buf[open_idx + len(self._OPEN):]
                else:
                    hold = max(
                        self._tail_overlap(self._buf, self._CLOSE),
                        self._tail_overlap(self._buf, self._OPEN),
                    )
                    if hold:
                        out_thk += self._buf[:-hold]
                        self._buf = self._buf[-hold:]
                    else:
                        out_thk += self._buf
                        self._buf = ""
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
                        out_vis += self._buf[:-hold]
                        self._buf = self._buf[-hold:]
                    else:
                        out_vis += self._buf
                        self._buf = ""
                    break
        return out_vis, out_thk

    def flush(self) -> tuple[str, str]:
        """Release buffered text. Returns (visible_text, thinking_text)."""
        if self._depth == 0:
            result, self._buf = self._buf, ""
            return result, ""
        self._buf = ""
        return "", ""
