"""Shared data generator for demo datasets.

Uses a fixed random seed (42) so both the DuckDB seeder and the Iceberg seeder
produce byte-for-byte identical data across runs and across environments.

Row-count targets:
  Banking:    msme_credit (972), customer (80), branch (25), loan_application (200)
  Telco:      subscriber (80), data_usage (480), network (27), network_incident (162)
  Government: resident (40), regional_budget (88), public_service (132)
  Grand total: 2,286 rows
"""
from __future__ import annotations

import random
from datetime import date, timedelta

_RNG = random.Random(42)

# ── City metadata: 27 cities across all Indonesian islands ─────────────────

_CITY_META: dict[str, dict] = {
    # Java
    "Jakarta":     {"province": "DKI Jakarta",           "lat": -6.2088,  "lon": 106.8456},
    "Surabaya":    {"province": "Jawa Timur",             "lat": -7.2575,  "lon": 112.7521},
    "Bandung":     {"province": "Jawa Barat",             "lat": -6.9175,  "lon": 107.6191},
    "Semarang":    {"province": "Jawa Tengah",            "lat": -6.9932,  "lon": 110.4203},
    "Yogyakarta":  {"province": "DI Yogyakarta",          "lat": -7.7956,  "lon": 110.3695},
    "Malang":      {"province": "Jawa Timur",             "lat": -7.9797,  "lon": 112.6304},
    "Bekasi":      {"province": "Jawa Barat",             "lat": -6.2349,  "lon": 106.9896},
    "Tangerang":   {"province": "Banten",                 "lat": -6.1783,  "lon": 106.6319},
    "Depok":       {"province": "Jawa Barat",             "lat": -6.3744,  "lon": 106.8227},
    # Sumatra
    "Medan":       {"province": "Sumatera Utara",         "lat": 3.5952,   "lon": 98.6722},
    "Palembang":   {"province": "Sumatera Selatan",       "lat": -2.9761,  "lon": 104.7754},
    "Pekanbaru":   {"province": "Riau",                   "lat": 0.5335,   "lon": 101.4474},
    "Padang":      {"province": "Sumatera Barat",         "lat": -0.9471,  "lon": 100.4172},
    "Batam":       {"province": "Kepulauan Riau",         "lat": 1.0457,   "lon": 104.0305},
    "Banda Aceh":  {"province": "Aceh",                   "lat": 5.5483,   "lon": 95.3238},
    # Kalimantan
    "Balikpapan":  {"province": "Kalimantan Timur",       "lat": -1.2675,  "lon": 116.8289},
    "Pontianak":   {"province": "Kalimantan Barat",       "lat": -0.0263,  "lon": 109.3425},
    "Banjarmasin": {"province": "Kalimantan Selatan",     "lat": -3.3186,  "lon": 114.5944},
    "Samarinda":   {"province": "Kalimantan Timur",       "lat": -0.5022,  "lon": 117.1536},
    # Sulawesi
    "Makassar":    {"province": "Sulawesi Selatan",       "lat": -5.1477,  "lon": 119.4327},
    "Manado":      {"province": "Sulawesi Utara",         "lat": 1.4748,   "lon": 124.8421},
    "Kendari":     {"province": "Sulawesi Tenggara",      "lat": -3.9985,  "lon": 122.5127},
    # Bali & Nusa Tenggara
    "Denpasar":    {"province": "Bali",                   "lat": -8.6705,  "lon": 115.2126},
    "Mataram":     {"province": "Nusa Tenggara Barat",    "lat": -8.5833,  "lon": 116.1167},
    "Kupang":      {"province": "Nusa Tenggara Timur",    "lat": -10.1771, "lon": 123.6070},
    # Maluku & Papua
    "Ambon":       {"province": "Maluku",                 "lat": -3.6954,  "lon": 128.1814},
    "Jayapura":    {"province": "Papua",                  "lat": -2.5337,  "lon": 140.7180},
}

CITIES = list(_CITY_META.keys())  # 27 cities spanning all major islands

MONTHS_12 = [
    "2026-03", "2026-02", "2026-01",
    "2025-12", "2025-11", "2025-10",
    "2025-09", "2025-08", "2025-07",
    "2025-06", "2025-05", "2025-04",
]

