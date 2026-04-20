#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# entrypoint.sh — single-container startup for the Cloudera RAG Demo
#
# Starts MinIO, Nessie, Trino in background, waits for each to be healthy,
# seeds Iceberg tables + uploads documents, builds the vector store if needed,
# then launches uvicorn (foreground — keeps the container alive).
#
# Port assignments (all on localhost inside the container):
#   8080  FastAPI + React SPA   (exposed to CML / Docker host)
#   8085  Trino coordinator     (internal)
#   9000  MinIO S3 gateway      (internal)
#   9001  MinIO console         (internal, optional)
#   19120 Nessie REST catalog   (internal)
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

PORT="${APP_PORT:-8080}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
VECTOR_STORE_PATH="${VECTOR_STORE_PATH:-./data/vector_store}"

# ── Load override env file (written by /configure wizard) ────────────────────
OVERRIDE_FILE="data/.env.local"
if [ -f "$OVERRIDE_FILE" ]; then
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        key="${key// /}"
        if [ -z "${!key+x}" ]; then export "$key=$value"; fi
    done < <(grep -v '^\s*#' "$OVERRIDE_FILE" | grep '=')
fi

echo "========================================================"
echo " Cloudera AI RAG Demo — Startup"
echo " Python : $(python --version 2>&1)"
echo " Java   : $(java -version 2>&1 | head -1)"
echo " Port   : $PORT"
echo "========================================================"

# ── Helper: wait for an HTTP endpoint to return 200 ──────────────────────────
# Usage: wait_for_http <name> <url> [<max_retries>] [<logfile>]
wait_for_http() {
    local name="$1" url="$2" max="${3:-90}" logfile="${4:-/dev/null}" attempt=0
    echo "[startup] Waiting for $name at $url ..."
    until curl -sf "$url" > /dev/null 2>&1; do
        attempt=$((attempt + 1))
        if [ "$attempt" -ge "$max" ]; then
            echo "[startup] ERROR: $name did not start within $((max * 3))s"
            echo "[startup] Last 15 log lines from $name:"
            tail -15 "$logfile" 2>/dev/null || echo "  (log not available at $logfile)"
            exit 1
        fi
        sleep 3
    done
    echo "[startup] $name is ready."
}

# ── Allow external service hostnames for multi-container deployments ──────────
MINIO_HOST="${MINIO_HOST:-localhost}"
MINIO_PORT="${MINIO_PORT:-9000}"
NESSIE_HOST="${NESSIE_HOST:-localhost}"
NESSIE_PORT="${NESSIE_PORT:-19120}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"

# Template Trino catalog config if non-default hostnames are requested
if [ "$NESSIE_HOST" != "localhost" ] || [ "$MINIO_HOST" != "localhost" ]; then
    echo "[startup] Templating Trino catalog config for NESSIE_HOST=$NESSIE_HOST MINIO_HOST=$MINIO_HOST"
    sed -i "s|http://localhost:${NESSIE_PORT}|http://${NESSIE_HOST}:${NESSIE_PORT}|g" \
        /opt/trino/etc/catalog/iceberg.properties
    sed -i "s|http://localhost:${MINIO_PORT}|http://${MINIO_HOST}:${MINIO_PORT}|g" \
        /opt/trino/etc/catalog/iceberg.properties
    sed -i "s|s3.aws-access-key=minioadmin|s3.aws-access-key=${MINIO_ROOT_USER}|g" \
        /opt/trino/etc/catalog/iceberg.properties
    sed -i "s|s3.aws-secret-key=minioadmin|s3.aws-secret-key=${MINIO_ROOT_PASSWORD}|g" \
        /opt/trino/etc/catalog/iceberg.properties
fi

# ── 1. Start MinIO ────────────────────────────────────────────────────────────
echo "[1/5] Starting MinIO..."
mkdir -p /data/minio
MINIO_ROOT_USER="${MINIO_ROOT_USER}" \
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD}" \
minio server /data/minio \
    --address :9000 \
    --console-address :9001 \
    > /tmp/minio.log 2>&1 &

wait_for_http "MinIO" "http://localhost:9000/minio/health/live" 90 /tmp/minio.log

# ── 2. Start Nessie ───────────────────────────────────────────────────────────
echo "[2/5] Starting Nessie (Iceberg REST catalog)..."
java \
    -Dquarkus.http.port=19120 \
    -Dnessie.version.store.type=IN_MEMORY \
    -Dquarkus.log.level=WARN \
    -jar /opt/nessie/nessie.jar \
    > /tmp/nessie.log 2>&1 &

wait_for_http "Nessie" "http://localhost:19120/api/v1/config" 60 /tmp/nessie.log

# ── 3. Start Trino ────────────────────────────────────────────────────────────
echo "[3/5] Starting Trino (query engine)..."
mkdir -p /opt/trino/var/log /opt/trino/var/run
/opt/trino/bin/launcher run \
    > /tmp/trino.log 2>&1 &

# Trino JVM takes longer to start — allow up to 5 minutes
wait_for_http "Trino" "http://localhost:8085/v1/info" 100 /tmp/trino.log

# ── 4. Seed data ──────────────────────────────────────────────────────────────
echo "[4/5] Seeding Iceberg tables and uploading documents..."
python deployment/seed_iceberg.py
echo "[4/5] Seed complete."

# ── 5. Build vector store (skip if already present) ──────────────────────────
FAISS_INDEX="${VECTOR_STORE_PATH}/index.faiss"
if [ ! -f "$FAISS_INDEX" ]; then
    echo "[5/5] Building FAISS vector store from documents in MinIO..."
    echo "      (First run downloads the embedding model ~500 MB — please wait)"
    python -m src.retrieval.document_loader
    echo "[5/5] Vector store ready."
else
    echo "[5/5] Vector store found — skipping ingestion."
fi

# ── Start FastAPI (foreground — keeps container alive) ────────────────────────
echo "========================================================"
echo " All services ready. Starting FastAPI on port $PORT..."
echo "========================================================"

exec uvicorn app.api:app \
    --host "0.0.0.0" \
    --port "$PORT" \
    --log-level "$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')"
