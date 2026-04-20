# Session: Dataset Expansion + Re-ingest Button
**Date:** 2026-04-20  
**Topics:** Expand structured datasets to 1485 rows; add Re-ingest button to /setup; document how to add files

## User requests

1. "Add more rows to structured datasets, more than 1000 rows if possible"
2. "Add button to re-ingest all structured and unstructured data to vector store"
3. "Make sure this button don't delete data after ingestion"
4. "Add documentation how to add more documents to vector store"
5. "Update all project state and MD files"

## What was done

### 1. Shared data generator: `data/sample_tables/sample_data.py` (NEW)
- Single source of truth imported by both SQLite and Iceberg seeders
- `random.Random(42)` — fixed seed, deterministic; same rows every run
- `generate_all()` returns `dict[table_name → list[tuple]]`
- 1485 total rows: kredit_umkm (540), nasabah (80), cabang (25), pelanggan (80),
  penggunaan_data (480), jaringan (20), penduduk (40), anggaran_daerah (88), layanan_publik (132)

### 2. SQLite seed rewrite: `data/sample_tables/seed_database.py`
- Dropped all inline data; now imports `generate_all` and executes `executemany`
- File shrank from ~430 lines to ~85 lines
- `kredit_umkm` uses `AUTOINCREMENT` — no explicit id in executemany rows

### 3. Iceberg seed update: `deployment/seed_iceberg.py`
- Adds `sys.path.insert(0, str(Path(__file__).parent.parent))` at top
- Imports `generate_all as _generate_all` with a lazy `_get_data()` cache
- `_seed_banking/_seed_telco/_seed_government` each replaced with 3 `_exec(INSERT...)` calls
- `kredit_umkm` Iceberg table has explicit `id BIGINT` column — prepended via enumerate:
  `[(i+1,) + row for i, row in enumerate(data["kredit_umkm"])]`
- Removed ~350 lines of hardcoded row tuples

### 4. Ingest API: `app/api.py`
- `_ingest_state: dict` + `_ingest_lock: threading.Lock()` at module level
- `IngestRequest(BaseModel)` with `reseed_db: bool = False`
- `POST /api/ingest`: returns 409 if running; starts `threading.Thread(daemon=True, name="ingest-worker")`
  that runs `load_documents → chunk_documents → get_embeddings → build_vector_store`
  - Source docs (MinIO/local) are NOT deleted — only `index.faiss` + `index.pkl` + `index.sha256` overwritten
  - Optional: re-seeds SQLite via `importlib.util.spec_from_file_location` when `reseed_db=True`
- `GET /api/ingest/status`: returns running state, elapsed_s, last_result `{ok, docs, chunks}` or `{ok:false, error}`

### 5. Re-ingest button: `app/static/setup.html`
- Added `<button class="refresh-btn" id="ingestBtn" onclick="triggerIngest()">⟳ Re-ingest</button>` to topbar
- `triggerIngest()`: disables button, POSTs, handles 409, calls `_startIngestPoll()`
- `_startIngestPoll()`: 2s interval, updates button text with `⟳ Ns…`, stops on completion
- Shows `✓ N chunks` on success (3s), `✗ Failed` on error (4s), then resets and calls `load()`
- On page load: prefetch `/api/ingest/status` → resumes poll if job was running before page opened

### 6. Documentation: `DEPLOYMENT.md` new Section 8
- File types, directory structure, MinIO upload examples (mc + boto3)
- Four re-ingest options: button, CLI, API, hash-delete restart
- What the button does (no deletion guarantee documented explicitly)
- Structured data section: SQLite re-seed, Iceberg INSERT, SQL_APPROVED_TABLES
- Sections 8–11 renumbered to 9–12; Table of Contents updated

## Key design decisions

- **Shared generator not inline data**: avoids the dual-maintenance problem where SQLite and Iceberg drifted out of sync; fixed seed ensures reproducibility
- **No source deletion**: `build_vector_store()` overwrites FAISS files only; MinIO/local docs untouched
- **Background thread not async task**: ingestion is CPU-bound (embeddings); running in a thread pool avoids blocking the uvicorn event loop
- **409 not queue**: simplest safe behavior; concurrent ingest requests are rejected rather than queued
- **Iceberg id prepend**: sample_data rows match SQLite AUTOINCREMENT layout (no id); Iceberg tables require explicit BIGINT id; enumerate solves this without duplicating the generator

## Tests
- All 86 tests pass (`pytest tests/ -v`)
- Seed script verified: `python data/sample_tables/seed_database.py` → "Total rows: 1485"
