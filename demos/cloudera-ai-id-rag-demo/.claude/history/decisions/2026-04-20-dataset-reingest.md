# Decision: Dataset Expansion + Re-ingest Architecture
**Date:** 2026-04-20

## Decision 1: Shared data generator module

**Choice:** Create `data/sample_tables/sample_data.py` as a single source of truth imported by both `seed_database.py` and `seed_iceberg.py`, rather than duplicating data in each file.

**Alternatives considered:**
- Copy-paste the same row data into both files (previous approach — was already out of sync)
- Generate data at runtime inside each seed script independently

**Why:** The two seed scripts had already drifted (SQLite had 45 umkm rows, Iceberg also 45 but with slightly different nasabah IDs). Any future expansion would require touching two files. A shared module with a fixed `random.Random(42)` seed guarantees identical output and single-point maintenance.

**Trade-off:** seed_iceberg.py needs a `sys.path.insert` hack to import from the project root since it lives in `deployment/`. Acceptable because it's a startup script, not library code.

## Decision 2: Row count strategy (1485 rows across 9 tables)

**Choice:** Generate time-series data algorithmically (15 cities × 3 segments × 12 months for kredit_umkm) rather than hand-crafting individual rows.

**Why:** Hand-crafted data at this scale would be unreadable and impossible to maintain. Time-series and cross-product generation reflects how real enterprise data looks (monthly snapshots per entity) and makes the SQL queries more interesting for demos (trends over time, aggregations by city/segment/quarter).

**Distribution rationale:**
- `kredit_umkm` 540: 12 months of history enables trend queries ("bulan mana NPL tertinggi?")
- `penggunaan_data` 480: 6 months × 80 customers enables per-customer usage analysis
- `anggaran_daerah` 88: 2 years × 4 quarters × 11 programs enables year-over-year budget comparison
- `layanan_publik` 132: 12 months × 11 service types enables seasonal service volume patterns

## Decision 3: Re-ingest as background thread, not async task

**Choice:** `threading.Thread(daemon=True)` rather than `asyncio.create_task()` or `BackgroundTasks`.

**Why:** The ingest pipeline (`load_documents → chunk_documents → build_vector_store`) is CPU-bound and includes blocking I/O (file reads, FAISS index build, HuggingFace model inference). Running it in a thread pool via `asyncio.run_in_executor` or directly as a `threading.Thread` is correct; `asyncio.create_task` would block the event loop.

**Alternative rejected:** FastAPI `BackgroundTasks` — same mechanism under the hood but less control over the thread lifecycle and harder to check status from a separate endpoint.

## Decision 4: 409 on concurrent ingest (not queue)

**Choice:** Return HTTP 409 Conflict if an ingest job is already running. Don't queue requests.

**Why:** Ingestion is expensive (embeddings model, FAISS rebuild) and idempotent — a second request right after the first is almost certainly an accidental double-click, not a meaningful second ingest. A queue adds complexity with no practical benefit for a single-operator demo tool.

**Trade-off:** If two operators simultaneously click Re-ingest, the second one gets a 409 error. The button handles this gracefully (shows "⟳ Already running" and starts polling the status).

## Decision 5: Source documents are never deleted

**Choice:** `build_vector_store()` only writes `index.faiss`, `index.pkl`, and `index.sha256`. Documents in MinIO or local filesystem are untouched.

**Why:** This is the entire safety contract of the Re-ingest feature. Users need to be able to add documents, click Re-ingest, and know their documents weren't removed. The ingest pipeline is purely read-from-source → write-to-index.

**Documentation:** Explicitly documented in DEPLOYMENT.md Section 8: "Source files are never deleted — only the FAISS index is rebuilt."

## Decision 6: `SQL_APPROVED_TABLES` required for new structured tables

**Choice:** New database tables added by users are NOT automatically exposed to the SQL assistant — they must be added to `SQL_APPROVED_TABLES`.

**Why:** Security guardrail. The SQL assistant must only query tables explicitly approved by the operator. Auto-discovery would silently expose internal or sensitive tables. Documented in Section 8 of DEPLOYMENT.md.
