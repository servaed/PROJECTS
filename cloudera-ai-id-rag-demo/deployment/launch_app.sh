#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────
# launch_app.sh — Cloudera AI Application startup script
#
# Usage in Cloudera AI Applications:
#   Set "Launch Command" to:  bash deployment/launch_app.sh
#
# Requirements:
#   - CLOUDERA_INFERENCE_URL, CLOUDERA_INFERENCE_API_KEY set in app env vars
#   - Python 3.10+ available
#   - App must listen on PORT (default: 8080)
# ──────────────────────────────────────────────────────────────────────────

set -euo pipefail

PORT="${APP_PORT:-8080}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

echo "=== Cloudera AI Application Startup ==="
echo "Port: $PORT"
echo "Log level: $LOG_LEVEL"
echo "Python: $(python --version)"
echo "Working directory: $(pwd)"

# Install dependencies if not already installed
if [ ! -f ".deps_installed" ]; then
    echo "Installing Python dependencies..."
    pip install --quiet -r requirements.txt
    touch .deps_installed
    echo "Dependencies installed."
fi

# Ingest documents if vector store does not exist
VECTOR_STORE_PATH="${VECTOR_STORE_PATH:-./data/vector_store}"
if [ ! -f "${VECTOR_STORE_PATH}/index.faiss" ]; then
    echo "Vector store not found — running document ingestion..."
    python -m src.retrieval.document_loader
    echo "Ingestion complete."
else
    echo "Vector store found at ${VECTOR_STORE_PATH} — skipping ingestion."
fi

# Launch Streamlit
echo "Starting Streamlit on port $PORT..."
exec streamlit run app/main.py \
    --server.port "$PORT" \
    --server.address "0.0.0.0" \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --logger.level "$LOG_LEVEL"
