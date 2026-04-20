"""Seed script — creates MinIO buckets, uploads documents, and seeds Iceberg tables.

Run automatically by deployment/entrypoint.sh after MinIO, Nessie, and Trino
are healthy.

Idempotency:
  In CML mode (SEED_SENTINEL env var set by entrypoint.sh), seeding is skipped
  on subsequent restarts if the sentinel file already exists — MinIO data
  persists on the project filesystem so tables and objects are still there.

  In Docker mode (no sentinel), the schema is always dropped and recreated
  because MinIO data is ephemeral.

  Pass --force to always re-seed regardless of sentinel.

Can also be run manually against any running stack:
    QUERY_ENGINE=trino python deployment/seed_iceberg.py [--force]
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Allow importing shared data generator from project root.
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.sample_tables.sample_data import generate_all as _generate_all  # noqa: E402

_SEED_DATA: dict | None = None


def _get_data() -> dict:
    global _SEED_DATA
    if _SEED_DATA is None:
        _SEED_DATA = _generate_all()
    return _SEED_DATA

FORCE_SEED = "--force" in sys.argv

# Sentinel file path set by entrypoint.sh in CML mode.
# When it exists the seed is skipped (data is already on persistent MinIO).
_SENTINEL = Path(os.environ.get("SEED_SENTINEL", "")) if os.environ.get("SEED_SENTINEL") else None

import boto3
import botocore.exceptions
import trino.dbapi

# ── Connection defaults (can be overridden via env vars) ──────────────────

MINIO_ENDPOINT  = os.environ.get("MINIO_ENDPOINT",  "http://localhost:9000")
MINIO_KEY       = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET    = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
DOCS_BUCKET     = os.environ.get("MINIO_DOCS_BUCKET",      "rag-docs")
WAREHOUSE_BUCKET = os.environ.get("MINIO_WAREHOUSE_BUCKET", "rag-warehouse")

TRINO_HOST    = os.environ.get("TRINO_HOST",    "localhost")
TRINO_PORT    = int(os.environ.get("TRINO_PORT", "8085"))
TRINO_CATALOG = os.environ.get("TRINO_CATALOG", "iceberg")
TRINO_SCHEMA  = os.environ.get("TRINO_SCHEMA",  "demo")

DOCS_SOURCE = Path(__file__).parent.parent / "data" / "sample_docs"


# ── Helpers ────────────────────────────────────────────────────────────────

def _v(val) -> str:
    """Format a Python value as a Trino SQL literal."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, float):
        return repr(val)
    if isinstance(val, int):
        return str(val)
    # string — escape single quotes
    return "'" + str(val).replace("'", "''") + "'"


def _rows_to_values(rows: list[tuple]) -> str:
    """Convert a list of row tuples to a multi-row VALUES string."""
    return ",\n  ".join(
        "(" + ", ".join(_v(x) for x in row) + ")"
        for row in rows
    )


def _s3_client():
    import botocore.config
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_KEY,
        aws_secret_access_key=MINIO_SECRET,
        region_name="us-east-1",
        config=botocore.config.Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def _trino_cursor():
    conn = trino.dbapi.connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        user="admin",
        catalog=TRINO_CATALOG,
        schema=TRINO_SCHEMA,
        http_scheme="http",
    )
    return conn.cursor()


# ── Step 1: MinIO buckets ──────────────────────────────────────────────────

def create_buckets() -> None:
    print("[seed] Creating MinIO buckets...")
    s3 = _s3_client()
    for bucket in (DOCS_BUCKET, WAREHOUSE_BUCKET):
        try:
            s3.create_bucket(Bucket=bucket)
            print(f"[seed]   Created bucket: {bucket}")
        except s3.exceptions.BucketAlreadyOwnedByYou:
            print(f"[seed]   Bucket already exists: {bucket}")
        except botocore.exceptions.ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("BucketAlreadyExists", "BucketAlreadyOwnedByYou"):
                print(f"[seed]   Bucket already exists: {bucket}")
            else:
                raise


# ── Step 2: Upload sample documents ───────────────────────────────────────