MONTHS_8  = MONTHS_12[:8]
MONTHS_6  = MONTHS_12[:6]

# ── NPL risk tiers by city ─────────────────────────────────────────────────
# Each tier drives both credit quality pools AND branch NPL amounts

_NPL_TIER: dict[str, str] = {
    # Tier 1 — Major Java metropolis: 3-6% NPL
    "Jakarta": "low", "Surabaya": "low", "Bandung": "low", "Semarang": "low",
    "Yogyakarta": "low", "Malang": "low", "Bekasi": "low",
    "Tangerang": "low", "Depok": "low", "Denpasar": "low",
    # Tier 2 — Sumatra & Kalimantan: 7-12% NPL
    "Medan": "mid", "Palembang": "mid", "Pekanbaru": "mid", "Padang": "mid",
    "Batam": "mid", "Balikpapan": "mid", "Pontianak": "mid",
    "Banjarmasin": "mid", "Samarinda": "mid", "Makassar": "mid",
    # Tier 3 — Outer islands: 13-22% NPL
    "Banda Aceh": "high", "Manado": "high", "Kendari": "high",
    "Mataram": "high", "Kupang": "high", "Ambon": "high", "Jayapura": "high",
}

_NPL_RANGES = {"low": (0.03, 0.06), "mid": (0.07, 0.12), "high": (0.13, 0.22)}

_CREDIT_QUALITY_POOLS: dict[str, list[str]] = {
    "low":  ["Lancar"] * 78 + ["DPK"] * 13 + ["Kurang Lancar"] * 6 + ["Macet"] * 3,
    "mid":  ["Lancar"] * 68 + ["DPK"] * 17 + ["Kurang Lancar"] * 10 + ["Macet"] * 5,
    "high": ["Lancar"] * 55 + ["DPK"] * 22 + ["Kurang Lancar"] * 15 + ["Macet"] * 8,
}

_MSME_RANGES = {
    "Micro":  (100_000_000,   500_000_000),
    "Small":  (800_000_000, 5_000_000_000),
    "Medium": (5_000_000_000, 20_000_000_000),
}

_CITY_SCALE: dict[str, float] = {
    "Jakarta": 3.2, "Surabaya": 2.4, "Bandung": 1.8, "Bekasi": 1.6, "Tangerang": 1.5,
    "Semarang": 1.4, "Medan": 1.3, "Depok": 1.2, "Malang": 1.1, "Palembang": 1.0,
    "Makassar": 0.95, "Yogyakarta": 0.9, "Pekanbaru": 0.85, "Balikpapan": 0.8,
    "Denpasar": 0.9, "Padang": 0.7, "Batam": 0.75, "Pontianak": 0.65,
    "Banjarmasin": 0.6, "Samarinda": 0.6, "Manado": 0.55, "Mataram": 0.5,
    "Kendari": 0.4, "Kupang": 0.38, "Banda Aceh": 0.45, "Ambon": 0.42, "Jayapura": 0.4,
}

# ── Banking: msme_credit ───────────────────────────────────────────────────

def gen_msme_credit() -> list[tuple]:
    """27 cities x 3 segments x 12 months = 972 rows."""
    rows: list[tuple] = []
    customer_counter = 0
    for city in CITIES:
        province = _CITY_META[city]["province"]
        scale    = _CITY_SCALE.get(city, 1.0)
        pool     = _CREDIT_QUALITY_POOLS[_NPL_TIER[city]]
        for seg in ("Micro", "Small", "Medium"):
            lo, hi = _MSME_RANGES[seg]
            base = int(_RNG.randint(lo, hi) * scale)
            base = max(lo, min(hi, base))
            customer_id = (customer_counter % 80) + 1
            customer_counter += 1
            for month in MONTHS_12:
                raw = base * _RNG.uniform(0.93, 1.09)
                outstanding = max(float(lo), round(raw / 1_000_000) * 1_000_000)
                credit_quality = _RNG.choice(pool)
                rows.append((customer_id, city, province, seg, outstanding, credit_quality, month))
    return rows


# ── Banking: customer ──────────────────────────────────────────────────────

