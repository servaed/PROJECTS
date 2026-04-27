"""CML Job: Nightly document re-ingestion.

Scheduled via CML Jobs (or cron) to keep the FAISS vector store fresh as
new documents are added to the knowledge base.

Usage (local):
    python data/cml_jobs/nightly_reingest.py

Usage (CML Job):
    Script: data/cml_jobs/nightly_reingest.py
    Schedule: 0 2 * * *  (02:00 daily)
    Resource profile: 4 vCPU / 8 GiB RAM (required for multilingual-e5-large)
"""

import sys
import os
import time
import logging

# Ensure project root is on path so src.* imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Load data/.env.local overrides before importing settings
from src.config.settings import _load_override_env
_load_override_env()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("nightly_reingest")

t0 = time.time()
logger.info("=== Nightly Re-ingestion Job starting ===")

try:
    from src.retrieval.document_loader import load_documents
    from src.retrieval.chunking import chunk_documents
    from src.retrieval.embeddings import get_embeddings
    from src.retrieval.vector_store import build_vector_store
    from src.retrieval.retriever import invalidate_bm25_cache

    logger.info("Step 1/4: Loading documents...")
    docs = load_documents()
    logger.info("  Loaded %d documents", len(docs))

    logger.info("Step 2/4: Chunking...")
    chunks = chunk_documents(docs)
    logger.info("  Created %d chunks", len(chunks))

    logger.info("Step 3/4: Loading embeddings model...")
    embeddings = get_embeddings()

    logger.info("Step 4/4: Building vector store...")
    build_vector_store(chunks, embeddings)
    invalidate_bm25_cache()

    elapsed = round(time.time() - t0)
    logger.info("=== Re-ingestion complete: %d docs, %d chunks in %ds ===", len(docs), len(chunks), elapsed)

    # Log to MLflow if configured
    try:
        from src.utils.metrics import log_inference
        from src.config.settings import settings
        if settings.mlflow_tracking_uri:
            import mlflow
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            mlflow.set_experiment(settings.mlflow_experiment_name)
            with mlflow.start_run(run_name="nightly_reingest"):
                mlflow.log_metrics({
                    "docs_loaded": len(docs),
                    "chunks_indexed": len(chunks),
                    "elapsed_seconds": elapsed,
                })
            logger.info("Logged to MLflow experiment: %s", settings.mlflow_experiment_name)
    except Exception as mlflow_exc:
        logger.debug("MLflow logging skipped: %s", mlflow_exc)

    sys.exit(0)

except Exception as exc:
    logger.exception("Re-ingestion failed: %s", exc)
    sys.exit(1)
