"""Database schema discovery — builds schema context for LLM SQL generation.

Only exposes approved tables to prevent the LLM from accessing sensitive tables.
Column descriptions are included alongside types so the SQL model understands
the semantic meaning of each field without needing to inspect sample data.
"""

from __future__ import annotations

from src.config.settings import settings
from src.config.logging import get_logger
from src.connectors.db_adapter import get_table_names, get_table_schema

logger = get_logger(__name__)

# ── Column-level descriptions ──────────────────────────────────────────────
# Maps "table.column" → human-readable description injected into the schema
# context.  This helps the SQL model generate semantically correct queries
# (e.g. knowing that kualitas is a 1-5 bucket, not a free-text field).

_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # ── Banking: kredit_umkm ──────────────────────────────────────────────
    "kredit_umkm.id":          "primary key",
    "kredit_umkm.nasabah_id":  "foreign key → nasabah.id",
    "kredit_umkm.wilayah":     "region/province (e.g. Jakarta, Jawa Barat, Bali)",
    "kredit_umkm.segmen":      "MSME segment: mikro | kecil | menengah",
    "kredit_umkm.outstanding": "outstanding loan balance in IDR (rupiah)",
    "kredit_umkm.kualitas":    "credit quality per OJK: Lancar | Dalam Perhatian Khusus | Kurang Lancar | Diragukan | Macet",
    "kredit_umkm.bulan":       "reporting month (YYYY-MM, e.g. 2026-03)",

    # ── Banking: nasabah ──────────────────────────────────────────────────
    "nasabah.id":              "primary key",
    "nasabah.nama":            "customer full name",
    "nasabah.segmen":          "customer segment: mikro | kecil | menengah",
    "nasabah.wilayah":         "home region/province",
    "nasabah.total_eksposur":  "total credit exposure across all products in IDR",

    # ── Banking: cabang ───────────────────────────────────────────────────
    "cabang.id":               "primary key",
    "cabang.nama":             "branch office name",
    "cabang.wilayah":          "region/province",
    "cabang.kota":             "city",
    "cabang.aktif":            "branch status: 1 = active, 0 = inactive",

    # ── Telco: pelanggan ──────────────────────────────────────────────────
    "pelanggan.id":                "primary key",
    "pelanggan.nama":              "subscriber name",
    "pelanggan.tipe":              "subscription type: prepaid | postpaid",
    "pelanggan.paket":             "active plan/package name",
    "pelanggan.wilayah":           "subscriber region/province",
    "pelanggan.status":            "account status: aktif | suspend | churn",
    "pelanggan.tanggal_aktivasi":  "activation date (YYYY-MM-DD)",
    "pelanggan.churn_risk_score":  "predicted churn risk 0–100; ≥70 = high risk",

    # ── Telco: jaringan ───────────────────────────────────────────────────
    "jaringan.id":              "primary key",
    "jaringan.wilayah":         "region/province",
    "jaringan.kota":            "city",
    "jaringan.tipe_jaringan":   "network generation: 4G | 5G | 3G",
    "jaringan.jumlah_bts":      "number of base transceiver stations",
    "jaringan.kapasitas_mbps":  "total network capacity in Mbps",
    "jaringan.utilisasi_pct":   "current utilization as percentage of capacity (0–100)",
    "jaringan.status":          "operational status: normal | kritis | gangguan",

    # ── Telco: penggunaan_data ────────────────────────────────────────────
    "penggunaan_data.id":               "primary key",
    "penggunaan_data.pelanggan_id":     "foreign key → pelanggan.id",
    "penggunaan_data.bulan":            "billing month (YYYY-MM)",
    "penggunaan_data.kuota_gb":         "subscribed data quota in GB",
    "penggunaan_data.penggunaan_gb":    "actual data usage in GB",
    "penggunaan_data.kecepatan_mbps":   "average experienced speed in Mbps",
    "penggunaan_data.biaya_tambahan":   "overage charges in IDR",

    # ── Government: anggaran_daerah ───────────────────────────────────────
    "anggaran_daerah.id":           "primary key",
    "anggaran_daerah.satuan_kerja": "work unit / government agency (SKPD)",
    "anggaran_daerah.program":      "budget program name",
    "anggaran_daerah.pagu":         "allocated budget in IDR",
    "anggaran_daerah.realisasi":    "actual spending to date in IDR",
    "anggaran_daerah.triwulan":     "quarter: Q1 | Q2 | Q3 | Q4",
    "anggaran_daerah.tahun":        "fiscal year (e.g. 2026)",

    # ── Government: layanan_publik ────────────────────────────────────────
    "layanan_publik.id":                    "primary key",
    "layanan_publik.jenis_layanan":         "service type (e.g. KTP, IMB, Akta Kelahiran)",
    "layanan_publik.satuan_kerja":          "responsible government agency",
    "layanan_publik.jumlah_permohonan":     "total applications received",
    "layanan_publik.selesai_tepat_waktu":   "applications completed on time",
    "layanan_publik.kepuasan_pct":          "citizen satisfaction rate 0–100 (%)",
    "layanan_publik.rata_waktu_hari":       "average processing time in working days",
    "layanan_publik.bulan":                 "reporting month (YYYY-MM)",

    # ── Government: penduduk ──────────────────────────────────────────────
    "penduduk.id":          "primary key",
    "penduduk.wilayah":     "region/kelurahan",
    "penduduk.kota":        "city/kabupaten",
    "penduduk.jumlah":      "registered resident count",
    "penduduk.tahun":       "census year",
}


def get_approved_tables() -> list[str]:
    """Return the intersection of approved tables and tables that actually exist."""
    existing = get_table_names()
    approved = settings.approved_tables

    if not approved:
        return existing

    visible = [t for t in approved if t in existing]
    hidden  = [t for t in approved if t not in existing]
    if hidden:
        logger.warning("Approved tables not found in database: %s", hidden)
    return visible


def build_schema_context(tables: list[str] | None = None) -> str:
    """Build an enriched text schema description for SQL generation.

    Includes column types AND semantic descriptions so the LLM generates
    semantically correct queries (e.g. filters kualitas by the correct values,
    uses churn_risk_score ≥ 70 for high-risk, etc.).
    """
    if tables is None:
        tables = get_approved_tables()

    if not tables:
        return "Tidak ada tabel yang tersedia."

    lines = []
    for table in tables:
        try:
            columns = get_table_schema(table)
            col_lines = []
            for c in columns:
                desc = _COLUMN_DESCRIPTIONS.get(f"{table}.{c['name']}", "")
                desc_str = f"  -- {desc}" if desc else ""
                col_lines.append(f"  {c['name']} ({c['type']}){desc_str}")
            lines.append(f"Tabel: {table}\nKolom:\n" + "\n".join(col_lines))
        except Exception as exc:
            logger.error("Failed to get schema for table '%s': %s", table, exc)

    return "\n\n".join(lines)
