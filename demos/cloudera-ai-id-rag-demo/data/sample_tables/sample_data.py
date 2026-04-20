"""Shared data generator for demo datasets.

Uses a fixed random seed (42) so both the SQLite seeder and the Iceberg seeder
produce byte-for-byte identical data across runs and across environments.

Row-count targets (>= 1000 total):
  Banking:    kredit_umkm (540), nasabah (80), cabang (25)
  Telco:      pelanggan (80), penggunaan_data (480), jaringan (20)
  Government: penduduk (40), anggaran_daerah (88), layanan_publik (132)
  Grand total: 1485 rows
"""
from __future__ import annotations

import random
from datetime import date, timedelta

_RNG = random.Random(42)

# ── Geography ──────────────────────────────────────────────────────────────────

CITIES = [
    "Jakarta", "Surabaya", "Bandung", "Medan", "Makassar",
    "Semarang", "Yogyakarta", "Palembang", "Balikpapan", "Denpasar",
    "Malang", "Bekasi", "Tangerang", "Depok", "Pekanbaru",
]

MONTHS_12 = [
    "2026-03", "2026-02", "2026-01",
    "2025-12", "2025-11", "2025-10",
    "2025-09", "2025-08", "2025-07",
    "2025-06", "2025-05", "2025-04",
]

MONTHS_6 = MONTHS_12[:6]

# ── Banking: kredit_umkm ───────────────────────────────────────────────────────

_KUALITAS_POOL = (
    ["Lancar"] * 70 + ["DPK"] * 15 + ["Kurang Lancar"] * 10 + ["Macet"] * 5
)

_UMKM_RANGES = {
    "Mikro":    (100_000_000,   500_000_000),
    "Kecil":    (800_000_000, 5_000_000_000),
    "Menengah": (5_000_000_000, 20_000_000_000),
}


def gen_kredit_umkm() -> list[tuple]:
    """15 cities x 3 segments x 12 months = 540 rows."""
    rows: list[tuple] = []
    nasabah_counter = 0
    for city in CITIES:
        for seg in ("Mikro", "Kecil", "Menengah"):
            lo, hi = _UMKM_RANGES[seg]
            base = _RNG.randint(lo, hi)
            nasabah_id = (nasabah_counter % 80) + 1
            nasabah_counter += 1
            for month in MONTHS_12:
                raw = base * _RNG.uniform(0.95, 1.08)
                outstanding = max(float(lo), round(raw / 1_000_000) * 1_000_000)
                kualitas = _RNG.choice(_KUALITAS_POOL)
                rows.append((nasabah_id, city, seg, outstanding, kualitas, month))
    return rows


# ── Banking: nasabah ───────────────────────────────────────────────────────────

_COMPANY_TYPES = ["PT", "PT", "CV", "UD", "Koperasi", "Yayasan"]
_COMPANY_CORES = [
    "Maju", "Berkah", "Sejahtera", "Nusantara", "Mandiri", "Prima",
    "Sentosa", "Karya", "Abadi", "Makmur", "Jaya", "Sukses",
    "Indonesia", "Bersama", "Utama", "Global", "Digital", "Agro",
    "Logistik", "Energi", "Konstruksi", "Tekstil", "Farmasi", "Media",
    "Teknologi", "Industri", "Perdagangan", "Investasi", "Properti", "Retail",
    "Transportasi", "Kuliner", "Pariwisata", "Perikanan", "Pertanian",
]
_COMPANY_SUFFS = [
    "Jaya Abadi", "Sejahtera", "Mandiri", "Prima", "Indonesia",
    "Nusantara", "Sentosa", "Makmur", "Bersama", "Utama",
    "Digital", "Teknologi", "Global", "Asia", "Raya", "Perkasa", "Lestari",
]
_RATINGS = ["AA", "AA", "A", "A", "A-", "B+", "B+", "B", "B", "B-"]


