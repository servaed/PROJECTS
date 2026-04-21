# Makefile — cloudera-ai-id-rag-demo
# Common development and testing commands.

.PHONY: help dev seed test test-fast reset-vs clean

PORT ?= 8080

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
	@echo "    make test             Run full pytest suite"
	@echo "    make test-fast        Run tests, stop on first failure"
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

# ── Cleanup ────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f .deps_installed
