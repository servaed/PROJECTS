# Cloudera AI RAG Demo — self-contained Docker image
#
# Bundles MinIO (object storage), Nessie (Iceberg REST catalog), Trino
# (query engine), and the FastAPI + React SPA into a single container.
#
# Identical experience whether run locally or deployed to Cloudera AI Workbench
# as a CML Application.
#
# Build:
#   docker build -t cloudera-rag-demo:latest .
#
# Run locally:
#   docker run --rm -p 8080:8080 \
#     -e LLM_PROVIDER=openai \
#     -e LLM_BASE_URL=https://api.openai.com/v1 \
#     -e LLM_API_KEY=sk-... \
#     -e LLM_MODEL_ID=gpt-4o \
#     cloudera-rag-demo:latest
#
# For persistent data between restarts (vector store + MinIO tables):
#   docker run --rm -p 8080:8080 -v $(pwd)/data:/app/data -v rag-minio:/data/minio \
#     -e LLM_PROVIDER=... cloudera-rag-demo:latest
#
# CML Application: deploy from this Docker image, port 8080, 4 vCPU / 8 GB RAM.
# The container listens on PORT env var (defaults to 8080).

# ── Stage 1: Download infrastructure binaries ─────────────────────────────────
FROM debian:bookworm-slim AS infra

ARG TRINO_VERSION=455
ARG NESSIE_VERSION=0.83.2

RUN apt-get update && apt-get install -y --no-install-recommends \
        wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# MinIO server binary
RUN wget -q "https://dl.min.io/server/minio/release/linux-amd64/minio" \
        -O /usr/local/bin/minio \
    && chmod +x /usr/local/bin/minio

# Nessie — Iceberg REST catalog (single executable JAR)
RUN wget -q \
    "https://github.com/projectnessie/nessie/releases/download/nessie-${NESSIE_VERSION}/nessie-quarkus-${NESSIE_VERSION}-runner.jar" \
    -O /opt/nessie.jar

# Trino server tarball
RUN wget -q \
    "https://repo1.maven.org/maven2/io/trino/trino-server/${TRINO_VERSION}/trino-server-${TRINO_VERSION}.tar.gz" \
    -O /tmp/trino.tar.gz \
    && tar -xzf /tmp/trino.tar.gz -C /opt \
    && mv /opt/trino-server-${TRINO_VERSION} /opt/trino \
    && rm /tmp/trino.tar.gz

# ── Stage 2: Final image ──────────────────────────────────────────────────────
FROM python:3.11-slim

# System deps:
#   openjdk-21-jre-headless  — required by Trino + Nessie (openjdk-17 removed from bookworm)
#   curl                     — health-check loops in entrypoint.sh
#   build-essential libgomp1 — required by faiss-cpu + sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-21-jre-headless \
        curl \
        build-essential \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── Copy infrastructure binaries from stage 1 ────────────────────────────────
COPY --from=infra /usr/local/bin/minio   /usr/local/bin/minio
COPY --from=infra /opt/nessie.jar        /opt/nessie/nessie.jar
COPY --from=infra /opt/trino             /opt/trino

# ── Python environment ────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
COPY . .

# ── Trino configuration ───────────────────────────────────────────────────────
COPY deployment/trino/etc /opt/trino/etc
RUN mkdir -p /opt/trino/var/log /opt/trino/var/run

# ── Data directories ──────────────────────────────────────────────────────────
RUN mkdir -p data/vector_store /data/minio

# ── Environment ───────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    # Use Trino + MinIO by default in the container image
    QUERY_ENGINE=trino \
    DOCS_STORAGE_TYPE=s3 \
    # Java home for Trino / Nessie (Debian bookworm path)
    JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

EXPOSE 8080

# ── Unprivileged user (matches CML Applications runtime) ─────────────────────
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app \
    && chown -R appuser:appuser /opt/trino \
    && chown -R appuser:appuser /opt/nessie \
    && chown -R appuser:appuser /data \
    && chmod +x /usr/local/bin/minio \
    && chmod +x /app/deployment/entrypoint.sh

USER appuser

# ── Entrypoint ────────────────────────────────────────────────────────────────
# entrypoint.sh starts MinIO → Nessie → Trino → seeds data → builds vector
# store (first run) → launches uvicorn on port 8080.
CMD ["bash", "deployment/entrypoint.sh"]
