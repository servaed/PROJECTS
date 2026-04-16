"""Seed script — creates and populates the demo SQLite database with sample banking,
telco, and government data.

Run once before starting the app:
    python data/sample_tables/seed_database.py
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "demo.db"


def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ── BANKING: kredit_umkm ───────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS kredit_umkm")
    cur.execute("""
        CREATE TABLE kredit_umkm (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nasabah_id  INTEGER,
            wilayah     TEXT,
            segmen      TEXT,
            outstanding REAL,
            kualitas    TEXT,
            bulan       TEXT
        )
    """)
    umkm_rows = [
        # 2026-03 (latest)
        (1,  "Jakarta",         "Mikro",      450_000_000,   "Lancar",        "2026-03"),
        (2,  "Jakarta",         "Kecil",    2_500_000_000,   "Lancar",        "2026-03"),
        (3,  "Jakarta",         "Menengah", 15_000_000_000,  "DPK",           "2026-03"),
        (4,  "Surabaya",        "Mikro",      380_000_000,   "Lancar",        "2026-03"),
        (5,  "Surabaya",        "Kecil",    1_800_000_000,   "Lancar",        "2026-03"),
        (6,  "Surabaya",        "Menengah",  8_500_000_000,  "Lancar",        "2026-03"),
        (7,  "Bandung",         "Mikro",      200_000_000,   "Lancar",        "2026-03"),
        (8,  "Bandung",         "Kecil",      950_000_000,   "Kurang Lancar", "2026-03"),
        (9,  "Medan",           "Mikro",      300_000_000,   "Lancar",        "2026-03"),
        (10, "Medan",           "Kecil",    1_450_000_000,   "Lancar",        "2026-03"),
        (11, "Makassar",        "Kecil",    1_200_000_000,   "Lancar",        "2026-03"),
        (12, "Makassar",        "Mikro",      175_000_000,   "Lancar",        "2026-03"),
        (13, "Jakarta",         "Mikro",      120_000_000,   "Macet",         "2026-03"),
        (14, "Semarang",        "Kecil",    1_650_000_000,   "Lancar",        "2026-03"),
        (15, "Semarang",        "Menengah",  6_200_000_000,  "Lancar",        "2026-03"),
        (16, "Yogyakarta",      "Mikro",      280_000_000,   "Lancar",        "2026-03"),
        (17, "Yogyakarta",      "Kecil",      880_000_000,   "DPK",           "2026-03"),
        (18, "Palembang",       "Kecil",    1_100_000_000,   "Lancar",        "2026-03"),
        (19, "Balikpapan",      "Menengah",  4_800_000_000,  "Lancar",        "2026-03"),
        (20, "Denpasar",        "Mikro",      320_000_000,   "Lancar",        "2026-03"),
        # 2026-02
        (21, "Jakarta",         "Kecil",    3_000_000_000,   "Lancar",        "2026-02"),
        (22, "Jakarta",         "Menengah", 14_200_000_000,  "Lancar",        "2026-02"),
        (23, "Surabaya",        "Menengah", 12_000_000_000,  "Lancar",        "2026-02"),
        (24, "Jakarta",         "Kecil",    2_200_000_000,   "Lancar",        "2026-02"),
        (25, "Jakarta",         "Mikro",      410_000_000,   "DPK",           "2026-02"),
        (26, "Bandung",         "Kecil",    1_100_000_000,   "Lancar",        "2026-02"),
        (27, "Medan",           "Mikro",      260_000_000,   "Lancar",        "2026-02"),
        (28, "Semarang",        "Kecil",    1_500_000_000,   "Lancar",        "2026-02"),
        (29, "Makassar",        "Kecil",    1_050_000_000,   "Lancar",        "2026-02"),
        (30, "Denpasar",        "Mikro",      290_000_000,   "Kurang Lancar", "2026-02"),
        # 2026-01
        (31, "Jakarta",         "Kecil",    2_850_000_000,   "Lancar",        "2026-01"),
        (32, "Jakarta",         "Menengah", 13_500_000_000,  "Lancar",        "2026-01"),
        (33, "Surabaya",        "Kecil",    1_700_000_000,   "Lancar",        "2026-01"),
        (34, "Bandung",         "Kecil",    1_020_000_000,   "Lancar",        "2026-01"),
        (35, "Medan",           "Kecil",    1_320_000_000,   "Lancar",        "2026-01"),
        (36, "Makassar",        "Menengah",  5_600_000_000,  "Lancar",        "2026-01"),
        (37, "Semarang",        "Menengah",  5_900_000_000,  "DPK",           "2026-01"),
        (38, "Balikpapan",      "Kecil",      920_000_000,   "Lancar",        "2026-01"),
        # 2025-12
        (39, "Jakarta",         "Kecil",    2_700_000_000,   "Lancar",        "2025-12"),
        (40, "Jakarta",         "Menengah", 13_100_000_000,  "Lancar",        "2025-12"),
        (41, "Surabaya",        "Kecil",    1_620_000_000,   "Lancar",        "2025-12"),
        (42, "Bandung",         "Mikro",      230_000_000,   "Lancar",        "2025-12"),
        (43, "Medan",           "Kecil",    1_200_000_000,   "Macet",         "2025-12"),
        (44, "Makassar",        "Kecil",      980_000_000,   "Lancar",        "2025-12"),
        (45, "Semarang",        "Kecil",    1_380_000_000,   "Lancar",        "2025-12"),
    ]
    cur.executemany(
        "INSERT INTO kredit_umkm (nasabah_id,wilayah,segmen,outstanding,kualitas,bulan) VALUES (?,?,?,?,?,?)",
        umkm_rows,
    )

    # ── BANKING: nasabah ───────────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS nasabah")
    cur.execute("""
        CREATE TABLE nasabah (
            id             INTEGER PRIMARY KEY,
            nama           TEXT,
            segmen         TEXT,
            wilayah        TEXT,
            total_eksposur REAL,
            rating_internal TEXT,
            tanggal_onboard TEXT
        )
    """)
    nasabah_rows = [
        (1,  "PT Maju Jaya Abadi",       "Korporasi", "Jakarta",    85_000_000_000, "A",  "2018-03-10"),
        (2,  "CV Berkah Usaha",          "UMKM",      "Jakarta",     3_200_000_000, "B+", "2020-06-15"),
        (3,  "UD Sumber Rejeki",         "UMKM",      "Surabaya",    1_900_000_000, "B",  "2021-01-20"),
        (4,  "PT Nusantara Sejati",      "Korporasi", "Jakarta",    60_000_000_000, "A-", "2017-08-05"),
        (5,  "Koperasi Tani Makmur",     "UMKM",      "Bandung",     2_500_000_000, "B",  "2019-11-30"),
        (6,  "PT Logistik Indonesia",    "Korporasi", "Surabaya",   42_000_000_000, "B+", "2016-05-12"),
        (7,  "UD Karya Mandiri",         "UMKM",      "Medan",         980_000_000, "B-", "2022-04-08"),
        (8,  "PT Energi Nusantara",      "Korporasi", "Jakarta",    95_000_000_000, "AA", "2015-09-22"),
        (9,  "CV Mitra Dagang",          "UMKM",      "Makassar",    1_500_000_000, "B",  "2021-07-17"),
        (10, "PT Tekstil Nusantara",     "Korporasi", "Bandung",    38_000_000_000, "B+", "2019-02-14"),
        (11, "PT Konstruksi Prima",      "Korporasi", "Surabaya",   55_000_000_000, "A-", "2016-12-01"),
        (12, "CV Agro Sejahtera",        "UMKM",      "Semarang",    2_100_000_000, "B",  "2020-08-09"),
        (13, "PT Farmasi Nusantara",     "Korporasi", "Jakarta",    48_000_000_000, "A",  "2018-06-25"),
        (14, "UD Hasil Laut Bersama",    "UMKM",      "Makassar",    1_200_000_000, "B-", "2022-10-03"),
        (15, "PT Media Digital Indo",    "Korporasi", "Jakarta",    30_000_000_000, "B+", "2020-01-15"),
    ]
    cur.executemany("INSERT INTO nasabah VALUES (?,?,?,?,?,?,?)", nasabah_rows)

    # ── BANKING: cabang ────────────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS cabang")
    cur.execute("""
        CREATE TABLE cabang (
            id              INTEGER PRIMARY KEY,
            nama            TEXT,
            wilayah         TEXT,
            kota            TEXT,
            aktif           INTEGER,
            jumlah_nasabah  INTEGER,
            target_kredit   REAL,
            realisasi_kredit REAL
        )
    """)
    cabang_rows = [
        (1,  "Cabang Jakarta Pusat",    "Jakarta",      "Jakarta",    1, 12500,  85_000_000_000, 88_200_000_000),
        (2,  "Cabang Jakarta Selatan",  "Jakarta",      "Jakarta",    1, 10800,  75_000_000_000, 78_500_000_000),
        (3,  "Cabang Jakarta Utara",    "Jakarta",      "Jakarta",    1,  8200,  55_000_000_000, 53_400_000_000),
        (4,  "Cabang Jakarta Timur",    "Jakarta",      "Jakarta",    1,  7600,  48_000_000_000, 46_800_000_000),
        (5,  "Cabang Surabaya Utama",   "Jawa Timur",   "Surabaya",   1,  9200,  60_000_000_000, 62_100_000_000),
        (6,  "Cabang Surabaya Selatan", "Jawa Timur",   "Surabaya",   1,  5400,  35_000_000_000, 33_800_000_000),
        (7,  "Cabang Bandung Utama",    "Jawa Barat",   "Bandung",    1,  7100,  42_000_000_000, 41_200_000_000),
        (8,  "Cabang Medan Utama",      "Sumatera Utara","Medan",     1,  6300,  38_000_000_000, 36_500_000_000),
        (9,  "Cabang Makassar Utama",   "Sulawesi Selatan","Makassar",1,  4800,  28_000_000_000, 27_400_000_000),
        (10, "Cabang Semarang Utama",   "Jawa Tengah",  "Semarang",   1,  5900,  35_000_000_000, 36_800_000_000),
        (11, "Cabang Yogyakarta",       "DI Yogyakarta","Yogyakarta", 1,  4200,  22_000_000_000, 21_100_000_000),
        (12, "Cabang Palembang",        "Sumatera Selatan","Palembang",1, 3800,  20_000_000_000, 19_500_000_000),
        (13, "Cabang Balikpapan",       "Kalimantan",   "Balikpapan", 1,  3200,  18_000_000_000, 18_900_000_000),
        (14, "Cabang Denpasar",         "Bali",         "Denpasar",   1,  4500,  25_000_000_000, 24_600_000_000),
    ]
    cur.executemany("INSERT INTO cabang VALUES (?,?,?,?,?,?,?,?)", cabang_rows)

    # ── TELCO: pelanggan ───────────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS pelanggan")
    cur.execute("""
        CREATE TABLE pelanggan (
            id                INTEGER PRIMARY KEY,
            nama              TEXT,
            tipe              TEXT,
            paket             TEXT,
            wilayah           TEXT,
            status            TEXT,
            tanggal_aktivasi  TEXT,
            churn_risk_score  INTEGER,
            arpu_monthly      REAL
        )
    """)
    pelanggan_rows = [
        (1,  "Budi Santoso",          "Prabayar",   "Basic",      "Jakarta",   "Aktif",      "2022-03-15", 25,  55_000),
        (2,  "Siti Rahayu",           "Pascabayar", "Premium",    "Surabaya",  "Aktif",      "2021-07-20", 12, 280_000),
        (3,  "PT Maju Digital",       "Korporasi",  "Enterprise", "Jakarta",   "Aktif",      "2020-01-05",  5, 5_200_000),
        (4,  "Ahmad Fauzi",           "Prabayar",   "Starter",    "Bandung",   "Aktif",      "2023-11-10", 72,  30_000),
        (5,  "CV Teknologi Muda",     "Korporasi",  "Business",   "Medan",     "Aktif",      "2021-04-18", 18, 1_800_000),
        (6,  "Dewi Lestari",          "Pascabayar", "Standard",   "Jakarta",   "Aktif",      "2022-09-30", 45, 120_000),
        (7,  "Rudi Hermawan",         "Prabayar",   "Basic",      "Makassar",  "Tidak Aktif","2019-06-12", 88,  20_000),
        (8,  "PT Nusantara Retail",   "Korporasi",  "Enterprise", "Surabaya",  "Aktif",      "2020-08-22",  8, 8_400_000),
        (9,  "Rina Wijaya",           "Pascabayar", "Unlimited",  "Bali",      "Aktif",      "2023-02-14", 30, 350_000),
        (10, "Hendra Gunawan",        "Prabayar",   "Standard",   "Jakarta",   "Aktif",      "2024-01-08", 55,  75_000),
        (11, "Yuni Pratiwi",          "Pascabayar", "Premium",    "Bandung",   "Aktif",      "2021-12-01", 20, 270_000),
        (12, "PT Agro Nusantara",     "Korporasi",  "Business",   "Semarang",  "Aktif",      "2022-05-17",  3, 2_100_000),
        (13, "Fahri Kusuma",          "Prabayar",   "Starter",    "Jakarta",   "Aktif",      "2024-06-20", 78,  25_000),
        (14, "Maya Indah",            "Pascabayar", "Standard",   "Surabaya",  "Aktif",      "2022-03-08", 42, 115_000),
        (15, "PT Wisata Bahari",      "Korporasi",  "Business",   "Bali",      "Aktif",      "2021-10-15", 10, 3_600_000),
        (16, "Dani Prasetyo",         "Prabayar",   "Basic",      "Semarang",  "Aktif",      "2023-07-22", 65,  45_000),
        (17, "Lena Marlina",          "Pascabayar", "Premium",    "Medan",     "Aktif",      "2020-11-18", 15, 260_000),
        (18, "CV Mitra Logistik",     "Korporasi",  "Business",   "Makassar",  "Aktif",      "2022-08-30",  6, 1_500_000),
        (19, "Bagas Purnomo",         "Prabayar",   "Standard",   "Bandung",   "Tidak Aktif","2020-05-10", 91,  40_000),
        (20, "Nisa Amalia",           "Pascabayar", "Unlimited",  "Jakarta",   "Aktif",      "2023-09-05", 18, 380_000),
    ]
    cur.executemany(
        "INSERT INTO pelanggan VALUES (?,?,?,?,?,?,?,?,?)",
        pelanggan_rows,
    )

    # ── TELCO: penggunaan_data ─────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS penggunaan_data")
    cur.execute("""
        CREATE TABLE penggunaan_data (
            id               INTEGER PRIMARY KEY,
            pelanggan_id     INTEGER,
            bulan            TEXT,
            kuota_gb         REAL,
            penggunaan_gb    REAL,
            kecepatan_mbps   REAL,
            biaya_tambahan   REAL
        )
    """)
    usage_rows = [
        # 2026-03
        (1,  1,  "2026-03",  20.0,  18.5,  22.3,       0),
        (2,  2,  "2026-03", 100.0,  95.2,  48.7,       0),
        (3,  4,  "2026-03",   5.0,   6.8,   8.1,  15_000),
        (4,  6,  "2026-03",  50.0,  41.3,  31.2,       0),
        (5,  9,  "2026-03", 999.0,  85.6,  49.2,       0),
        (6,  10, "2026-03",  50.0,  52.1,  28.4,  10_000),
        (7,  11, "2026-03", 100.0,  77.3,  45.8,       0),
        (8,  13, "2026-03",   5.0,   7.2,   7.5,  22_000),
        (9,  14, "2026-03",  50.0,  48.9,  30.1,       0),
        (10, 16, "2026-03",  20.0,  21.5,  18.6,   5_000),
        (11, 17, "2026-03", 100.0,  88.4,  44.2,       0),
        (12, 20, "2026-03", 999.0, 102.3,  51.0,       0),
        # 2026-02
        (13,  1, "2026-02",  20.0,  15.2,  21.1,       0),
        (14,  2, "2026-02", 100.0, 102.8,  50.1,  25_000),
        (15,  4, "2026-02",   5.0,   4.1,   7.8,       0),
        (16,  6, "2026-02",  50.0,  49.9,  30.5,       0),
        (17,  9, "2026-02", 999.0, 120.3,  48.0,       0),
        (18, 10, "2026-02",  50.0,  54.8,  27.9,  15_000),
        (19, 11, "2026-02", 100.0,  82.1,  46.3,       0),
        (20, 13, "2026-02",   5.0,   5.9,   7.1,   9_000),
        (21, 14, "2026-02",  50.0,  43.5,  29.8,       0),
        (22, 16, "2026-02",  20.0,  18.7,  19.2,       0),
        (23, 17, "2026-02", 100.0,  94.6,  43.7,       0),
        (24, 20, "2026-02", 999.0,  96.8,  50.2,       0),
        # 2026-01
        (25,  1, "2026-01",  20.0,  16.8,  20.5,       0),
        (26,  2, "2026-01", 100.0,  89.4,  47.3,       0),
        (27,  4, "2026-01",   5.0,   5.3,   8.0,   3_000),
        (28,  6, "2026-01",  50.0,  38.2,  29.4,       0),
        (29,  9, "2026-01", 999.0, 110.5,  47.8,       0),
        (30, 11, "2026-01", 100.0,  91.2,  45.5,       0),
    ]
    cur.executemany(
        "INSERT INTO penggunaan_data VALUES (?,?,?,?,?,?,?)",
        usage_rows,
    )

    # ── TELCO: jaringan ────────────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS jaringan")
    cur.execute("""
        CREATE TABLE jaringan (
            id              INTEGER PRIMARY KEY,
            wilayah         TEXT,
            kota            TEXT,
            tipe_jaringan   TEXT,
            jumlah_bts      INTEGER,
            kapasitas_mbps  REAL,
            utilisasi_pct   REAL,
            status          TEXT
        )
    """)
    jaringan_rows = [
        (1,  "Jakarta",          "Jakarta",    "5G",      320, 10000.0, 62.5, "Optimal"),
        (2,  "Jakarta",          "Jakarta",    "4G LTE",  580,  5800.0, 78.3, "Optimal"),
        (3,  "Jawa Barat",       "Bandung",    "4G LTE",  210,  2100.0, 71.2, "Optimal"),
        (4,  "Jawa Timur",       "Surabaya",   "4G LTE",  245,  2450.0, 85.6, "Kritis"),
        (5,  "Sumatera Utara",   "Medan",      "4G LTE",  180,  1800.0, 55.0, "Optimal"),
        (6,  "Sulawesi Selatan", "Makassar",   "4G LTE",  120,  1200.0, 48.2, "Optimal"),
        (7,  "Jawa Tengah",      "Semarang",   "4G LTE",  155,  1550.0, 68.9, "Optimal"),
        (8,  "Bali",             "Denpasar",   "4G LTE",  130,  1300.0, 90.1, "Kritis"),
        (9,  "Kalimantan Timur", "Balikpapan", "4G LTE",   95,   950.0, 42.7, "Optimal"),
        (10, "Papua",            "Jayapura",   "4G LTE",   45,   450.0, 33.1, "Optimal"),
        (11, "DI Yogyakarta",    "Yogyakarta", "4G LTE",   98,   980.0, 74.5, "Optimal"),
        (12, "Sumatera Selatan", "Palembang",  "4G LTE",   88,   880.0, 61.3, "Optimal"),
        (13, "Jawa Timur",       "Malang",     "4G LTE",  112,  1120.0, 79.8, "Tinggi"),
        (14, "Jawa Barat",       "Bekasi",     "4G LTE",  198,  1980.0, 83.4, "Tinggi"),
        (15, "Jakarta",          "Jakarta",    "4.5G",    240,  3600.0, 70.2, "Optimal"),
    ]
    cur.executemany(
        "INSERT INTO jaringan VALUES (?,?,?,?,?,?,?,?)",
        jaringan_rows,
    )

    # ── GOVERNMENT: penduduk ───────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS penduduk")
    cur.execute("""
        CREATE TABLE penduduk (
            id            INTEGER PRIMARY KEY,
            kecamatan     TEXT,
            kabupaten     TEXT,
            provinsi      TEXT,
            jumlah        INTEGER,
            laki_laki     INTEGER,
            perempuan     INTEGER,
            tahun         INTEGER
        )
    """)
    penduduk_rows = [
        (1,  "Gambir",          "Jakarta Pusat",    "DKI Jakarta",        74_000,  36_500,  37_500, 2025),
        (2,  "Tanah Abang",     "Jakarta Pusat",    "DKI Jakarta",       215_000, 107_000, 108_000, 2025),
        (3,  "Kebayoran Baru",  "Jakarta Selatan",  "DKI Jakarta",       180_000,  89_000,  91_000, 2025),
        (4,  "Penjaringan",     "Jakarta Utara",    "DKI Jakarta",       190_000,  98_000,  92_000, 2025),
        (5,  "Cempaka Putih",   "Jakarta Pusat",    "DKI Jakarta",       130_000,  64_000,  66_000, 2025),
        (6,  "Tegalsari",       "Surabaya",         "Jawa Timur",        108_000,  53_000,  55_000, 2025),
        (7,  "Coblong",         "Bandung",          "Jawa Barat",        142_000,  70_000,  72_000, 2025),
        (8,  "Medan Baru",      "Medan",            "Sumatera Utara",     80_000,  39_000,  41_000, 2025),
        (9,  "Rappocini",       "Makassar",         "Sulawesi Selatan",  120_000,  59_000,  61_000, 2025),
        (10, "Semarang Tengah", "Semarang",         "Jawa Tengah",        70_000,  34_500,  35_500, 2025),
        (11, "Umbulharjo",      "Yogyakarta",       "DI Yogyakarta",      65_000,  32_000,  33_000, 2025),
        (12, "Ilir Barat I",    "Palembang",        "Sumatera Selatan",   95_000,  47_000,  48_000, 2025),
        (13, "Balikpapan Kota", "Balikpapan",       "Kalimantan Timur",   72_000,  36_500,  35_500, 2025),
        (14, "Denpasar Selatan","Denpasar",         "Bali",              105_000,  52_000,  53_000, 2025),
        (15, "Jayapura Utara",  "Jayapura",         "Papua",              45_000,  23_000,  22_000, 2025),
    ]
    cur.executemany(
        "INSERT INTO penduduk VALUES (?,?,?,?,?,?,?,?)",
        penduduk_rows,
    )

    # ── GOVERNMENT: anggaran_daerah ────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS anggaran_daerah")
    cur.execute("""
        CREATE TABLE anggaran_daerah (
            id            INTEGER PRIMARY KEY,
            satuan_kerja  TEXT,
            program       TEXT,
            pagu          REAL,
            realisasi     REAL,
            triwulan      TEXT,
            tahun         INTEGER
        )
    """)
    anggaran_rows = [
        # TW3 2025 (latest complete quarter)
        (1,  "Dinas Kesehatan",        "Peningkatan Puskesmas",          15_000_000_000, 12_450_000_000, "TW3", 2025),
        (2,  "Dinas Pendidikan",       "Rehabilitasi Gedung Sekolah",    22_000_000_000, 19_800_000_000, "TW3", 2025),
        (3,  "Dinas PU",               "Perbaikan Jalan Kota",           35_000_000_000, 28_000_000_000, "TW3", 2025),
        (4,  "Dinas Sosial",           "Bantuan Sosial PSKS",            10_000_000_000,  9_500_000_000, "TW3", 2025),
        (5,  "Dinas Perhubungan",      "Pengadaan Bus TransJakarta",     80_000_000_000, 72_000_000_000, "TW3", 2025),
        (6,  "BPBD",                   "Mitigasi Banjir",                18_000_000_000, 11_000_000_000, "TW3", 2025),
        (7,  "Dinas Lingkungan Hidup", "Pengelolaan Sampah Terpadu",     12_000_000_000, 10_200_000_000, "TW3", 2025),
        (8,  "Dinas Perizinan",        "Digitalisasi OSS Daerah",         5_000_000_000,  4_750_000_000, "TW3", 2025),
        (9,  "Dinas Kesehatan",        "Vaksinasi dan Imunisasi",         8_000_000_000,  8_000_000_000, "TW3", 2025),
        (10, "Dinas Pendidikan",       "Beasiswa Siswa Berprestasi",      6_000_000_000,  5_400_000_000, "TW3", 2025),
        (11, "Dinas PU",               "Normalisasi Sungai Ciliwung",    28_000_000_000, 18_900_000_000, "TW3", 2025),
        (12, "Diskominfo",             "Smart City Infrastructure",       9_500_000_000,  8_800_000_000, "TW3", 2025),
        # TW2 2025
        (13, "Dinas Kesehatan",        "Peningkatan Puskesmas",          15_000_000_000,  7_200_000_000, "TW2", 2025),
        (14, "Dinas Pendidikan",       "Rehabilitasi Gedung Sekolah",    22_000_000_000,  9_900_000_000, "TW2", 2025),
        (15, "Dinas PU",               "Perbaikan Jalan Kota",           35_000_000_000, 14_500_000_000, "TW2", 2025),
        (16, "Dinas Sosial",           "Bantuan Sosial PSKS",            10_000_000_000,  4_800_000_000, "TW2", 2025),
        (17, "Dinas Perhubungan",      "Pengadaan Bus TransJakarta",     80_000_000_000, 32_000_000_000, "TW2", 2025),
        (18, "BPBD",                   "Mitigasi Banjir",                18_000_000_000,  5_200_000_000, "TW2", 2025),
        (19, "Dinas Lingkungan Hidup", "Pengelolaan Sampah Terpadu",     12_000_000_000,  5_800_000_000, "TW2", 2025),
        (20, "Dinas Perizinan",        "Digitalisasi OSS Daerah",         5_000_000_000,  2_300_000_000, "TW2", 2025),
        # TW1 2025
        (21, "Dinas Kesehatan",        "Peningkatan Puskesmas",          15_000_000_000,  2_100_000_000, "TW1", 2025),
        (22, "Dinas Pendidikan",       "Rehabilitasi Gedung Sekolah",    22_000_000_000,  2_800_000_000, "TW1", 2025),
        (23, "Dinas PU",               "Perbaikan Jalan Kota",           35_000_000_000,  3_500_000_000, "TW1", 2025),
        (24, "Dinas Sosial",           "Bantuan Sosial PSKS",            10_000_000_000,  2_500_000_000, "TW1", 2025),
        (25, "Dinas Perhubungan",      "Pengadaan Bus TransJakarta",     80_000_000_000,  8_000_000_000, "TW1", 2025),
        (26, "BPBD",                   "Mitigasi Banjir",                18_000_000_000,  1_400_000_000, "TW1", 2025),
    ]
    cur.executemany(
        "INSERT INTO anggaran_daerah VALUES (?,?,?,?,?,?,?)",
        anggaran_rows,
    )

    # ── GOVERNMENT: layanan_publik ─────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS layanan_publik")
    cur.execute("""
        CREATE TABLE layanan_publik (
            id                  INTEGER PRIMARY KEY,
            jenis_layanan       TEXT,
            satuan_kerja        TEXT,
            jumlah_permohonan   INTEGER,
            selesai_tepat_waktu INTEGER,
            kepuasan_pct        REAL,
            rata_waktu_hari     REAL,
            bulan               TEXT
        )
    """)
    layanan_rows = [
        # 2026-03
        (1,  "KTP Elektronik",   "Disdukcapil",     8500,  8200, 92.5,  2.1, "2026-03"),
        (2,  "Kartu Keluarga",   "Disdukcapil",     5200,  5180, 94.3,  0.8, "2026-03"),
        (3,  "Akta Kelahiran",   "Disdukcapil",     3100,  3090, 96.1,  0.9, "2026-03"),
        (4,  "IMB/PBG",          "Dinas PU",         420,   380, 78.5, 12.3, "2026-03"),
        (5,  "Izin Usaha (NIB)", "Dinas Perizinan", 2800,  2795, 98.2,  0.1, "2026-03"),
        (6,  "SKTM",             "Dinas Sosial",    1200,  1195, 95.8,  0.9, "2026-03"),
        (7,  "Legalisir Dokumen","Kecamatan",       6800,  6790, 91.0,  0.7, "2026-03"),
        (8,  "Izin Keramaian",   "Satpol PP",        180,   172, 82.3,  2.8, "2026-03"),
        (9,  "Paspor",           "Imigrasi",        2200,  2188, 97.5,  3.0, "2026-03"),
        (10, "BPJS Kesehatan",   "Dinkes",          4500,  4490, 96.8,  0.5, "2026-03"),
        # 2026-02
        (11, "KTP Elektronik",   "Disdukcapil",     7900,  7650, 90.1,  2.4, "2026-02"),
        (12, "Kartu Keluarga",   "Disdukcapil",     4800,  4770, 93.7,  0.9, "2026-02"),
        (13, "IMB/PBG",          "Dinas PU",         390,   340, 75.2, 13.1, "2026-02"),
        (14, "Izin Usaha (NIB)", "Dinas Perizinan", 2600,  2591, 97.8,  0.1, "2026-02"),
        (15, "Akta Kelahiran",   "Disdukcapil",     2900,  2890, 95.5,  1.0, "2026-02"),
        (16, "SKTM",             "Dinas Sosial",    1050,  1042, 94.9,  1.0, "2026-02"),
        (17, "Paspor",           "Imigrasi",        1980,  1968, 96.8,  3.2, "2026-02"),
        # 2026-01
        (18, "KTP Elektronik",   "Disdukcapil",     8100,  7820, 91.8,  2.2, "2026-01"),
        (19, "Kartu Keluarga",   "Disdukcapil",     5000,  4980, 94.1,  0.8, "2026-01"),
        (20, "IMB/PBG",          "Dinas PU",         405,   355, 76.4, 13.8, "2026-01"),
        (21, "Izin Usaha (NIB)", "Dinas Perizinan", 2450,  2440, 97.2,  0.1, "2026-01"),
        (22, "Akta Kelahiran",   "Disdukcapil",     3050,  3040, 96.3,  0.9, "2026-01"),
        (23, "Paspor",           "Imigrasi",        2050,  2035, 97.0,  3.1, "2026-01"),
    ]
    cur.executemany(
        "INSERT INTO layanan_publik VALUES (?,?,?,?,?,?,?,?)",
        layanan_rows,
    )

    conn.commit()
    conn.close()
    print(f"Demo database seeded successfully at: {DB_PATH}")
    print("Tables:")
    print("  Banking:    kredit_umkm (45 rows), nasabah (15), cabang (14)")
    print("  Telco:      pelanggan (20), penggunaan_data (30), jaringan (15)")
    print("  Government: penduduk (15), anggaran_daerah (26), layanan_publik (23)")


if __name__ == "__main__":
    seed()
