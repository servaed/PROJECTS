---
name: data-seeding
description: Seeding Parquet data, resetting the vector store, re-ingesting documents, and managing DuckDB tables. Use when adding data, resetting demo state, or debugging data issues.
---

# Skill: Data Seeding & Reset

## Quick Reference

```bash
make seed          # Seed Parquet files (idempotent — skips if msme_credit.parquet exists)
make reingest      # Rebuild FAISS vector store from source documents
make reset-vs      # Delete data/vector_store/ only (next startup re-ingests)
make demo-reset    # Full factory reset: clear VS + reseed + reingest
```

## Parquet Seeding

`data/sample_tables/seed_parquet.py` — generates 9 DuckDB Parquet files from `sample_data.py`.

Fixed seed: `random.Random(42)` — data is deterministic. Run it again to restore factory state.

```bash
python data/sample_tables/seed_parquet.py
```

### Tables generated

| Domain | Table | Rows |
|--------|-------|------|
| Banking | `msme_credit` | 540 |
| Banking | `customer` | 80 |
| Banking | `branch` | 25 |
| Telco | `subscriber` | 80 |
| Telco | `data_usage` | 480 |
| Telco | `network` | 20 |
| Government | `resident` | 40 |
| Government | `regional_budget` | 88 |
| Government | `public_service` | 132 |
| **Total** | | **1,485** |

Parquet files land in `data/sample_tables/*.parquet`. DuckDB reads them as views at startup.

## FAISS Vector Store

Built from documents in `data/sample_docs/{domain}/`. Each document chunked, embedded, and indexed.

```bash
# Rebuild vector store (documents preserved)
python -m src.retrieval.document_loader

# Or via Makefile
make reingest
```

### When to re-ingest
- After uploading new documents via `/upload`
- After deleting documents
- After changing `EMBEDDINGS_MODEL` env var
- After changing chunking parameters in `src/retrieval/chunking.py`

### Startup behavior
`launch_app.sh` skips seeding if `msme_credit.parquet` exists and skips FAISS build if `data/vector_store/` exists. First boot: ~3–5 min (model download + embedding). Warm restart: ~30 s.

### Integrity hash
After every FAISS build, a SHA-256 hash is written to `data/vector_store/index.hash`. On load, the hash is verified — mismatch causes a rebuild rather than loading a corrupt index.

## DuckDB Hot-Reload

After importing a new CSV/xlsx table via `/upload`, `DuckDB.reset_connection()` in `duckdb_adapter.py` hot-reloads Parquet views without restarting uvicorn. The new table is immediately queryable.

## Adding a New Domain or Table

1. Add data generation logic to `data/sample_tables/sample_data.py`
2. Register the new table in `seed_parquet.py`
3. Add the table name to `SQL_APPROVED_TABLES` env var (or `.env.local`)
4. If it's a new domain: add sample documents to `data/sample_docs/{domain}/`, add domain to `/api/domains`, update sidebar `domainMeta` in `index.html`
5. Run `make demo-reset` to rebuild everything

## CML Nightly Job

`data/cml_jobs/nightly_reingest.py` — scheduled FAISS rebuild, logs to MLflow if configured.
`deployment/cml_job.yaml` — CML Job definitions (nightly reingest + weekly reseed).

## Document Structure

```
data/sample_docs/
├─ banking/
│   ├─ kebijakan_kredit_umkm.txt      # ID — credit policy
│   ├─ sme_credit_policy_en.txt       # EN — same content
│   ├─ prosedur_kyc_nasabah.txt       # ID — KYC procedure
│   ├─ kyc_aml_procedures_en.txt      # EN
│   ├─ regulasi_ojk_2025.txt          # ID — OJK regulation
│   └─ ojk_regulatory_summary_en.txt  # EN
├─ telco/
│   ├─ kebijakan_layanan_pelanggan.txt
│   ├─ customer_service_sla_policy_en.txt
│   ├─ regulasi_spektrum_frekuensi.txt
│   └─ spectrum_network_operations_en.txt
└─ government/
    ├─ kebijakan_pelayanan_publik.txt
    ├─ public_service_standard_en.txt
    ├─ regulasi_anggaran_daerah.txt
    └─ municipal_budget_regulation_en.txt
```

Language detection: filename ending `_en.txt` → `language="en"`; everything else → `language="id"`.

## Troubleshooting Data Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| "No data available" for SQL questions | Parquet files missing | `make seed` |
| SQL query returns no rows | Table not registered in DuckDB | Check `SQL_APPROVED_TABLES`; restart app |
| Document questions hallucinate | Vector store stale or missing | `make reingest` or `make reset-vs` then restart |
| New uploaded doc not found in chat | Auto-ingest was disabled | Manually trigger via `/upload` Re-ingest button or `make reingest` |
| FAISS load fails with hash mismatch | Index file corrupted | `make reset-vs` — forces full rebuild on next startup |