def gen_nasabah() -> list[tuple]:
    """80 customer profiles."""
    rows: list[tuple] = []
    used: set[str] = set()
    for i in range(1, 81):
        seg = _RNG.choice(["Korporasi", "UMKM", "UMKM"])
        city = _RNG.choice(CITIES)
        while True:
            name = f"{_RNG.choice(_COMPANY_TYPES)} {_RNG.choice(_COMPANY_CORES)} {_RNG.choice(_COMPANY_SUFFS)}"
            if name not in used:
                used.add(name)
                break
        eksposur = (
            float(_RNG.randint(20_000_000_000, 120_000_000_000))
            if seg == "Korporasi"
            else float(_RNG.randint(500_000_000, 8_000_000_000))
        )
        rating = _RNG.choice(_RATINGS)
        onboard = date(2014, 1, 1) + timedelta(days=_RNG.randint(0, 3650))
        rows.append((i, name, seg, city, eksposur, rating, str(onboard)))
    return rows


# ── Banking: cabang ────────────────────────────────────────────────────────────

def gen_cabang() -> list[tuple]:
    """25 bank branches across Indonesia."""
    return [
        (1,  "Cabang Jakarta Pusat",      "Jakarta",               "Jakarta",      1, 12500, 85_000_000_000.0,  88_200_000_000.0),
        (2,  "Cabang Jakarta Selatan",    "Jakarta",               "Jakarta",      1, 10800, 75_000_000_000.0,  78_500_000_000.0),
        (3,  "Cabang Jakarta Utara",      "Jakarta",               "Jakarta",      1,  8200, 55_000_000_000.0,  53_400_000_000.0),
        (4,  "Cabang Jakarta Timur",      "Jakarta",               "Jakarta",      1,  7600, 48_000_000_000.0,  46_800_000_000.0),
        (5,  "Cabang Jakarta Barat",      "Jakarta",               "Jakarta",      1,  6900, 42_000_000_000.0,  41_300_000_000.0),
        (6,  "Cabang Surabaya Utama",     "Jawa Timur",            "Surabaya",     1,  9200, 60_000_000_000.0,  62_100_000_000.0),
        (7,  "Cabang Surabaya Selatan",   "Jawa Timur",            "Surabaya",     1,  5400, 35_000_000_000.0,  33_800_000_000.0),
        (8,  "Cabang Bandung Utama",      "Jawa Barat",            "Bandung",      1,  7100, 42_000_000_000.0,  41_200_000_000.0),
        (9,  "Cabang Medan Utama",        "Sumatera Utara",        "Medan",        1,  6300, 38_000_000_000.0,  36_500_000_000.0),
        (10, "Cabang Makassar Utama",     "Sulawesi Selatan",      "Makassar",     1,  4800, 28_000_000_000.0,  27_400_000_000.0),
        (11, "Cabang Semarang Utama",     "Jawa Tengah",           "Semarang",     1,  5900, 35_000_000_000.0,  36_800_000_000.0),
        (12, "Cabang Yogyakarta",         "DI Yogyakarta",         "Yogyakarta",   1,  4200, 22_000_000_000.0,  21_100_000_000.0),
        (13, "Cabang Palembang",          "Sumatera Selatan",      "Palembang",    1,  3800, 20_000_000_000.0,  19_500_000_000.0),
        (14, "Cabang Balikpapan",         "Kalimantan Timur",      "Balikpapan",   1,  3200, 18_000_000_000.0,  18_900_000_000.0),
        (15, "Cabang Denpasar",           "Bali",                  "Denpasar",     1,  4500, 25_000_000_000.0,  24_600_000_000.0),
        (16, "Cabang Malang",             "Jawa Timur",            "Malang",       1,  4100, 22_000_000_000.0,  21_500_000_000.0),
        (17, "Cabang Bekasi",             "Jawa Barat",            "Bekasi",       1,  6800, 40_000_000_000.0,  38_900_000_000.0),
        (18, "Cabang Tangerang",          "Banten",                "Tangerang",    1,  7200, 45_000_000_000.0,  43_200_000_000.0),
        (19, "Cabang Depok",              "Jawa Barat",            "Depok",        1,  5600, 30_000_000_000.0,  29_100_000_000.0),
        (20, "Cabang Pekanbaru",          "Riau",                  "Pekanbaru",    1,  3500, 19_000_000_000.0,  18_400_000_000.0),
        (21, "Cabang Pontianak",          "Kalimantan Barat",      "Pontianak",    1,  2900, 15_000_000_000.0,  14_300_000_000.0),
        (22, "Cabang Manado",             "Sulawesi Utara",        "Manado",       1,  2400, 12_000_000_000.0,  11_800_000_000.0),
        (23, "Cabang Padang",             "Sumatera Barat",        "Padang",       1,  2700, 14_000_000_000.0,  13_500_000_000.0),
        (24, "Cabang Banjarmasin",        "Kalimantan Selatan",    "Banjarmasin",  1,  2200, 11_000_000_000.0,  10_800_000_000.0),
        (25, "Cabang Mataram",            "Nusa Tenggara Barat",   "Mataram",      1,  1600,  7_500_000_000.0,   7_100_000_000.0),
    ]