def upload_documents() -> None:
    print(f"[seed] Uploading documents from {DOCS_SOURCE} to s3://{DOCS_BUCKET}/...")
    s3 = _s3_client()
    count = 0
    for doc_file in DOCS_SOURCE.rglob("*"):
        if not doc_file.is_file():
            continue
        # Preserve domain subdirectory: banking/file.txt, telco/file.txt, ...
        key = doc_file.relative_to(DOCS_SOURCE).as_posix()
        s3.upload_file(str(doc_file), DOCS_BUCKET, key)
        print(f"[seed]   {key}")
        count += 1
    print(f"[seed] Uploaded {count} documents.")


# ── Step 3: Seed Iceberg tables ────────────────────────────────────────────

def _already_seeded() -> bool:
    """Return True if Iceberg tables are already present and populated."""
    if _SENTINEL and _SENTINEL.exists():
        return True
    # Fall back to a live Trino probe (handles cases where sentinel was deleted)
    try:
        cur = _trino_cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM {TRINO_CATALOG}.{TRINO_SCHEMA}.kredit_umkm"
        )
        row = cur.fetchone()
        return bool(row and row[0] > 0)
    except Exception:
        return False


def _mark_seeded() -> None:
    if _SENTINEL:
        _SENTINEL.touch()
        print(f"[seed] Sentinel written: {_SENTINEL}")


def seed_tables() -> None:
    print("[seed] Seeding Iceberg tables via Trino...")
    cur = _trino_cursor()

    # Drop + recreate schema so tables match the current seed definition.
    # In CML mode this only runs on first boot (sentinel guards subsequent runs).
    cur.execute(f"DROP SCHEMA IF EXISTS {TRINO_CATALOG}.{TRINO_SCHEMA} CASCADE")
    cur.execute(
        f"CREATE SCHEMA {TRINO_CATALOG}.{TRINO_SCHEMA} "
        f"WITH (location='s3://{WAREHOUSE_BUCKET}/')"
    )
    print(f"[seed] Schema {TRINO_CATALOG}.{TRINO_SCHEMA} ready.")

    _seed_banking(cur)
    _seed_telco(cur)
    _seed_government(cur)
    print("[seed] All tables seeded.")


def _exec(cur, sql: str) -> None:
    cur.execute(sql)


def _seed_banking(cur) -> None:
    data = _get_data()
    _exec(cur, """
        CREATE TABLE kredit_umkm (
            id          BIGINT,
            nasabah_id  BIGINT,
            wilayah     VARCHAR,
            segmen      VARCHAR,
            outstanding DOUBLE,
            kualitas    VARCHAR,
            bulan       VARCHAR
        ) WITH (format='PARQUET')
    """)
    # sample_data rows: (nasabah_id, city, seg, outstanding, kualitas, month) — prepend id
    umkm_rows = [(i + 1,) + row for i, row in enumerate(data["kredit_umkm"])]
    _exec(cur, f"INSERT INTO kredit_umkm VALUES\n  {_rows_to_values(umkm_rows)}")
    print(f"[seed]   kredit_umkm: {len(umkm_rows)} rows")

    _exec(cur, """
        CREATE TABLE nasabah (
            id              BIGINT,
            nama            VARCHAR,
            segmen          VARCHAR,
            wilayah         VARCHAR,
            total_eksposur  DOUBLE,
            rating_internal VARCHAR,
            tanggal_onboard VARCHAR
        ) WITH (format='PARQUET')
    """)
    _exec(cur, f"INSERT INTO nasabah VALUES\n  {_rows_to_values(data['nasabah'])}")
    print(f"[seed]   nasabah: {len(data['nasabah'])} rows")

    _exec(cur, """
        CREATE TABLE cabang (
            id               BIGINT,
            nama             VARCHAR,
            wilayah          VARCHAR,
            kota             VARCHAR,
            aktif            INTEGER,
            jumlah_nasabah   BIGINT,
            target_kredit    DOUBLE,
            realisasi_kredit DOUBLE
        ) WITH (format='PARQUET')
    """)
    _exec(cur, f"INSERT INTO cabang VALUES\n  {_rows_to_values(data['cabang'])}")
    print(f"[seed]   cabang: {len(data['cabang'])} rows")