_COMPANY_TYPES  = ["PT", "PT", "CV", "UD", "Koperasi", "Yayasan"]
_COMPANY_CORES  = [
    "Maju", "Berkah", "Sejahtera", "Nusantara", "Mandiri", "Prima",
    "Sentosa", "Karya", "Abadi", "Makmur", "Jaya", "Sukses",
    "Indonesia", "Bersama", "Utama", "Global", "Digital", "Agro",
    "Logistik", "Energi", "Konstruksi", "Tekstil", "Farmasi", "Media",
    "Teknologi", "Industri", "Perdagangan", "Investasi", "Properti", "Retail",
    "Transportasi", "Kuliner", "Pariwisata", "Perikanan", "Pertanian",
]
_COMPANY_SUFFS  = [
    "Jaya Abadi", "Sejahtera", "Mandiri", "Prima", "Indonesia",
    "Nusantara", "Sentosa", "Makmur", "Bersama", "Utama",
    "Digital", "Teknologi", "Global", "Asia", "Raya", "Perkasa", "Lestari",
]
_RATINGS        = ["AA", "AA", "A", "A", "A-", "B+", "B+", "B", "B", "B-"]
_INDUSTRIES     = [
    "Manufacturing", "Retail & Trade", "Agriculture", "Construction",
    "Food & Beverage", "Logistics", "Healthcare", "Hospitality",
    "Technology", "Textiles", "Fishery", "Property",
]


def gen_customer() -> list[tuple]:
    """80 customer profiles."""
    rows: list[tuple] = []
    used: set[str] = set()
    for i in range(1, 81):
        segment = _RNG.choice(["Corporate", "MSME", "MSME"])
        city    = _RNG.choice(CITIES)
        industry = _RNG.choice(_INDUSTRIES)
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
        annual_revenue = round(total_exposure * _RNG.uniform(1.5, 4.0) / 1_000_000) * 1_000_000
        dsr = round(_RNG.uniform(0.18, 0.62), 2)   # debt service ratio 18-62%
        internal_rating = _RNG.choice(_RATINGS)
        onboard_date = date(2014, 1, 1) + timedelta(days=_RNG.randint(0, 3650))
        rows.append((i, name, segment, city, industry, total_exposure,
                     float(annual_revenue), dsr, internal_rating, str(onboard_date)))
    return rows


# ── Banking: branch ────────────────────────────────────────────────────────