# ── Telco: pelanggan ───────────────────────────────────────────────────────────

_FIRST_NAMES = [
    "Budi", "Siti", "Ahmad", "Dewi", "Rudi", "Rina", "Hendra", "Yuni", "Fahri", "Maya",
    "Dani", "Lena", "Bagas", "Nisa", "Agus", "Sri", "Eko", "Wulan", "Rizal", "Fitri",
    "Joko", "Indah", "Wahyu", "Ayu", "Dedi", "Ratna", "Irwan", "Suci", "Guntur", "Mega",
    "Fajar", "Reni", "Hadi", "Tari", "Arif", "Sari", "Toni", "Putri", "Yogi", "Laras",
]
_LAST_NAMES = [
    "Santoso", "Rahayu", "Fauzi", "Lestari", "Hermawan", "Wijaya", "Gunawan", "Pratiwi",
    "Kusuma", "Indah", "Prasetyo", "Marlina", "Purnomo", "Amalia", "Setiawan", "Anggraini",
    "Hidayat", "Kurniawan", "Susanto", "Wibowo", "Nugroho", "Hartono", "Saputra", "Dewi",
    "Firmansyah", "Utami", "Mahendra", "Saragih", "Situmorang", "Manurung",
]
_PACKAGES = {
    "Prabayar":   ["Starter", "Basic", "Standard"],
    "Pascabayar": ["Standard", "Premium", "Unlimited"],
    "Korporasi":  ["Business", "Enterprise"],
}
_CORP_NAMES = [
    "PT Maju Digital", "PT Nusantara Retail", "PT Wisata Bahari", "PT Agro Nusantara",
    "CV Mitra Logistik", "CV Teknologi Muda", "PT Prima Solusi", "PT Indah Karya",
    "CV Berkah Mandiri", "PT Dinamika Global", "PT Sinar Harapan", "CV Maju Bersama",
    "PT Cipta Kreasi", "PT Mega Teknologi", "PT Anugerah Sejati",
]


def gen_pelanggan() -> list[tuple]:
    """80 telecom customers (individual + corporate)."""
    rows: list[tuple] = []
    corp_idx = 0
    used_names: set[str] = set()
    for i in range(1, 81):
        tipe = _RNG.choice(["Prabayar", "Prabayar", "Pascabayar", "Pascabayar", "Korporasi"])
        if tipe == "Korporasi":
            nama = _CORP_NAMES[corp_idx % len(_CORP_NAMES)]
            corp_idx += 1
            arpu = float(_RNG.randint(1_000_000, 10_000_000))
        else:
            while True:
                nama = f"{_RNG.choice(_FIRST_NAMES)} {_RNG.choice(_LAST_NAMES)}"
                if nama not in used_names:
                    used_names.add(nama)
                    break
            arpu = (
                float(_RNG.randint(20_000, 100_000))
                if tipe == "Prabayar"
                else float(_RNG.randint(100_000, 500_000))
            )
        paket = _RNG.choice(_PACKAGES[tipe])
        city = _RNG.choice(CITIES)
        status = _RNG.choice(["Aktif"] * 4 + ["Tidak Aktif"])
        churn = _RNG.randint(70, 99) if status == "Tidak Aktif" else _RNG.randint(5, 75)
        aktivasi = date(2019, 1, 1) + timedelta(days=_RNG.randint(0, 1826))
        rows.append((i, nama, tipe, paket, city, status, str(aktivasi), churn, arpu))
    return rows


# ── Telco: penggunaan_data ─────────────────────────────────────────────────────

