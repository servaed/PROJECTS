# Makefile — cloudera-ai-id-rag-demo
# Common development, testing, and deployment commands.
# Usage: make <target>

.PHONY: help dev seed test docker docker-push clean reset-vector-store

REGISTRY   ?= ghcr.io/your-org
IMAGE      ?= cloudera-rag-demo
TAG        ?= latest
PORT       ?= 8080

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  cloudera-ai-id-rag-demo — available targets"
	@echo ""
	@echo "  Development"
	@echo "    make dev              Start local dev server on port 8080 (hot-reload)"
	@echo "    make seed             Seed SQLite database + ingest documents into FAISS"
	@echo "    make reset-vs         Delete vector store (forces re-ingestion on next start)"
	@echo ""
	@echo "  Testing"
	@echo "    make test             Run full pytest suite (66 tests)"
	@echo "    make test-fast        Run tests, stop on first failure"
	@echo ""
	@echo "  Docker"
	@echo "    make docker           Build Docker image ($(REGISTRY)/$(IMAGE):$(TAG))"
	@echo "    make docker-run       Build + run locally on port $(PORT)"
	@echo "    make docker-push      Push image to registry"
	@echo ""
	@echo "  Variables (override with make VAR=value)"
	@echo "    REGISTRY  default: $(REGISTRY)"
	@echo "    IMAGE     default: $(IMAGE)"
	@echo "    TAG       default: $(TAG)"
	@echo "    PORT      default: $(PORT)"
	@echo ""

# ── Development ────────────────────────────────────────────────────────────────
dev:
	@echo "Starting dev server on port $(PORT)…"
	uvicorn app.api:app --host 0.0.0.0 --port $(PORT) --reload

seed:
	@echo "[1/2] Seeding demo SQLite database…"
	python data/sample_tables/seed_database.py
	@echo "[2/2] Ingesting documents into FAISS vector store…"
	python -m src.retrieval.document_loader
	@echo "Done. Run 'make dev' to start the server."

reset-vs:
	@echo "Deleting vector store (will be rebuilt on next start)…"
	rm -rf data/vector_store/
	@echo "Vector store removed."

# ── Testing ────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v

test-fast:
	pytest tests/ -v -x

# ── Docker ─────────────────────────────────────────────────────────────────────
docker:
	docker build -t $(REGISTRY)/$(IMAGE):$(TAG) .

docker-run: docker
	docker run --rm -p $(PORT):8080 \
	  --env-file .env \
	  -v "$$(pwd)/data/vector_store:/app/data/vector_store" \
	  -v "rag-minio:/data/minio" \
	  $(REGISTRY)/$(IMAGE):$(TAG)

docker-push: docker
	docker push $(REGISTRY)/$(IMAGE):$(TAG)

# ── Cleanup ────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f .deps_installed