def gen_branch() -> list[tuple]:
    """25 bank branches with NPL amount, deposit balance, and geo coordinates."""
    _base = [
        (1,  "Jakarta Pusat Branch",    "DKI Jakarta",        "Jakarta",      1, 12500, 85_000_000_000.0,  88_200_000_000.0),
        (2,  "Jakarta Selatan Branch",  "DKI Jakarta",        "Jakarta",      1, 10800, 75_000_000_000.0,  78_500_000_000.0),
        (3,  "Jakarta Utara Branch",    "DKI Jakarta",        "Jakarta",      1,  8200, 55_000_000_000.0,  53_400_000_000.0),
        (4,  "Jakarta Timur Branch",    "DKI Jakarta",        "Jakarta",      1,  7600, 48_000_000_000.0,  46_800_000_000.0),
        (5,  "Jakarta Barat Branch",    "DKI Jakarta",        "Jakarta",      1,  6900, 42_000_000_000.0,  41_300_000_000.0),
        (6,  "Surabaya Main Branch",    "Jawa Timur",         "Surabaya",     1,  9200, 60_000_000_000.0,  62_100_000_000.0),
        (7,  "Surabaya Selatan Branch", "Jawa Timur",         "Surabaya",     1,  5400, 35_000_000_000.0,  33_800_000_000.0),
        (8,  "Bandung Main Branch",     "Jawa Barat",         "Bandung",      1,  7100, 42_000_000_000.0,  41_200_000_000.0),
        (9,  "Medan Main Branch",       "Sumatera Utara",     "Medan",        1,  6300, 38_000_000_000.0,  36_500_000_000.0),
        (10, "Makassar Main Branch",    "Sulawesi Selatan",   "Makassar",     1,  4800, 28_000_000_000.0,  27_400_000_000.0),
        (11, "Semarang Main Branch",    "Jawa Tengah",        "Semarang",     1,  5900, 35_000_000_000.0,  36_800_000_000.0),
        (12, "Yogyakarta Branch",       "DI Yogyakarta",      "Yogyakarta",   1,  4200, 22_000_000_000.0,  21_100_000_000.0),
        (13, "Palembang Branch",        "Sumatera Selatan",   "Palembang",    1,  3800, 20_000_000_000.0,  19_500_000_000.0),
        (14, "Balikpapan Branch",       "Kalimantan Timur",   "Balikpapan",   1,  3200, 18_000_000_000.0,  18_900_000_000.0),
        (15, "Denpasar Branch",         "Bali",               "Denpasar",     1,  4500, 25_000_000_000.0,  24_600_000_000.0),
        (16, "Malang Branch",           "Jawa Timur",         "Malang",       1,  4100, 22_000_000_000.0,  21_500_000_000.0),
        (17, "Bekasi Branch",           "Jawa Barat",         "Bekasi",       1,  6800, 40_000_000_000.0,  38_900_000_000.0),
        (18, "Tangerang Branch",        "Banten",             "Tangerang",    1,  7200, 45_000_000_000.0,  43_200_000_000.0),
        (19, "Depok Branch",            "Jawa Barat",         "Depok",        1,  5600, 30_000_000_000.0,  29_100_000_000.0),
        (20, "Pekanbaru Branch",        "Riau",               "Pekanbaru",    1,  3500, 19_000_000_000.0,  18_400_000_000.0),
        (21, "Pontianak Branch",        "Kalimantan Barat",   "Pontianak",    1,  2900, 15_000_000_000.0,  14_300_000_000.0),
        (22, "Manado Branch",           "Sulawesi Utara",     "Manado",       1,  2400, 12_000_000_000.0,  11_800_000_000.0),
        (23, "Padang Branch",           "Sumatera Barat",     "Padang",       1,  2700, 14_000_000_000.0,  13_500_000_000.0),
        (24, "Banjarmasin Branch",      "Kalimantan Selatan", "Banjarmasin",  1,  2200, 11_000_000_000.0,  10_800_000_000.0),
        (25, "Mataram Branch",          "Nusa Tenggara Barat","Mataram",      1,  1600,  7_500_000_000.0,   7_100_000_000.0),
    ]
    result = []
    for row in _base:
        bid, _name, _region, city = row[0], row[1], row[2], row[3]
        realization = row[7]
        tier = _NPL_TIER.get(city, "high")
        npl_lo, npl_hi = _NPL_RANGES[tier]
        npl_rate    = _RNG.uniform(npl_lo, npl_hi)
        npl_amount  = round(realization * npl_rate / 1_000_000) * 1_000_000
        deposit_bal = round(realization * _RNG.uniform(0.82, 1.18) / 1_000_000) * 1_000_000
        roi_pct     = round(_RNG.uniform(1.8, 4.2) - npl_rate * 8, 2)  # higher NPL erodes ROI
        meta = _CITY_META.get(city, {"lat": 0.0, "lon": 0.0})
        lat  = round(meta["lat"] + ((bid * 0.013) % 0.08) - 0.04, 4)
        lon  = round(meta["lon"] + ((bid * 0.017) % 0.08) - 0.04, 4)
        result.append(row + (float(npl_amount), float(deposit_bal), round(roi_pct, 2), lat, lon))
    return result


# ── Banking: loan_application ──────────────────────────────────────────────

_LOAN_TYPES = ["KUR Mikro", "KUR Kecil", "KUR Menengah"]

# Approval rates and processing days by loan type and city tier
_LOAN_CONFIG = {
    ("KUR Mikro",    "low"):  {"approval": (0.82, 0.94), "days": (3, 6),   "amount": (150_000_000,   280_000_000)},
    ("KUR Mikro",    "mid"):  {"approval": (0.72, 0.86), "days": (4, 8),   "amount": (100_000_000,   200_000_000)},
    ("KUR Mikro",    "high"): {"approval": (0.58, 0.74), "days": (5, 10),  "amount": (70_000_000,    150_000_000)},
    ("KUR Kecil",    "low"):  {"approval": (0.70, 0.84), "days": (7, 13),  "amount": (1_200_000_000, 3_500_000_000)},
    ("KUR Kecil",    "mid"):  {"approval": (0.58, 0.74), "days": (9, 16),  "amount": (800_000_000,   2_500_000_000)},
    ("KUR Kecil",    "high"): {"approval": (0.44, 0.62), "days": (11, 20), "amount": (500_000_000,   1_500_000_000)},
    ("KUR Menengah", "low"):  {"approval": (0.55, 0.72), "days": (14, 24), "amount": (9_000_000_000, 18_000_000_000)},
    ("KUR Menengah", "mid"):  {"approval": (0.42, 0.60), "days": (18, 30), "amount": (6_000_000_000, 14_000_000_000)},
    ("KUR Menengah", "high"): {"approval": (0.30, 0.48), "days": (22, 38), "amount": (4_000_000_000, 10_000_000_000)},
}


