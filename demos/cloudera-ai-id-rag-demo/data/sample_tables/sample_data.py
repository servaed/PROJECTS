"""Shared data generator for demo datasets.

Uses a fixed random seed (42) so both the SQLite seeder and the Iceberg seeder
produce byte-for-byte identical data across runs and across environments.

Row-count targets (>= 1000 total):
  Banking:    msme_credit (540), customer (80), branch (25)
  Telco:      subscriber (80), data_usage (480), network (20)
  Government: resident (40), regional_budget (88), public_service (132)
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

# ── Banking: msme_credit ───────────────────────────────────────────────────────

# OJK credit quality tiers — kept in Indonesian as regulatory terminology
_CREDIT_QUALITY_POOL = (
    ["Lancar"] * 70 + ["DPK"] * 15 + ["Kurang Lancar"] * 10 + ["Macet"] * 5
)

_MSME_RANGES = {
    "Micro":  (100_000_000,   500_000_000),
    "Small":  (800_000_000, 5_000_000_000),
    "Medium": (5_000_000_000, 20_000_000_000),
}


def gen_msme_credit() -> list[tuple]:
    """15 cities x 3 segments x 12 months = 540 rows."""
    rows: list[tuple] = []
    customer_counter = 0
    for city in CITIES:
        for seg in ("Micro", "Small", "Medium"):
            lo, hi = _MSME_RANGES[seg]
            base = _RNG.randint(lo, hi)
            customer_id = (customer_counter % 80) + 1
            customer_counter += 1
            for month in MONTHS_12:
                raw = base * _RNG.uniform(0.95, 1.08)
                outstanding = max(float(lo), round(raw / 1_000_000) * 1_000_000)
                credit_quality = _RNG.choice(_CREDIT_QUALITY_POOL)
                rows.append((customer_id, city, seg, outstanding, credit_quality, month))
    return rows


# ── Banking: customer ──────────────────────────────────────────────────────────

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


def gen_customer() -> list[tuple]:
    """80 customer profiles."""
    rows: list[tuple] = []
    used: set[str] = set()
    for i in range(1, 81):
        segment = _RNG.choice(["Corporate", "MSME", "MSME"])
        city = _RNG.choice(CITIES)
        while True:
            name = f"{_RNG.choice(_COMPANY_TYPES)} {_RNG.choice(_COMPANY_CORES)} {_RNG.choice(_COMPANY_SUFFS)}"
            if name not in used:
                used.add(name)
                break
        total_exposure = (
            float(_RNG.randint(20_000_000_000, 120_000_000_000))
            if segment == "Corporate"
            else float(_RNG.randint(500_000_000, 8_000_000_000))
        )
        internal_rating = _RNG.choice(_RATINGS)
        onboard_date = date(2014, 1, 1) + timedelta(days=_RNG.randint(0, 3650))
        rows.append((i, name, segment, city, total_exposure, internal_rating, str(onboard_date)))
    return rows


# ── Banking: branch ────────────────────────────────────────────────────────────

def gen_branch() -> list[tuple]:
    """25 bank branches across Indonesia."""
    return [
        (1,  "Jakarta Pusat Branch",    "Jakarta",               "Jakarta",      1, 12500, 85_000_000_000.0,  88_200_000_000.0),
        (2,  "Jakarta Selatan Branch",  "Jakarta",               "Jakarta",      1, 10800, 75_000_000_000.0,  78_500_000_000.0),
        (3,  "Jakarta Utara Branch",    "Jakarta",               "Jakarta",      1,  8200, 55_000_000_000.0,  53_400_000_000.0),
        (4,  "Jakarta Timur Branch",    "Jakarta",               "Jakarta",      1,  7600, 48_000_000_000.0,  46_800_000_000.0),
        (5,  "Jakarta Barat Branch",    "Jakarta",               "Jakarta",      1,  6900, 42_000_000_000.0,  41_300_000_000.0),
        (6,  "Surabaya Main Branch",    "Jawa Timur",            "Surabaya",     1,  9200, 60_000_000_000.0,  62_100_000_000.0),
        (7,  "Surabaya Selatan Branch", "Jawa Timur",            "Surabaya",     1,  5400, 35_000_000_000.0,  33_800_000_000.0),
        (8,  "Bandung Main Branch",     "Jawa Barat",            "Bandung",      1,  7100, 42_000_000_000.0,  41_200_000_000.0),
        (9,  "Medan Main Branch",       "Sumatera Utara",        "Medan",        1,  6300, 38_000_000_000.0,  36_500_000_000.0),
        (10, "Makassar Main Branch",    "Sulawesi Selatan",      "Makassar",     1,  4800, 28_000_000_000.0,  27_400_000_000.0),
        (11, "Semarang Main Branch",    "Jawa Tengah",           "Semarang",     1,  5900, 35_000_000_000.0,  36_800_000_000.0),
        (12, "Yogyakarta Branch",       "DI Yogyakarta",         "Yogyakarta",   1,  4200, 22_000_000_000.0,  21_100_000_000.0),
        (13, "Palembang Branch",        "Sumatera Selatan",      "Palembang",    1,  3800, 20_000_000_000.0,  19_500_000_000.0),
        (14, "Balikpapan Branch",       "Kalimantan Timur",      "Balikpapan",   1,  3200, 18_000_000_000.0,  18_900_000_000.0),
        (15, "Denpasar Branch",         "Bali",                  "Denpasar",     1,  4500, 25_000_000_000.0,  24_600_000_000.0),
        (16, "Malang Branch",           "Jawa Timur",            "Malang",       1,  4100, 22_000_000_000.0,  21_500_000_000.0),
        (17, "Bekasi Branch",           "Jawa Barat",            "Bekasi",       1,  6800, 40_000_000_000.0,  38_900_000_000.0),
        (18, "Tangerang Branch",        "Banten",                "Tangerang",    1,  7200, 45_000_000_000.0,  43_200_000_000.0),
        (19, "Depok Branch",            "Jawa Barat",            "Depok",        1,  5600, 30_000_000_000.0,  29_100_000_000.0),
        (20, "Pekanbaru Branch",        "Riau",                  "Pekanbaru",    1,  3500, 19_000_000_000.0,  18_400_000_000.0),
        (21, "Pontianak Branch",        "Kalimantan Barat",      "Pontianak",    1,  2900, 15_000_000_000.0,  14_300_000_000.0),
        (22, "Manado Branch",           "Sulawesi Utara",        "Manado",       1,  2400, 12_000_000_000.0,  11_800_000_000.0),
        (23, "Padang Branch",           "Sumatera Barat",        "Padang",       1,  2700, 14_000_000_000.0,  13_500_000_000.0),
        (24, "Banjarmasin Branch",      "Kalimantan Selatan",    "Banjarmasin",  1,  2200, 11_000_000_000.0,  10_800_000_000.0),
        (25, "Mataram Branch",          "Nusa Tenggara Barat",   "Mataram",      1,  1600,  7_500_000_000.0,   7_100_000_000.0),
    ]


# ── Telco: subscriber ──────────────────────────────────────────────────────────

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
    "Prepaid":   ["Starter", "Basic", "Standard"],
    "Postpaid":  ["Standard", "Premium", "Unlimited"],
    "Corporate": ["Business", "Enterprise"],
}
_CORP_NAMES = [
    "PT Maju Digital", "PT Nusantara Retail", "PT Wisata Bahari", "PT Agro Nusantara",
    "CV Mitra Logistik", "CV Teknologi Muda", "PT Prima Solusi", "PT Indah Karya",
    "CV Berkah Mandiri", "PT Dinamika Global", "PT Sinar Harapan", "CV Maju Bersama",
    "PT Cipta Kreasi", "PT Mega Teknologi", "PT Anugerah Sejati",
]


def gen_subscriber() -> list[tuple]:
    """80 telecom subscribers (individual + corporate)."""
    rows: list[tuple] = []
    corp_idx = 0
    used_names: set[str] = set()
    for i in range(1, 81):
        sub_type = _RNG.choice(["Prepaid", "Prepaid", "Postpaid", "Postpaid", "Corporate"])
        if sub_type == "Corporate":
            name = _CORP_NAMES[corp_idx % len(_CORP_NAMES)]
            corp_idx += 1
            arpu = float(_RNG.randint(1_000_000, 10_000_000))
        else:
            while True:
                name = f"{_RNG.choice(_FIRST_NAMES)} {_RNG.choice(_LAST_NAMES)}"
                if name not in used_names:
                    used_names.add(name)
                    break
            arpu = (
                float(_RNG.randint(20_000, 100_000))
                if sub_type == "Prepaid"
                else float(_RNG.randint(100_000, 500_000))
            )
        plan = _RNG.choice(_PACKAGES[sub_type])
        city = _RNG.choice(CITIES)
        status = _RNG.choice(["Active"] * 4 + ["Inactive"])
        churn_risk_score = _RNG.randint(70, 99) if status == "Inactive" else _RNG.randint(5, 75)
        activation_date = date(2019, 1, 1) + timedelta(days=_RNG.randint(0, 1826))
        rows.append((i, name, sub_type, plan, city, status, str(activation_date), churn_risk_score, arpu))
    return rows


# ── Telco: data_usage ──────────────────────────────────────────────────────────

_QUOTA_BY_PLAN = {
    "Starter": 5.0, "Basic": 20.0, "Standard": 50.0,
    "Premium": 100.0, "Unlimited": 999.0,
    "Business": 200.0, "Enterprise": 500.0,
}


def gen_data_usage(subscriber_rows: list[tuple]) -> list[tuple]:
    """80 subscribers x 6 months = 480 rows."""
    rows: list[tuple] = []
    row_id = 1
    for sub in subscriber_rows:
        sub_id, _name, _sub_type, plan, *_rest = sub
        quota = _QUOTA_BY_PLAN.get(plan, 50.0)
        for month in MONTHS_6:
            usage = round(quota * _RNG.uniform(0.60, 1.25), 1)
            speed = round(_RNG.uniform(5.0, 55.0), 1)
            overage = 0.0
            if usage > quota:
                overage = float(round((usage - quota) * 5_000 / 1_000) * 1_000)
            rows.append((row_id, sub_id, month, quota, usage, speed, overage))
            row_id += 1
    return rows


# ── Telco: network ─────────────────────────────────────────────────────────────

def gen_network() -> list[tuple]:
    """20 network stations across Indonesia."""
    return [
        (1,  "Jakarta",               "Jakarta",      "5G",      320, 10000.0, 62.5, "Optimal"),
        (2,  "Jakarta",               "Jakarta",      "4G LTE",  580,  5800.0, 78.3, "Optimal"),
        (3,  "Jakarta",               "Jakarta",      "4.5G",    240,  3600.0, 70.2, "Optimal"),
        (4,  "Jawa Barat",            "Bandung",      "4G LTE",  210,  2100.0, 71.2, "Optimal"),
        (5,  "Jawa Barat",            "Bekasi",       "4G LTE",  198,  1980.0, 83.4, "High"),
        (6,  "Jawa Barat",            "Depok",        "4G LTE",  155,  1550.0, 68.9, "Optimal"),
        (7,  "Jawa Timur",            "Surabaya",     "4G LTE",  245,  2450.0, 85.6, "Critical"),
        (8,  "Jawa Timur",            "Malang",       "4G LTE",  112,  1120.0, 79.8, "High"),
        (9,  "Sumatera Utara",        "Medan",        "4G LTE",  180,  1800.0, 55.0, "Optimal"),
        (10, "Sulawesi Selatan",      "Makassar",     "4G LTE",  120,  1200.0, 48.2, "Optimal"),
        (11, "Jawa Tengah",           "Semarang",     "4G LTE",  155,  1550.0, 68.9, "Optimal"),
        (12, "Bali",                  "Denpasar",     "4G LTE",  130,  1300.0, 90.1, "Critical"),
        (13, "Kalimantan Timur",      "Balikpapan",   "4G LTE",   95,   950.0, 42.7, "Optimal"),
        (14, "DI Yogyakarta",         "Yogyakarta",   "4G LTE",   98,   980.0, 74.5, "Optimal"),
        (15, "Sumatera Selatan",      "Palembang",    "4G LTE",   88,   880.0, 61.3, "Optimal"),
        (16, "Papua",                 "Jayapura",     "4G LTE",   45,   450.0, 33.1, "Optimal"),
        (17, "Riau",                  "Pekanbaru",    "4G LTE",   82,   820.0, 57.4, "Optimal"),
        (18, "Banten",                "Tangerang",    "4G LTE",  185,  1850.0, 81.2, "High"),
        (19, "Sumatera Barat",        "Padang",       "4G LTE",   65,   650.0, 44.8, "Optimal"),
        (20, "Kalimantan Selatan",    "Banjarmasin",  "4G LTE",   72,   720.0, 52.1, "Optimal"),
    ]


# ── Government: resident ───────────────────────────────────────────────────────

_DISTRICT_DATA = [
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


def gen_resident() -> list[tuple]:
    """40 district population records."""
    rows: list[tuple] = []
    for i, (district, city, province) in enumerate(_DISTRICT_DATA, start=1):
        total = _RNG.randint(45_000, 250_000)
        male = int(total * _RNG.uniform(0.48, 0.52))
        female = total - male
        rows.append((i, district, city, province, total, male, female, 2025))
    return rows


# ── Government: regional_budget ────────────────────────────────────────────────

# Work unit names and program names kept in Indonesian (proper names of agencies)
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

_QUARTER_PCT = {
    "Q1": (0.08, 0.18),
    "Q2": (0.25, 0.38),
    "Q3": (0.50, 0.78),
    "Q4": (0.88, 0.99),
}


def gen_regional_budget() -> list[tuple]:
    """11 programs x 4 quarters x 2 years = 88 rows."""
    rows: list[tuple] = []
    row_id = 1
    for year in (2024, 2025):
        for quarter in ("Q1", "Q2", "Q3", "Q4"):
            for work_unit, program, budget_ceiling in _PROGRAMS:
                lo, hi = _QUARTER_PCT[quarter]
                realization = round(budget_ceiling * _RNG.uniform(lo, hi) / 1_000_000) * 1_000_000
                rows.append((row_id, work_unit, program, budget_ceiling, float(realization), quarter, year))
                row_id += 1
    return rows


# ── Government: public_service ─────────────────────────────────────────────────

# Service type names kept in Indonesian (proper names of government services)
_SERVICE_TYPES = [
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


def gen_public_service() -> list[tuple]:
    """11 services x 12 months = 132 rows."""
    rows: list[tuple] = []
    row_id = 1
    for service_type, agency, (lo, hi) in _SERVICE_TYPES:
        for month in MONTHS_12:
            application_count = _RNG.randint(lo, hi)
            on_time_count = int(application_count * _RNG.uniform(0.88, 0.99))
            satisfaction_pct = round(_RNG.uniform(82.0, 98.0), 1)
            if service_type == "IMB/PBG":
                avg_processing_days = round(_RNG.uniform(10.0, 16.0), 1)
            elif service_type == "Paspor":
                avg_processing_days = round(_RNG.uniform(2.5, 4.0), 1)
            else:
                avg_processing_days = round(_RNG.uniform(0.5, 2.5), 1)
            rows.append((row_id, service_type, agency, application_count, on_time_count,
                         satisfaction_pct, avg_processing_days, month))
            row_id += 1
    return rows


# ── Convenience: generate everything ─────────────────────────────────────────

def generate_all() -> dict[str, list[tuple]]:
    """Return all tables keyed by table name. Deterministic due to fixed RNG seed."""
    subscribers = gen_subscriber()
    return {
        "msme_credit":     gen_msme_credit(),
        "customer":        gen_customer(),
        "branch":          gen_branch(),
        "subscriber":      subscribers,
        "data_usage":      gen_data_usage(subscribers),
        "network":         gen_network(),
        "resident":        gen_resident(),
        "regional_budget": gen_regional_budget(),
        "public_service":  gen_public_service(),
    }


if __name__ == "__main__":
    data = generate_all()
    total = sum(len(v) for v in data.values())
    print(f"Total rows: {total}")
    for table, rows in data.items():
        print(f"  {table}: {len(rows)}")
