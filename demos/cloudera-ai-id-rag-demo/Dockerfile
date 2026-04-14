# Cloudera AI Enterprise Assistant — Docker image
#
# Supports both deployment paths in Cloudera AI Applications:
#   1. Git-based (no Docker needed — platform builds from source)
#   2. Docker image — build this image, push to a registry, then point
#      the Cloudera AI Application at the registry URL.
#
# Build:
#   docker build -t cloudera-ai-id-rag-demo:latest .
#
# Run locally (mirrors Cloudera AI Applications runtime):
#   docker run --rm -p 8080:8080 \
#     -e LLM_PROVIDER=openai \
#     -e LLM_BASE_URL=https://... \
#     -e LLM_API_KEY=sk-... \
#     -e LLM_MODEL_ID=meta/llama-3.1-70b-instruct \
#     -v $(pwd)/data:/app/data \
#     cloudera-ai-id-rag-demo:latest
#
# Required env vars at runtime — see .env.example for the full list.
# The container must listen on PORT 8080 (Cloudera AI Applications requirement).

FROM python:3.11-slim

# ── System deps ───────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps (separate layer for cache efficiency) ─────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ───────────────────────────────────────────────────────
COPY . .

# Pre-create data directories so volume mounts work without root
RUN mkdir -p data/docs data/vector_store data/db

# ── Runtime config ─────────────────────────────────────────────────────────
# All sensitive values (API keys, DB URLs) must be injected via env vars at
# runtime — never bake secrets into the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

EXPOSE 8080

# Unprivileged user — matches Cloudera AI Applications runtime expectations
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# ── Entrypoint ─────────────────────────────────────────────────────────────
# launch_app.sh handles optional ingestion + DB seeding before starting uvicorn.
# Pass --no-seed / --no-ingest flags to skip steps when data is pre-mounted.
CMD ["bash", "deployment/launch_app.sh"]
