"""Seed Parquet files from sample_data for DuckDB demo mode.

Creates one Parquet file per table in data/parquet/ using DuckDB as the
writer. Run once before starting the app with QUERY_ENGINE=duckdb.

Usage:
    python data/sample_tables/seed_parquet.py
    python data/sample_tables/seed_parquet.py --dir /custom/path
"""

from __future__ import annotations

import argparse
import pathlib
import sys

PARQUET_DIR = pathlib.Path(__file__).parent.parent / "parquet"

# Column names per table, matching the INSERT order in seed_database.py.
# msme_credit omits `id` (AUTOINCREMENT); all other tables include it as first column.
TABLE_COLUMNS: dict[str, list[str]] = {
    "msme_credit": ["customer_id", "region", "segment", "outstanding", "credit_quality", "month"],
    "customer": ["id", "name", "segment", "region", "total_exposure", "internal_rating", "onboard_date"],
    "branch": ["id", "name", "region", "city", "is_active", "customer_count", "credit_target", "credit_realization"],
    "subscriber": ["id", "name", "subscription_type", "plan", "region", "status", "activation_date", "churn_risk_score", "arpu_monthly"],
    "data_usage": ["id", "subscriber_id", "month", "quota_gb", "usage_gb", "speed_mbps", "overage_charge"],
    "network": ["id", "region", "city", "network_type", "bts_count", "capacity_mbps", "utilization_pct", "status"],
    "resident": ["id", "district", "city", "province", "total", "male", "female", "year"],
    "regional_budget": ["id", "work_unit", "program", "budget_ceiling", "realization", "quarter", "year"],
    "public_service": ["id", "service_type", "agency", "application_count", "on_time_count", "satisfaction_pct", "avg_processing_days", "month"],
}


def seed_parquet(parquet_dir: pathlib.Path = PARQUET_DIR) -> None:
    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        print(f"Missing dependency: {exc}. Run: pip install pandas pyarrow")
        sys.exit(1)

    # Allow running from project root or from within the package
    project_root = pathlib.Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from data.sample_tables.sample_data import generate_all

    parquet_dir.mkdir(parents=True, exist_ok=True)
    tables = generate_all()

    print(f"Writing {len(tables)} tables to {parquet_dir} ...", flush=True)
    for table_name, rows in tables.items():
        if not rows:
            print(f"  {table_name}: empty — skipped", flush=True)
            continue
        columns = TABLE_COLUMNS.get(table_name)
        if columns is None:
            print(f"  {table_name}: no column mapping — skipped", flush=True)
            continue
        out = parquet_dir / f"{table_name}.parquet"
        df = pd.DataFrame(rows, columns=columns)
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(arrow_table, out)
        print(f"  {table_name}: {len(rows):,} rows -> {out}", flush=True)

    print(f"\nDone. {len(tables)} Parquet files written to {parquet_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Parquet files for DuckDB demo mode")
    parser.add_argument("--dir", default=str(PARQUET_DIR), help="Output directory (default: data/parquet)")
    args = parser.parse_args()
    seed_parquet(pathlib.Path(args.dir))