def gen_loan_application(branch_rows: list[tuple]) -> list[tuple]:
    """25 branches x 3 loan types x 8 months = 600 rows."""
    rows: list[tuple] = []
    row_id = 1
    for branch in branch_rows:
        bid, _name, _region, city = branch[0], branch[1], branch[2], branch[3]
        tier = _NPL_TIER.get(city, "high")
        base_volume = max(20, int(branch[5] / 500))   # rough monthly app volume from customer_count
        for loan_type in _LOAN_TYPES:
            cfg = _LOAN_CONFIG[(loan_type, tier)]
            for month in MONTHS_8:
                app_count = _RNG.randint(max(3, base_volume // 5), max(10, base_volume // 2))
                # Trend: slight growth in recent months for low-tier cities
                if tier == "low" and month >= "2026-01":
                    app_count = int(app_count * _RNG.uniform(1.05, 1.18))
                approval_rate = _RNG.uniform(*cfg["approval"])
                approved = max(1, int(app_count * approval_rate))
                rejected = app_count - approved
                avg_days  = round(_RNG.uniform(*cfg["days"]), 1)
                avg_amount = float(round(_RNG.randint(*cfg["amount"]) / 1_000_000) * 1_000_000)
                rows.append((row_id, bid, city, loan_type, app_count, approved, rejected,
                             round(approval_rate * 100, 1), avg_days, avg_amount, month))
                row_id += 1
    return rows


# ── Telco: subscriber ──────────────────────────────────────────────────────

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
    """80 telecom subscribers with tenure and complaint history."""
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
        plan   = _RNG.choice(_PACKAGES[sub_type])
        city   = _RNG.choice(CITIES)
        status = _RNG.choice(["Active"] * 4 + ["Inactive"])
        churn_risk_score = _RNG.randint(70, 99) if status == "Inactive" else _RNG.randint(5, 75)

        # Tenure: inversely correlated with churn risk (new subscribers churn more)
        if churn_risk_score >= 70:
            tenure_months = _RNG.randint(1, 24)
        elif churn_risk_score >= 40:
            tenure_months = _RNG.randint(12, 48)
        else:
            tenure_months = _RNG.randint(24, 72)

        # Monthly complaints: positively correlated with churn risk
        if churn_risk_score >= 70:
            monthly_complaints = _RNG.randint(2, 7)
        elif churn_risk_score >= 40:
            monthly_complaints = _RNG.randint(0, 3)
        else:
            monthly_complaints = _RNG.randint(0, 1)

        activation_date = date(2019, 1, 1) + timedelta(days=_RNG.randint(0, 1826))
        rows.append((i, name, sub_type, plan, city, status, str(activation_date),
                     churn_risk_score, arpu, tenure_months, monthly_complaints))
    return rows


# ── Telco: data_usage ──────────────────────────────────────────────────────

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
            usage   = round(quota * _RNG.uniform(0.60, 1.25), 1)
            speed   = round(_RNG.uniform(5.0, 55.0), 1)
            overage = 0.0
            if usage > quota:
                overage = float(round((usage - quota) * 5_000 / 1_000) * 1_000)
            rows.append((row_id, sub_id, month, quota, usage, speed, overage))
            row_id += 1
    return rows


# ── Telco: network ─────────────────────────────────────────────────────────

def gen_network() -> list[tuple]:
    """27 network stations with latency and packet-loss metrics."""
    # (id, region, city, network_type, bts_count, capacity_mbps,
    #  utilization_pct, status, avg_latency_ms, packet_loss_pct, lat, lon)
    _stations = [
        # Java — high utilization → higher latency/packet loss
        (1,  "DKI Jakarta",        "Jakarta",     "5G",     420, 13000.0, 81.4, "High"),
        (2,  "Jawa Timur",         "Surabaya",    "4.5G",   285,  3800.0, 87.6, "Critical"),
        (3,  "Jawa Barat",         "Bandung",     "4G LTE", 218,  2180.0, 73.2, "Optimal"),
        (4,  "Jawa Tengah",        "Semarang",    "4G LTE", 162,  1620.0, 69.4, "Optimal"),
        (5,  "DI Yogyakarta",      "Yogyakarta",  "4G LTE", 104,  1040.0, 75.8, "High"),
        (6,  "Jawa Timur",         "Malang",      "4G LTE", 118,  1180.0, 80.1, "High"),
        (7,  "Jawa Barat",         "Bekasi",      "4G LTE", 201,  2010.0, 84.3, "Critical"),
        (8,  "Banten",             "Tangerang",   "4G LTE", 192,  1920.0, 82.7, "High"),
        (9,  "Jawa Barat",         "Depok",       "4G LTE", 158,  1580.0, 71.5, "Optimal"),
        (10, "Bali",               "Denpasar",    "4.5G",   138,  1380.0, 91.4, "Critical"),
        # Sumatra — moderate
        (11, "Sumatera Utara",     "Medan",       "4G LTE", 182,  1820.0, 57.3, "Optimal"),
        (12, "Sumatera Selatan",   "Palembang",   "4G LTE",  90,   900.0, 62.8, "Optimal"),
        (13, "Riau",               "Pekanbaru",   "4G LTE",  84,   840.0, 58.9, "Optimal"),
        (14, "Sumatera Barat",     "Padang",      "4G LTE",  67,   670.0, 45.2, "Optimal"),
        (15, "Kepulauan Riau",     "Batam",       "4G LTE",  95,   950.0, 64.7, "Optimal"),
        (16, "Aceh",               "Banda Aceh",  "4G LTE",  58,   580.0, 39.6, "Optimal"),
        # Kalimantan — moderate-low
        (17, "Kalimantan Timur",   "Balikpapan",  "4G LTE",  98,   980.0, 43.8, "Optimal"),
        (18, "Kalimantan Barat",   "Pontianak",   "4G LTE",  72,   720.0, 41.5, "Optimal"),
        (19, "Kalimantan Selatan", "Banjarmasin", "4G LTE",  75,   750.0, 53.4, "Optimal"),
        (20, "Kalimantan Timur",   "Samarinda",   "4G LTE",  68,   680.0, 37.9, "Optimal"),
        # Sulawesi
        (21, "Sulawesi Selatan",   "Makassar",    "4G LTE", 124,  1240.0, 49.3, "Optimal"),
        (22, "Sulawesi Utara",     "Manado",      "4G LTE",  60,   600.0, 40.7, "Optimal"),
        (23, "Sulawesi Tenggara",  "Kendari",     "4G LTE",  45,   450.0, 33.2, "Optimal"),
        # Nusa Tenggara
        (24, "Nusa Tenggara Barat","Mataram",     "4G LTE",  54,   540.0, 44.6, "Optimal"),
        (25, "Nusa Tenggara Timur","Kupang",      "4G LTE",  38,   380.0, 28.9, "Optimal"),
        # Maluku & Papua
        (26, "Maluku",             "Ambon",       "4G LTE",  42,   420.0, 31.5, "Optimal"),
        (27, "Papua",              "Jayapura",    "4G LTE",  35,   350.0, 29.4, "Optimal"),
    ]
    result = []
    for row in _stations:
        util = row[6]
        status = row[7]
        # Latency: rises sharply above 70% utilization
        if status == "Critical":
            latency = round(_RNG.uniform(68, 130), 1)
            pkt_loss = round(_RNG.uniform(1.5, 3.2), 2)
        elif status == "High":
            latency = round(_RNG.uniform(38, 72), 1)
            pkt_loss = round(_RNG.uniform(0.5, 1.8), 2)
        else:
            latency = round(_RNG.uniform(10, 42), 1)
            pkt_loss = round(_RNG.uniform(0.0, 0.6), 2)
        meta = _CITY_META.get(row[2], {"lat": 0.0, "lon": 0.0})
        result.append(row + (latency, pkt_loss, meta["lat"], meta["lon"]))
    return result


# ── Telco: network_incident ────────────────────────────────────────────────

def gen_network_incident(network_rows: list[tuple]) -> list[tuple]:
    """27 cities x 6 months = 162 rows of monthly network incident data."""
    rows: list[tuple] = []
    row_id = 1
    for net in network_rows:
        _nid, _region, city, _ntype, _bts, _cap, util, status, _lat_ms, _pkt, _lat, _lon = net
        for month in MONTHS_6:
            # Higher utilization → more incidents
            if status == "Critical":
                incident_count = _RNG.randint(8, 18)
                avg_downtime_hrs = round(_RNG.uniform(2.5, 6.0), 1)
            elif status == "High":
                incident_count = _RNG.randint(3, 9)
                avg_downtime_hrs = round(_RNG.uniform(0.8, 2.8), 1)
            else:
                incident_count = _RNG.randint(0, 4)
                avg_downtime_hrs = round(_RNG.uniform(0.1, 1.2), 1)
            resolved_count = max(0, incident_count - _RNG.randint(0, 2))
            avg_resolution_hrs = round(avg_downtime_hrs * _RNG.uniform(1.5, 3.5), 1)
            mttr_hrs = round(avg_resolution_hrs, 1)  # mean time to resolve
            # SLA breach: incident taking >4h to resolve
            sla_breach_count = _RNG.randint(0, max(0, incident_count // 3))
            rows.append((row_id, city, month, incident_count, resolved_count,
                         avg_downtime_hrs, avg_resolution_hrs, mttr_hrs, sla_breach_count))
            row_id += 1
    return rows


# ── Government: resident ───────────────────────────────────────────────────

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
        total  = _RNG.randint(45_000, 250_000)
        male   = int(total * _RNG.uniform(0.48, 0.52))
        female = total - male
        rows.append((i, district, city, province, total, male, female, 2025))
    return rows


# ── Government: regional_budget ────────────────────────────────────────────

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
    "Q1": (0.08, 0.18), "Q2": (0.25, 0.38),
    "Q3": (0.50, 0.78), "Q4": (0.88, 0.99),
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


# ── Government: public_service ─────────────────────────────────────────────

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
            on_time_count     = int(application_count * _RNG.uniform(0.88, 0.99))
            pending_count     = _RNG.randint(0, max(1, application_count // 20))
            satisfaction_pct  = round(_RNG.uniform(82.0, 98.0), 1)
            complaint_count   = _RNG.randint(0, max(1, application_count // 50))
            if service_type == "IMB/PBG":
                avg_processing_days = round(_RNG.uniform(10.0, 16.0), 1)
            elif service_type == "Paspor":
                avg_processing_days = round(_RNG.uniform(2.5, 4.0), 1)
            else:
                avg_processing_days = round(_RNG.uniform(0.5, 2.5), 1)
            rows.append((row_id, service_type, agency, application_count, on_time_count,
                         pending_count, satisfaction_pct, complaint_count,
                         avg_processing_days, month))
            row_id += 1
    return rows


# ── Convenience: generate everything ─────────────────────────────────────

def generate_all() -> dict[str, list[tuple]]:
    """Return all tables keyed by table name. Deterministic due to fixed RNG seed."""
    subscribers  = gen_subscriber()
    branch_rows  = gen_branch()
    network_rows = gen_network()
    return {
        "msme_credit":       gen_msme_credit(),
        "customer":          gen_customer(),
        "branch":            branch_rows,
        "loan_application":  gen_loan_application(branch_rows),
        "subscriber":        subscribers,
        "data_usage":        gen_data_usage(subscribers),
        "network":           network_rows,
        "network_incident":  gen_network_incident(network_rows),
        "resident":          gen_resident(),
        "regional_budget":   gen_regional_budget(),
        "public_service":    gen_public_service(),
    }


if __name__ == "__main__":
    data = generate_all()
    total = sum(len(v) for v in data.values())
    print(f"Total rows: {total}")
    for table, rows in data.items():
        print(f"  {table}: {len(rows)}")