def _seed_telco(cur) -> None:
    data = _get_data()
    _exec(cur, """
        CREATE TABLE pelanggan (
            id               BIGINT,
            nama             VARCHAR,
            tipe             VARCHAR,
            paket            VARCHAR,
            wilayah          VARCHAR,
            status           VARCHAR,
            tanggal_aktivasi VARCHAR,
            churn_risk_score INTEGER,
            arpu_monthly     DOUBLE
        ) WITH (format='PARQUET')
    """)
    _exec(cur, f"INSERT INTO pelanggan VALUES\n  {_rows_to_values(data['pelanggan'])}")
    print(f"[seed]   pelanggan: {len(data['pelanggan'])} rows")

    _exec(cur, """
        CREATE TABLE penggunaan_data (
            id             BIGINT,
            pelanggan_id   BIGINT,
            bulan          VARCHAR,
            kuota_gb       DOUBLE,
            penggunaan_gb  DOUBLE,
            kecepatan_mbps DOUBLE,
            biaya_tambahan DOUBLE
        ) WITH (format='PARQUET')
    """)
    _exec(cur, f"INSERT INTO penggunaan_data VALUES\n  {_rows_to_values(data['penggunaan_data'])}")
    print(f"[seed]   penggunaan_data: {len(data['penggunaan_data'])} rows")

    _exec(cur, """
        CREATE TABLE jaringan (
            id             BIGINT,
            wilayah        VARCHAR,
            kota           VARCHAR,
            tipe_jaringan  VARCHAR,
            jumlah_bts     INTEGER,
            kapasitas_mbps DOUBLE,
            utilisasi_pct  DOUBLE,
            status         VARCHAR
        ) WITH (format='PARQUET')
    """)
    _exec(cur, f"INSERT INTO jaringan VALUES\n  {_rows_to_values(data['jaringan'])}")
    print(f"[seed]   jaringan: {len(data['jaringan'])} rows")


def _seed_government(cur) -> None:
    data = _get_data()
    _exec(cur, """
        CREATE TABLE penduduk (
            id        BIGINT,
            kecamatan VARCHAR,
            kabupaten VARCHAR,
            provinsi  VARCHAR,
            jumlah    BIGINT,
            laki_laki BIGINT,
            perempuan BIGINT,
            tahun     INTEGER
        ) WITH (format='PARQUET')
    """)
    _exec(cur, f"INSERT INTO penduduk VALUES\n  {_rows_to_values(data['penduduk'])}")
    print(f"[seed]   penduduk: {len(data['penduduk'])} rows")

    _exec(cur, """
        CREATE TABLE anggaran_daerah (
            id           BIGINT,
            satuan_kerja VARCHAR,
            program      VARCHAR,
            pagu         DOUBLE,
            realisasi    DOUBLE,
            triwulan     VARCHAR,
            tahun        INTEGER
        ) WITH (format='PARQUET')
    """)
    _exec(cur, f"INSERT INTO anggaran_daerah VALUES\n  {_rows_to_values(data['anggaran_daerah'])}")
    print(f"[seed]   anggaran_daerah: {len(data['anggaran_daerah'])} rows")

    _exec(cur, """
        CREATE TABLE layanan_publik (
            id                  BIGINT,
            jenis_layanan       VARCHAR,
            satuan_kerja        VARCHAR,
            jumlah_permohonan   BIGINT,
            selesai_tepat_waktu BIGINT,
            kepuasan_pct        DOUBLE,
            rata_waktu_hari     DOUBLE,
            bulan               VARCHAR
        ) WITH (format='PARQUET')
    """)
    _exec(cur, f"INSERT INTO layanan_publik VALUES\n  {_rows_to_values(data['layanan_publik'])}")
    print(f"[seed]   layanan_publik: {len(data['layanan_publik'])} rows")



# ── Entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print(" Iceberg seed — MinIO + Nessie + Trino")
    print("=" * 60)

    if not FORCE_SEED and _already_seeded():
        print("[seed] Data already present — skipping seed (use --force to override).")
        print("[seed] Sentinel:", _SENTINEL)
        sys.exit(0)

    try:
        create_buckets()
        upload_documents()
        seed_tables()
        _mark_seeded()
        print("=" * 60)
        print(" Seed complete.")
        print("=" * 60)
    except Exception as exc:
        print(f"[seed] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