_QUOTA_BY_PAKET = {
    "Starter": 5.0, "Basic": 20.0, "Standard": 50.0,
    "Premium": 100.0, "Unlimited": 999.0,
    "Business": 200.0, "Enterprise": 500.0,
}


def gen_penggunaan_data(pelanggan_rows: list[tuple]) -> list[tuple]:
    """80 customers x 6 months = 480 rows."""
    rows: list[tuple] = []
    row_id = 1
    for plg in pelanggan_rows:
        plg_id, _name, _tipe, paket, *_rest = plg
        quota = _QUOTA_BY_PAKET.get(paket, 50.0)
        for month in MONTHS_6:
            usage = round(quota * _RNG.uniform(0.60, 1.25), 1)
            speed = round(_RNG.uniform(5.0, 55.0), 1)
            biaya = 0.0
            if usage > quota:
                biaya = float(round((usage - quota) * 5_000 / 1_000) * 1_000)
            rows.append((row_id, plg_id, month, quota, usage, speed, biaya))
            row_id += 1
    return rows


# ── Telco: jaringan ────────────────────────────────────────────────────────────

def gen_jaringan() -> list[tuple]:
    """20 network stations across Indonesia."""
    return [
        (1,  "Jakarta",               "Jakarta",      "5G",      320, 10000.0, 62.5, "Optimal"),
        (2,  "Jakarta",               "Jakarta",      "4G LTE",  580,  5800.0, 78.3, "Optimal"),
        (3,  "Jakarta",               "Jakarta",      "4.5G",    240,  3600.0, 70.2, "Optimal"),
        (4,  "Jawa Barat",            "Bandung",      "4G LTE",  210,  2100.0, 71.2, "Optimal"),
        (5,  "Jawa Barat",            "Bekasi",       "4G LTE",  198,  1980.0, 83.4, "Tinggi"),
        (6,  "Jawa Barat",            "Depok",        "4G LTE",  155,  1550.0, 68.9, "Optimal"),
        (7,  "Jawa Timur",            "Surabaya",     "4G LTE",  245,  2450.0, 85.6, "Kritis"),
        (8,  "Jawa Timur",            "Malang",       "4G LTE",  112,  1120.0, 79.8, "Tinggi"),
        (9,  "Sumatera Utara",        "Medan",        "4G LTE",  180,  1800.0, 55.0, "Optimal"),
        (10, "Sulawesi Selatan",      "Makassar",     "4G LTE",  120,  1200.0, 48.2, "Optimal"),
        (11, "Jawa Tengah",           "Semarang",     "4G LTE",  155,  1550.0, 68.9, "Optimal"),
        (12, "Bali",                  "Denpasar",     "4G LTE",  130,  1300.0, 90.1, "Kritis"),
        (13, "Kalimantan Timur",      "Balikpapan",   "4G LTE",   95,   950.0, 42.7, "Optimal"),
        (14, "DI Yogyakarta",         "Yogyakarta",   "4G LTE",   98,   980.0, 74.5, "Optimal"),
        (15, "Sumatera Selatan",      "Palembang",    "4G LTE",   88,   880.0, 61.3, "Optimal"),
        (16, "Papua",                 "Jayapura",     "4G LTE",   45,   450.0, 33.1, "Optimal"),
        (17, "Riau",                  "Pekanbaru",    "4G LTE",   82,   820.0, 57.4, "Optimal"),
        (18, "Banten",                "Tangerang",    "4G LTE",  185,  1850.0, 81.2, "Tinggi"),
        (19, "Sumatera Barat",        "Padang",       "4G LTE",   65,   650.0, 44.8, "Optimal"),
        (20, "Kalimantan Selatan",    "Banjarmasin",  "4G LTE",   72,   720.0, 52.1, "Optimal"),
    ]


# ── Government: penduduk ───────────────────────────────────────────────────────

