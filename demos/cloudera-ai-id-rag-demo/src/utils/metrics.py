"""MLflow experiment tracking — logs every chat inference as an MLflow run.

Enabled when MLFLOW_TRACKING_URI is set (e.g. "mlruns" for local file-store
or an MLflow server URL for a CML-hosted tracking server).

All calls are fire-and-forget (background thread) so that a slow/unavailable
MLflow server never blocks the SSE streaming response.

Usage:
    from src.utils.metrics import log_inference
    log_inference(domain="banking", language="id", mode="document",
                  provider="anthropic", model="claude-3-5-sonnet",
                  latency_ms=1234, input_tokens=800, output_tokens=200)
"""

from __future__ import annotations

import threading
import time
from typing import Any

from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)

# In-memory ring buffer — always available regardless of MLflow
_RING_SIZE = 500
_ring: list[dict] = []
_ring_lock = threading.Lock()
_run_counter = 0
_total_latency_ms = 0.0
_total_input_tokens = 0
_total_output_tokens = 0


def _to_ring(record: dict) -> None:
    global _ring
    with _ring_lock:
        _ring.append(record)
        if len(_ring) > _RING_SIZE:
            _ring = _ring[-_RING_SIZE:]


def _mlflow_log(record: dict) -> None:
    """Log one inference record to MLflow (runs in background thread)."""
    try:
        import mlflow
        uri = settings.mlflow_tracking_uri
        if not uri:
            return
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(settings.mlflow_experiment_name)
        with mlflow.start_run(run_name=record.get("run_name", "chat")):
            mlflow.log_params({
                "domain":   record.get("domain", ""),
                "language": record.get("language", ""),
                "mode":     record.get("mode", ""),
                "provider": record.get("provider", ""),
                "model":    record.get("model", ""),
            })
            mlflow.log_metrics({
                "latency_ms":     record.get("latency_ms", 0),
                "input_tokens":   record.get("input_tokens", 0),
                "output_tokens":  record.get("output_tokens", 0),
                "total_tokens":   record.get("total_tokens", 0),
                "doc_citations":  record.get("doc_citations", 0),
                "has_sql":        float(record.get("has_sql", False)),
            })
    except ImportError:
        pass  # mlflow not installed — silently skip
    except Exception as exc:
        logger.debug("MLflow log failed (non-critical): %s", exc)


def log_inference(
    *,
    domain: str,
    language: str,
    mode: str,
    provider: str,
    model: str,
    latency_ms: float,
    input_tokens: int,
    output_tokens: int,
    doc_citations: int = 0,
    has_sql: bool = False,
) -> None:
    """Record one inference event.  Always updates the in-memory ring buffer.
    Logs to MLflow asynchronously if MLFLOW_TRACKING_URI is configured."""
    global _run_counter, _total_latency_ms, _total_input_tokens, _total_output_tokens

    record: dict[str, Any] = {
        "ts":            time.time(),
        "run_name":      f"{domain}/{language}/{mode}",
        "domain":        domain,
        "language":      language,
        "mode":          mode,
        "provider":      provider,
        "model":         model,
        "latency_ms":    round(latency_ms),
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "total_tokens":  input_tokens + output_tokens,
        "doc_citations": doc_citations,
        "has_sql":       has_sql,
    }
    _to_ring(record)

    with _ring_lock:
        _run_counter += 1
        _total_latency_ms += latency_ms
        _total_input_tokens += input_tokens
        _total_output_tokens += output_tokens

    if settings.mlflow_tracking_uri:
        threading.Thread(target=_mlflow_log, args=(record,), daemon=True).start()


def get_recent_runs(limit: int = 100) -> list[dict]:
    """Return the most recent inference records, newest first."""
    with _ring_lock:
        return list(reversed(_ring[-limit:]))


def get_summary() -> dict:
    """Return aggregate stats for the current session."""
    with _ring_lock:
        n = _run_counter
        avg_lat = round(_total_latency_ms / n) if n else 0
        return {
            "total_runs":         n,
            "avg_latency_ms":     avg_lat,
            "total_input_tokens": _total_input_tokens,
            "total_output_tokens": _total_output_tokens,
            "total_tokens":       _total_input_tokens + _total_output_tokens,
            "mlflow_enabled":     bool(settings.mlflow_tracking_uri),
            "mlflow_uri":         settings.mlflow_tracking_uri or None,
            "experiment":         settings.mlflow_experiment_name,
        }
