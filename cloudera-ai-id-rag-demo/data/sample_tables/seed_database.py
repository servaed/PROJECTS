"""Seed script — creates and populates the demo SQLite database with sample banking data.

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

    # ── kredit_umkm ────────────────────────────────────────────────────
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
        (1,  "Jakarta",    "Mikro",     450_000_000,  "Lancar",    "2026-03"),
        (2,  "Jakarta",    "Kecil",   2_500_000_000,  "Lancar",    "2026-03"),
        (3,  "Jakarta",    "Menengah",15_000_000_000, "DPK",       "2026-03"),
        (4,  "Surabaya",   "Mikro",     380_000_000,  "Lancar",    "2026-03"),
        (5,  "Surabaya",   "Kecil",   1_800_000_000,  "Lancar",    "2026-03"),
        (6,  "Bandung",    "Mikro",     200_000_000,  "Lancar",    "2026-03"),
        (7,  "Bandung",    "Kecil",     950_000_000,  "Kurang Lancar","2026-03"),
        (8,  "Medan",      "Mikro",     300_000_000,  "Lancar",    "2026-03"),
        (9,  "Makassar",   "Kecil",   1_200_000_000,  "Lancar",    "2026-03"),
        (10, "Jakarta",    "Mikro",     120_000_000,  "Macet",     "2026-03"),
        (11, "Jakarta",    "Kecil",   3_000_000_000,  "Lancar",    "2026-02"),
        (12, "Surabaya",   "Menengah",12_000_000_000, "Lancar",    "2026-02"),
        (13, "Jakarta",    "Kecil",   2_200_000_000,  "Lancar",    "2026-02"),
        (14, "Jakarta",    "Mikro",     410_000_000,  "DPK",       "2026-02"),
        (15, "Bandung",    "Kecil",   1_100_000_000,  "Lancar",    "2026-02"),
    ]
    cur.executemany(
        "INSERT INTO kredit_umkm (nasabah_id,wilayah,segmen,outstanding,kualitas,bulan) VALUES (?,?,?,?,?,?)",
        umkm_rows,
    )

    # ── nasabah ────────────────────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS nasabah")
    cur.execute("""
        CREATE TABLE nasabah (
            id          INTEGER PRIMARY KEY,
            nama        TEXT,
            segmen      TEXT,
            wilayah     TEXT,
            total_eksposur REAL
        )
    """)
    nasabah_rows = [
        (1,  "PT Maju Jaya Abadi",   "Korporasi", "Jakarta",   85_000_000_000),
        (2,  "CV Berkah Usaha",      "UMKM",      "Jakarta",    3_200_000_000),
        (3,  "UD Sumber Rejeki",     "UMKM",      "Surabaya",   1_900_000_000),
        (4,  "PT Nusantara Sejati",  "Korporasi", "Jakarta",   60_000_000_000),
        (5,  "Koperasi Tani Makmur", "UMKM",      "Bandung",    2_500_000_000),
        (6,  "PT Logistik Indonesia","Korporasi", "Surabaya",  42_000_000_000),
        (7,  "UD Karya Mandiri",     "UMKM",      "Medan",        980_000_000),
        (8,  "PT Energi Nusantara",  "Korporasi", "Jakarta",   95_000_000_000),
        (9,  "CV Mitra Dagang",      "UMKM",      "Makassar",   1_500_000_000),
        (10, "PT Tekstil Nusantara", "Korporasi", "Bandung",   38_000_000_000),
    ]
    cur.executemany(
        "INSERT INTO nasabah VALUES (?,?,?,?,?)",
        nasabah_rows,
    )

    # ── cabang ─────────────────────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS cabang")
    cur.execute("""
        CREATE TABLE cabang (
            id      INTEGER PRIMARY KEY,
            nama    TEXT,
            wilayah TEXT,
            kota    TEXT,
            aktif   INTEGER
        )
    """)
    cabang_rows = [
        (1,  "Cabang Jakarta Pusat",    "Jakarta",    "Jakarta",  1),
        (2,  "Cabang Jakarta Selatan",  "Jakarta",    "Jakarta",  1),
        (3,  "Cabang Jakarta Utara",    "Jakarta",    "Jakarta",  1),
        (4,  "Cabang Surabaya Utama",   "Jawa Timur", "Surabaya", 1),
        (5,  "Cabang Bandung Utama",    "Jawa Barat", "Bandung",  1),
        (6,  "Cabang Medan Utama",      "Sumatera",   "Medan",    1),
        (7,  "Cabang Makassar Utama",   "Sulawesi",   "Makassar", 1),
        (8,  "Cabang Semarang Utama",   "Jawa Tengah","Semarang", 1),
    ]
    cur.executemany(
        "INSERT INTO cabang VALUES (?,?,?,?,?)",
        cabang_rows,
    )

    conn.commit()
    conn.close()
    print(f"Demo database seeded successfully at: {DB_PATH}")


if __name__ == "__main__":
    seed()