_KECAMATAN_DATA = [
    ("Gambir",           "Jakarta Pusat",    "DKI Jakarta"),
    ("Tanah Abang",      "Jakarta Pusat",    "DKI Jakarta"),
    ("Kebayoran Baru",   "Jakarta Selatan",  "DKI Jakarta"),
    ("Penjaringan",      "Jakarta Utara",    "DKI Jakarta"),
    ("Cempaka Putih",    "Jakarta Pusat",    "DKI Jakarta"),
    ("Cilincing",        "Jakarta Utara",    "DKI Jakarta"),
    ("Matraman",         "Jakarta Timur",    "DKI Jakarta"),
    ("Kebon Jeruk",      "Jakarta Barat",    "DKI Jakarta"),
    ("Tegalsari",        "Surabaya",         "Jawa Timur"),
    ("Gubeng",           "Surabaya",         "Jawa Timur"),
    ("Sawahan",          "Surabaya",         "Jawa Timur"),
    ("Tambaksari",       "Surabaya",         "Jawa Timur"),
    ("Coblong",          "Bandung",          "Jawa Barat"),
    ("Cicendo",          "Bandung",          "Jawa Barat"),
    ("Babakan Ciparay",  "Bandung",          "Jawa Barat"),
    ("Medan Baru",       "Medan",            "Sumatera Utara"),
    ("Medan Kota",       "Medan",            "Sumatera Utara"),
    ("Rappocini",        "Makassar",         "Sulawesi Selatan"),
    ("Tamalate",         "Makassar",         "Sulawesi Selatan"),
    ("Semarang Tengah",  "Semarang",         "Jawa Tengah"),
    ("Semarang Barat",   "Semarang",         "Jawa Tengah"),
    ("Umbulharjo",       "Yogyakarta",       "DI Yogyakarta"),
    ("Mergangsan",       "Yogyakarta",       "DI Yogyakarta"),
    ("Ilir Barat I",     "Palembang",        "Sumatera Selatan"),
    ("Seberang Ulu I",   "Palembang",        "Sumatera Selatan"),
    ("Balikpapan Kota",  "Balikpapan",       "Kalimantan Timur"),
    ("Balikpapan Utara", "Balikpapan",       "Kalimantan Timur"),
    ("Denpasar Selatan", "Denpasar",         "Bali"),
    ("Denpasar Timur",   "Denpasar",         "Bali"),
    ("Jayapura Utara",   "Jayapura",         "Papua"),
    ("Malang Kota",      "Malang",           "Jawa Timur"),
    ("Lowokwaru",        "Malang",           "Jawa Timur"),
    ("Bekasi Utara",     "Bekasi",           "Jawa Barat"),
    ("Bekasi Selatan",   "Bekasi",           "Jawa Barat"),
    ("Tangerang Kota",   "Tangerang",        "Banten"),
    ("Karang Tengah",    "Tangerang",        "Banten"),
    ("Pancoran Mas",     "Depok",            "Jawa Barat"),
    ("Sukmajaya",        "Depok",            "Jawa Barat"),
    ("Tampan",           "Pekanbaru",        "Riau"),
    ("Sail",             "Pekanbaru",        "Riau"),
]


def gen_penduduk() -> list[tuple]:
    """40 district population records."""
    rows: list[tuple] = []
    for i, (kecamatan, kabupaten, provinsi) in enumerate(_KECAMATAN_DATA, start=1):
        total = _RNG.randint(45_000, 250_000)
        laki = int(total * _RNG.uniform(0.48, 0.52))
        perempuan = total - laki
        rows.append((i, kecamatan, kabupaten, provinsi, total, laki, perempuan, 2025))
    return rows


# ── Government: anggaran_daerah ────────────────────────────────────────────────

_PROGRAMS = [
    ("Dinas Kesehatan",        "Peningkatan Puskesmas",          15_000_000_000.0),
    ("Dinas Pendidikan",       "Rehabilitasi Gedung Sekolah",    22_000_000_000.0),
    ("Dinas PU",               "Perbaikan Jalan Kota",           35_000_000_000.0),
    ("Dinas Sosial",           "Bantuan Sosial PSKS",            10_000_000_000.0),
    ("Dinas Perhubungan",      "Pengadaan Bus TransJakarta",     80_000_000_000.0),
    ("BPBD",                   "Mitigasi Banjir",                18_000_000_000.0),
    ("Dinas Lingkungan Hidup", "Pengelolaan Sampah Terpadu",     12_000_000_000.0),
    ("Dinas Perizinan",        "Digitalisasi OSS Daerah",         5_000_000_000.0),
    ("Dinas Kesehatan",        "Vaksinasi dan Imunisasi",         8_000_000_000.0),
    ("Dinas Pendidikan",       "Beasiswa Siswa Berprestasi",      6_000_000_000.0),
    ("Diskominfo",             "Smart City Infrastructure",       9_500_000_000.0),
]

