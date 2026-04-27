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
	@echo "    make seed             Seed Parquet files + ingest documents into FAISS"
	@echo "    make reset-vs         Delete vector store (forces re-ingestion on next start)"
	@echo "    make demo-reset       Full demo factory-reset: clear VS, reseed, reingest"
	@echo "    make reingest         Rebuild FAISS vector store without reseeding data"
	@echo ""
	@echo "  Testing"
	@echo "    make test             Run full pytest suite"
	@echo "    make test-fast        Run tests, stop on first failure"
	@echo "    make eval             Run full 36+multi-turn evaluation (needs running server)"
	@echo ""

# ── Development ────────────────────────────────────────────────────────────────
dev:
	@echo "Starting dev server on port $(PORT)…"
	uvicorn app.api:app --host 0.0.0.0 --port $(PORT) --reload

seed:
	@echo "[1/2] Seeding Parquet files for DuckDB…"
	python data/sample_tables/seed_parquet.py
	@echo "[2/2] Ingesting documents into FAISS vector store…"
	python -m src.retrieval.document_loader
	@echo "Done. Run 'make dev' to start the server."

reset-vs:
	@echo "Deleting vector store (will be rebuilt on next start)…"
	rm -rf data/vector_store/
	@echo "Vector store removed."

reingest:
	@echo "Rebuilding FAISS vector store from existing documents…"
	python -m src.retrieval.document_loader
	@echo "Done. Vector store rebuilt."

demo-reset:
	@echo "=== Full demo factory reset ==="
	@echo "[1/3] Clearing vector store…"
	rm -rf data/vector_store/
	@echo "[2/3] Re-seeding Parquet data tables…"
	python data/sample_tables/seed_parquet.py
	@echo "[3/3] Re-ingesting documents into FAISS…"
	python -m src.retrieval.document_loader
	@echo "=== Demo reset complete. Run 'make dev' to start the server. ==="

# ── Testing ────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v

test-fast:
	pytest tests/ -v -x

eval:
	@echo "Running full evaluation (requires server on port 8080)…"
	python eval_all.py

# ── Cleanup ────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f .deps_installed
