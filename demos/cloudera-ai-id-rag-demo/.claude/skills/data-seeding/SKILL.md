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

`data/sample_tables/seed_parquet.py` — generates 11 DuckDB Parquet files from `sample_data.py`.

Fixed seed: `random.Random(42)` — data is deterministic. Run it again to restore factory state.

```bash
python data/sample_tables/seed_parquet.py
```

### Tables generated (2,286 rows total)

| Domain | Table | Rows | Key columns |
|--------|-------|------|------------|
| Banking | `msme_credit` | 972 | region (city), province, segment, outstanding, credit_quality, month |
| Banking | `customer` | 80 | industry, annual_revenue, debt_service_ratio, internal_rating |
| Banking | `branch` | 25 | npl_amount, deposit_balance, roi_pct, lat, lon |
| Banking | `loan_application` | 600 | loan_type (KUR), approval_rate_pct, avg_processing_days |
| Telco | `subscriber` | 80 | churn_risk_score, tenure_months, monthly_complaints |
| Telco | `data_usage` | 480 | quota_gb, usage_gb, speed_mbps, overage_charge |
| Telco | `network` | 27 | utilization_pct, avg_latency_ms, packet_loss_pct, status, lat, lon |
| Telco | `network_incident` | 162 | incident_count, sla_breach_count, mttr_hrs |
| Government | `resident` | 40 | district, city, province, total, male, female |
| Government | `regional_budget` | 88 | work_unit, program, budget_ceiling, realization, quarter, year |
| Government | `public_service` | 132 | application_count, pending_count, satisfaction_pct, complaint_count |
| **Total** | | **2,286** | |

Parquet files land in `data/parquet/`. DuckDB reads them as views at startup.

### NPL tiers (baked into msme_credit and branch)
- **Low** (Java metro + Bali): 3–6% — Jakarta, Surabaya, Bandung, Denpasar, etc.
- **Mid** (Sumatra + Kalimantan): 7–12% — Medan, Palembang, Balikpapan, etc.
- **High** (Outer islands): 13–22% — Jayapura, Kupang, Kendari, Ambon, etc.

### DOMAIN_CONFIG (approved tables per domain)
```python
"banking":    ["msme_credit", "customer", "branch", "loan_application"]
"telco":      ["subscriber", "data_usage", "network", "network_incident"]
"government": ["resident", "regional_budget", "public_service"]
"all":        all 11 tables
```

## PDF Table Extraction (Document Intelligence)

When a PDF is uploaded via `POST /api/docs/upload`, tables are automatically extracted using `pdfplumber` and registered as DuckDB views with a `doc_` prefix.

```python
# src/retrieval/table_extractor.py
extract_tables_from_pdf(path)           # → list of {name, df, page, row_count}
register_tables_as_views(tables, stem, parquet_dir)  # → list of view names
```

View naming: `doc_{stem}_{page}_{table}` (e.g. `doc_annual_report_p1_t1`)

## FAISS Vector Store

Built from documents in `data/sample_docs/{domain}/`. Each document chunked, embedded, and indexed.

```bash
python -m src.retrieval.document_loader   # rebuild vector store
make reingest                              # same via Makefile
```

### When to re-ingest
- After uploading new documents via `/upload`
- After deleting documents
- After changing `EMBEDDINGS_MODEL`
- After changing chunking parameters

### Startup behavior
`launch_app.sh` skips seeding if `msme_credit.parquet` exists and skips FAISS build if `data/vector_store/` exists.
- First boot: ~3–5 min (embedding model download + seeding)
- Warm restart: ~30 s

## DuckDB Hot-Reload

After importing a new CSV/xlsx table via `/upload`, `DuckDB.reset_connection()` in `duckdb_adapter.py` hot-reloads Parquet views without restarting uvicorn. The new table is immediately queryable.

## Adding a New Table

1. Add generation logic to `data/sample_tables/sample_data.py`
2. Register columns in `seed_parquet.py` `TABLE_COLUMNS`
3. Add column descriptions to `src/sql/metadata.py` `_COLUMN_DESCRIPTIONS`
4. Add table name to the appropriate domain in `DOMAIN_CONFIG` in `app/api.py`
5. Add few-shot SQL examples to `SYSTEM_PROMPT_SQL` in `src/llm/prompts.py`
6. Run `python data/sample_tables/seed_parquet.py` and restart

## Document Structure

```
data/sample_docs/
├─ banking/    — kebijakan_kredit_umkm.txt, sme_credit_policy_en.txt, prosedur_kyc_nasabah.txt,
│               kyc_aml_procedures_en.txt, regulasi_ojk_2025.txt, ojk_regulatory_summary_en.txt
├─ telco/      — kebijakan_layanan_pelanggan.txt, customer_service_sla_policy_en.txt,
│               regulasi_spektrum_frekuensi.txt, spectrum_network_operations_en.txt
└─ government/ — kebijakan_pelayanan_publik.txt, public_service_standard_en.txt,
                 regulasi_anggaran_daerah.txt, municipal_budget_regulation_en.txt
```

Language detection: filename ending `_en.txt` → `language="en"`; everything else → `language="id"`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "No data available" for SQL questions | `python data/sample_tables/seed_parquet.py` |
| SQL returns no rows but table exists | Check `DOMAIN_CONFIG` has the table; verify parquet file exists |
| Document questions hallucinate | `make reingest` or `make reset-vs` then restart |
| New uploaded doc not found | Trigger re-ingest via `/setup` → Re-ingest button |
| FAISS hash mismatch | `make reset-vs` — forces rebuild on next startup |
| PDF tables not appearing | Check `pdfplumber` installed: `pip install pdfplumber` |