# Typical quarterly absorption rate ranges (cumulative)
_TW_PCT = {
    "TW1": (0.08, 0.18),
    "TW2": (0.25, 0.38),
    "TW3": (0.50, 0.78),
    "TW4": (0.88, 0.99),
}


def gen_anggaran_daerah() -> list[tuple]:
    """11 programs x 4 quarters x 2 years = 88 rows."""
    rows: list[tuple] = []
    row_id = 1
    for year in (2024, 2025):
        for tw in ("TW1", "TW2", "TW3", "TW4"):
            for satuan_kerja, program, pagu in _PROGRAMS:
                lo, hi = _TW_PCT[tw]
                realisasi = round(pagu * _RNG.uniform(lo, hi) / 1_000_000) * 1_000_000
                rows.append((row_id, satuan_kerja, program, pagu, float(realisasi), tw, year))
                row_id += 1
    return rows


# ── Government: layanan_publik ─────────────────────────────────────────────────

_LAYANAN_TYPES = [
    ("KTP Elektronik",    "Disdukcapil",    (7500, 9500)),
    ("Kartu Keluarga",    "Disdukcapil",    (4500, 5500)),
    ("Akta Kelahiran",    "Disdukcapil",    (2800, 3500)),
    ("IMB/PBG",           "Dinas PU",       (350,   500)),
    ("Izin Usaha (NIB)",  "Dinas Perizinan",(2200, 3000)),
    ("SKTM",              "Dinas Sosial",   (900,  1400)),
    ("Legalisir Dokumen", "Kecamatan",      (5000, 8000)),
    ("Izin Keramaian",    "Satpol PP",      (150,   250)),
    ("Paspor",            "Imigrasi",       (1800, 2500)),
    ("BPJS Kesehatan",    "Dinkes",         (3500, 5000)),
    ("SIM Baru",          "Polri",          (1200, 2000)),
]


def gen_layanan_publik() -> list[tuple]:
    """11 services x 12 months = 132 rows."""
    rows: list[tuple] = []
    row_id = 1
    for jenis, satuan_kerja, (lo, hi) in _LAYANAN_TYPES:
        for month in MONTHS_12:
            permohonan = _RNG.randint(lo, hi)
            selesai = int(permohonan * _RNG.uniform(0.88, 0.99))
            kepuasan = round(_RNG.uniform(82.0, 98.0), 1)
            if jenis == "IMB/PBG":
                rata_waktu = round(_RNG.uniform(10.0, 16.0), 1)
            elif jenis == "Paspor":
                rata_waktu = round(_RNG.uniform(2.5, 4.0), 1)
            else:
                rata_waktu = round(_RNG.uniform(0.5, 2.5), 1)
            rows.append((row_id, jenis, satuan_kerja, permohonan, selesai, kepuasan, rata_waktu, month))
            row_id += 1
    return rows


# ── Convenience: generate everything ─────────────────────────────────────────

def generate_all() -> dict[str, list[tuple]]:
    """Return all tables keyed by table name. Deterministic due to fixed RNG seed."""
    pelanggan = gen_pelanggan()
    return {
        "kredit_umkm":      gen_kredit_umkm(),
        "nasabah":          gen_nasabah(),
        "cabang":           gen_cabang(),
        "pelanggan":        pelanggan,
        "penggunaan_data":  gen_penggunaan_data(pelanggan),
        "jaringan":         gen_jaringan(),
        "penduduk":         gen_penduduk(),
        "anggaran_daerah":  gen_anggaran_daerah(),
        "layanan_publik":   gen_layanan_publik(),
    }


if __name__ == "__main__":
    data = generate_all()
    total = sum(len(v) for v in data.values())
    print(f"Total rows: {total}")
    for table, rows in data.items():
        print(f"  {table}: {len(rows)}")
