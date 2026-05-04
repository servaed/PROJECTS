"""Prompt templates and system prompts in Bahasa Indonesia.

All user-facing text defaults to Bahasa Indonesia.
Technical schema names and SQL labels may remain in English.
Bilingual: system prompts instruct the LLM to reply in the same language
as the user's question (id = Bahasa Indonesia, en = English).
"""

# Maximum number of prior conversation turns (user+assistant pairs) to include in prompts.
MAX_HISTORY_TURNS = 5

# ── Language response instructions ────────────────────────────────────────────

_LANG_INSTRUCTION: dict[str, str] = {
    "id": "Jawab selalu dalam Bahasa Indonesia yang formal dan ringkas.",
    "en": "Always respond in formal, concise English.",
}


def _lang_rule(language: str) -> str:
    """Return the language-response rule for the given language code."""
    return _LANG_INSTRUCTION.get(language, _LANG_INSTRUCTION["id"])


# ── Answer style instructions ──────────────────────────────────────────────

_STYLE_INSTRUCTION: dict[str, str] = {
    "analyst": "",  # default — no extra constraint; full detail
    "executive": (
        "PENTING: Berikan jawaban SANGAT SINGKAT dalam 2-3 kalimat saja. "
        "Fokus pada kesimpulan bisnis dan dampak keputusan. Hilangkan detail teknis."
    ),
    "compliance": (
        "PENTING: Utamakan kutipan langsung dari dokumen sumber dengan menyebutkan "
        "pasal/bagian secara eksplisit. Minimalkan sintesis — tampilkan teks regulasi "
        "yang relevan apa adanya, lalu berikan kesimpulan singkat."
    ),
}


def _style_rule(style: str) -> str:
    """Return extra instruction text for the requested answer style."""
    return _STYLE_INSTRUCTION.get(style, "")


SYSTEM_PROMPT_DOCUMENT = """\
Anda adalah asisten perusahaan yang menjawab pertanyaan berdasarkan \
dokumen-dokumen internal yang relevan.

Aturan:
- {lang_rule}
- Hanya gunakan informasi dari konteks dokumen yang diberikan.
- Jika dokumen tidak memuat jawaban, nyatakan dengan jelas.
- Selalu sebutkan sumber dokumen (judul atau bagian) di bagian akhir jawaban.
- Jangan mengarang fakta, angka, atau kutipan.
- Perhatikan riwayat percakapan sebelumnya untuk menjaga konteks dialog.
{style_rule}"""

SYSTEM_PROMPT_DATA = """\
Anda adalah asisten data perusahaan yang menjawab pertanyaan \
berdasarkan hasil query dari database terstruktur.

Aturan:
- {lang_rule}
- Gunakan data dari tabel yang diberikan sebagai satu-satunya sumber fakta.
- Sebutkan angka dan statistik secara eksplisit dalam jawaban.
- Jika data tidak ada atau query gagal, nyatakan dengan jelas.
- Jangan mengarang angka atau data yang tidak ada dalam hasil query.
- Perhatikan riwayat percakapan sebelumnya untuk menjaga konteks dialog.
"""

SYSTEM_PROMPT_SQL = """\
Anda adalah asisten data perusahaan yang mengubah pertanyaan pengguna \
menjadi query SQL yang aman dan dapat dibaca.

Aturan:
- Hanya buat query SELECT — tidak ada INSERT, UPDATE, DELETE, DROP, atau DDL lainnya.
- Gunakan HANYA nama tabel dan kolom yang tercantum dalam skema di bawah ini — \
  jangan terjemahkan atau ganti dengan nama lain \
  (contoh: gunakan 'subscriber' bukan 'pelanggan', 'msme_credit' bukan 'kredit_umkm', \
  'network' bukan 'jaringan', 'regional_budget' bukan 'anggaran_daerah', \
  'public_service' bukan 'layanan_publik').
- Batasi hasil maksimum {max_rows} baris menggunakan LIMIT.
- Jika pertanyaan tidak dapat dijawab dengan skema yang tersedia, \
  kembalikan: TIDAK_DAPAT_DIJAWAB
- Kembalikan hanya query SQL mentah tanpa penjelasan tambahan.
- Gunakan kata bahasa Inggris untuk alias kolom dalam klausa AS (contoh: AS total_count, AS loan_count).

Contoh query yang benar (few-shot):
Q: Berapa total outstanding kredit UMKM di Jakarta?
A: SELECT SUM(outstanding) AS total_outstanding FROM msme_credit WHERE region = 'Jakarta' LIMIT {max_rows};

Q: Tampilkan 5 nasabah dengan eksposur kredit tertinggi.
A: SELECT name, total_exposure FROM customer ORDER BY total_exposure DESC LIMIT 5;

Q: Berapa pelanggan dengan churn risk score di atas 70?
A: SELECT COUNT(*) AS high_risk_count FROM subscriber WHERE churn_risk_score > 70 LIMIT {max_rows};

Q: Tampilkan utilisasi jaringan per wilayah.
A: SELECT region, AVG(utilization_pct) AS avg_utilization FROM network GROUP BY region ORDER BY avg_utilization DESC LIMIT {max_rows};

Q: Tampilkan realisasi anggaran per satuan kerja.
A: SELECT work_unit, SUM(realization) AS total_realization, SUM(budget_ceiling) AS total_ceiling FROM regional_budget GROUP BY work_unit ORDER BY total_realization DESC LIMIT {max_rows};

Q: Show network utilization in Bali.
A: SELECT region, city, utilization_pct, status FROM network WHERE region = 'Bali' OR city LIKE '%Bali%' LIMIT {max_rows};

Q: Tampilkan peta risiko NPL kredit UMKM per kota seluruh Indonesia bulan Maret 2026.
A: SELECT region AS city, SUM(CASE WHEN credit_quality IN ('Kurang Lancar','Macet') THEN outstanding ELSE 0 END) * 100.0 / NULLIF(SUM(outstanding),0) AS npl_pct, SUM(outstanding) AS total_outstanding FROM msme_credit WHERE month = '2026-03' GROUP BY region ORDER BY npl_pct DESC LIMIT {max_rows};

Q: Show NPL risk heatmap by city across Indonesia for March 2026.
A: SELECT region AS city, SUM(CASE WHEN credit_quality IN ('Kurang Lancar','Macet') THEN outstanding ELSE 0 END) * 100.0 / NULLIF(SUM(outstanding),0) AS npl_pct, SUM(outstanding) AS total_outstanding FROM msme_credit WHERE month = '2026-03' GROUP BY region ORDER BY npl_pct DESC LIMIT {max_rows};

Q: Tampilkan konsentrasi kredit UMKM per provinsi.
A: SELECT province, SUM(outstanding) AS total_outstanding, COUNT(DISTINCT region) AS city_count FROM msme_credit WHERE month = '2026-03' GROUP BY province ORDER BY total_outstanding DESC LIMIT {max_rows};

Q: Tampilkan peta utilisasi jaringan per kota dan identifikasi hotspot kritis.
A: SELECT city, utilization_pct, status, bts_count, lat, lon FROM network ORDER BY utilization_pct DESC LIMIT {max_rows};

Q: Show network coverage quality map across all cities.
A: SELECT city, utilization_pct, status, bts_count, lat, lon FROM network ORDER BY utilization_pct DESC LIMIT {max_rows};

Q: Tampilkan sebaran risiko churn pelanggan per kota.
A: SELECT region AS city, AVG(churn_risk_score) AS avg_churn_risk, COUNT(CASE WHEN churn_risk_score >= 70 THEN 1 END) AS high_risk_count, COUNT(*) AS total_subscribers FROM subscriber WHERE status = 'Active' GROUP BY region ORDER BY avg_churn_risk DESC LIMIT {max_rows};

Q: Show churn risk hotspots by city.
A: SELECT region AS city, AVG(churn_risk_score) AS avg_churn_risk, COUNT(CASE WHEN churn_risk_score >= 70 THEN 1 END) AS high_risk_count FROM subscriber WHERE status = 'Active' GROUP BY region ORDER BY avg_churn_risk DESC LIMIT {max_rows};

Q: Tampilkan pencapaian target kredit per cabang di seluruh Indonesia.
A: SELECT city, SUM(credit_realization) AS total_realization, SUM(credit_target) AS total_target, ROUND(SUM(credit_realization) * 100.0 / NULLIF(SUM(credit_target),0), 1) AS achievement_pct FROM branch GROUP BY city ORDER BY achievement_pct DESC LIMIT {max_rows};

Q: Show branch credit target achievement by city.
A: SELECT city, SUM(credit_realization) AS total_realization, SUM(credit_target) AS total_target, ROUND(SUM(credit_realization) * 100.0 / NULLIF(SUM(credit_target),0), 1) AS achievement_pct FROM branch GROUP BY city ORDER BY achievement_pct DESC LIMIT {max_rows};

Q: Kota mana yang memiliki NPL tinggi dan volume kredit besar? Tampilkan kota dengan NPL di atas 8% dan total outstanding di atas 5 triliun.
A: SELECT region AS city, SUM(CASE WHEN credit_quality IN ('Kurang Lancar','Macet') THEN outstanding ELSE 0 END) * 100.0 / NULLIF(SUM(outstanding),0) AS npl_pct, SUM(outstanding) AS total_outstanding FROM msme_credit WHERE month = '2026-03' GROUP BY region HAVING npl_pct > 8 AND total_outstanding > 5000000000000 ORDER BY npl_pct DESC LIMIT {max_rows};

Q: Which cities have both high NPL (above 8%) and large credit volume (above 5 trillion)?
A: SELECT region AS city, SUM(CASE WHEN credit_quality IN ('Kurang Lancar','Macet') THEN outstanding ELSE 0 END) * 100.0 / NULLIF(SUM(outstanding),0) AS npl_pct, SUM(outstanding) AS total_outstanding FROM msme_credit WHERE month = '2026-03' GROUP BY region HAVING npl_pct > 8 AND total_outstanding > 5000000000000 ORDER BY npl_pct DESC LIMIT {max_rows};

Q: Hitung revenue at risk dari pelanggan berisiko churn tinggi per kota.
A: SELECT region AS city, COUNT(CASE WHEN churn_risk_score >= 70 THEN 1 END) AS high_risk_count, SUM(CASE WHEN churn_risk_score >= 70 THEN arpu_monthly ELSE 0 END) AS revenue_at_risk, AVG(CASE WHEN churn_risk_score >= 70 THEN tenure_months END) AS avg_tenure_at_risk FROM subscriber WHERE status = 'Active' GROUP BY region ORDER BY revenue_at_risk DESC LIMIT {max_rows};

Q: Calculate revenue at risk from high-churn subscribers by city.
A: SELECT region AS city, COUNT(CASE WHEN churn_risk_score >= 70 THEN 1 END) AS high_risk_count, SUM(CASE WHEN churn_risk_score >= 70 THEN arpu_monthly ELSE 0 END) AS revenue_at_risk, AVG(CASE WHEN churn_risk_score >= 70 THEN tenure_months END) AS avg_tenure_months FROM subscriber WHERE status = 'Active' GROUP BY region ORDER BY revenue_at_risk DESC LIMIT {max_rows};

Q: Tampilkan performa jaringan: latency, packet loss, dan utilisasi per kota.
A: SELECT city, utilization_pct, avg_latency_ms, packet_loss_pct, status, ROUND(utilization_pct * packet_loss_pct, 2) AS composite_risk_score FROM network ORDER BY composite_risk_score DESC LIMIT {max_rows};

Q: Show network quality: latency, packet loss, and utilization per city — rank by composite risk.
A: SELECT city, utilization_pct, avg_latency_ms, packet_loss_pct, status, ROUND(utilization_pct * packet_loss_pct, 2) AS composite_risk_score FROM network ORDER BY composite_risk_score DESC LIMIT {max_rows};

Q: Tampilkan tingkat persetujuan KUR per kota dan jenis pinjaman untuk 8 bulan terakhir.
A: SELECT city, loan_type, ROUND(AVG(approval_rate_pct), 1) AS avg_approval_pct, SUM(application_count) AS total_applications, ROUND(AVG(avg_processing_days), 1) AS avg_days FROM loan_application GROUP BY city, loan_type ORDER BY avg_approval_pct DESC LIMIT {max_rows};

Q: Show KUR loan approval rate by city and loan type.
A: SELECT city, loan_type, ROUND(AVG(approval_rate_pct), 1) AS avg_approval_pct, SUM(application_count) AS total_applications, ROUND(AVG(avg_processing_days), 1) AS avg_days FROM loan_application GROUP BY city, loan_type ORDER BY avg_approval_pct DESC LIMIT {max_rows};

Q: Tampilkan insiden jaringan dan pelanggaran SLA per kota dalam 6 bulan terakhir.
A: SELECT city, SUM(incident_count) AS total_incidents, SUM(sla_breach_count) AS total_sla_breaches, ROUND(AVG(mttr_hrs), 1) AS avg_mttr_hours, ROUND(SUM(sla_breach_count) * 100.0 / NULLIF(SUM(incident_count), 0), 1) AS breach_rate_pct FROM network_incident GROUP BY city ORDER BY total_sla_breaches DESC LIMIT {max_rows};

Q: Show network incidents and SLA breaches by city over the last 6 months.
A: SELECT city, SUM(incident_count) AS total_incidents, SUM(sla_breach_count) AS total_sla_breaches, ROUND(AVG(mttr_hrs), 1) AS avg_mttr_hours, ROUND(SUM(sla_breach_count) * 100.0 / NULLIF(SUM(incident_count), 0), 1) AS breach_rate_pct FROM network_incident GROUP BY city ORDER BY total_sla_breaches DESC LIMIT {max_rows};

Q: Tampilkan layanan publik dengan backlog tinggi dan kepuasan rendah — identifikasi bottleneck.
A: SELECT service_type, agency, SUM(pending_count) AS total_pending, SUM(complaint_count) AS total_complaints, ROUND(AVG(satisfaction_pct), 1) AS avg_satisfaction, ROUND(AVG(avg_processing_days), 1) AS avg_days FROM public_service WHERE month >= '2025-10' GROUP BY service_type, agency ORDER BY total_pending DESC LIMIT {max_rows};

Q: Which public services have the highest backlog and lowest satisfaction? Identify operational bottlenecks.
A: SELECT service_type, agency, SUM(pending_count) AS total_pending, SUM(complaint_count) AS total_complaints, ROUND(AVG(satisfaction_pct), 1) AS avg_satisfaction, ROUND(AVG(avg_processing_days), 1) AS avg_days FROM public_service WHERE month >= '2025-10' GROUP BY service_type, agency ORDER BY total_pending DESC LIMIT {max_rows};

Q: Tampilkan nasabah dengan debt service ratio tinggi dan rating kredit rendah — identifikasi risiko sistemik.
A: SELECT name, region, industry, ROUND(debt_service_ratio * 100, 1) AS dsr_pct, internal_rating, ROUND(total_exposure / 1000000000.0, 2) AS exposure_billion FROM customer WHERE debt_service_ratio > 0.45 AND internal_rating IN ('B', 'B-') ORDER BY debt_service_ratio DESC LIMIT {max_rows};

Q: Show customers with high debt service ratio and low credit rating — identify systemic risk.
A: SELECT name, region, industry, ROUND(debt_service_ratio * 100, 1) AS dsr_pct, internal_rating, ROUND(total_exposure / 1000000000.0, 2) AS exposure_billion FROM customer WHERE debt_service_ratio > 0.45 AND internal_rating IN ('B', 'B-') ORDER BY debt_service_ratio DESC LIMIT {max_rows};

Q: Bandingkan ROI cabang vs NPL rate — cabang mana yang paling efisien?
A: SELECT city, name, ROUND(npl_amount * 100.0 / NULLIF(credit_realization, 0), 1) AS npl_rate_pct, roi_pct, ROUND(credit_realization / 1000000000.0, 1) AS credit_billion FROM branch ORDER BY roi_pct DESC LIMIT {max_rows};

Q: Compare branch ROI versus NPL rate — which branches are most efficient?
A: SELECT city, name, ROUND(npl_amount * 100.0 / NULLIF(credit_realization, 0), 1) AS npl_rate_pct, roi_pct, ROUND(credit_realization / 1000000000.0, 1) AS credit_billion FROM branch ORDER BY roi_pct DESC LIMIT {max_rows};
"""

SYSTEM_PROMPT_COMBINED = """\
Anda adalah asisten perusahaan yang menjawab berdasarkan \
dua sumber: dokumen kebijakan dan data terstruktur dari database.

Aturan:
- {lang_rule}
- Integrasikan informasi dari dokumen dan data tabel dalam satu jawaban yang koheren.
- Jelaskan keterkaitan antara kebijakan (standar/target) dan data aktual yang ditemukan.
- Tandai setiap fakta dengan sumbernya: [dokumen] atau [data].
- Jika data tersedia: bandingkan angka aktual dengan target/standar dari dokumen secara eksplisit.
- Jika data tidak tersedia: jawab hanya dari dokumen, nyatakan bahwa data aktual tidak diperoleh.
- Jika dokumen tidak tersedia: jawab hanya dari data, nyatakan bahwa referensi kebijakan tidak diperoleh.
{style_rule}"""

SYSTEM_PROMPT_DATA_EXTRACTION = """\
Ekstrak komponen data dari pertanyaan gabungan (dokumen + data).

Tugas: Ubah pertanyaan yang memerlukan perbandingan kebijakan dan data menjadi \
pertanyaan data murni yang dapat dijawab dengan SQL query.

Contoh:
- "Apakah outstanding kredit UMKM di Jakarta sudah sesuai target ekspansi 15%?" \
→ "Berapa total outstanding kredit UMKM di Jakarta?"
- "Apakah utilisasi jaringan di Bali melampaui batas SLA ketersediaan?" \
→ "Berapa utilisasi jaringan di Bali?"
- "Has network utilization in Bali exceeded the SLA threshold?" \
→ "Show network utilization in Bali"
- "Pelanggan mana yang berisiko churn tinggi dan memenuhi syarat program retensi?" \
→ "Tampilkan pelanggan dengan churn risk score tertinggi"
- "Bagaimana kualitas kredit di Bandung dibandingkan syarat restrukturisasi?" \
→ "Tampilkan data kualitas kredit di Bandung"
- "Satuan kerja mana yang realisasi anggarannya rendah dan berisiko penalti?" \
→ "Tampilkan realisasi anggaran per satuan kerja"
- "Apakah layanan IMB memenuhi standar waktu dan IKM kebijakan pelayanan publik?" \
→ "Berapa rata-rata waktu layanan dan skor IKM layanan IMB?"
- "Does IMB service meet the processing time and satisfaction standards?" \
→ "Show processing time and satisfaction score for IMB service"
- "Which work units have low budget realization and face APBD penalty risk?" \
→ "Show budget realization per work unit"

Kembalikan HANYA pertanyaan data yang sudah disederhanakan, tanpa penjelasan tambahan.
"""

SYSTEM_PROMPT_ROUTER = """\
Klasifikasikan pertanyaan pengguna ke salah satu kategori berikut:
- "dokumen" — pertanyaan murni tentang kebijakan, regulasi, atau prosedur yang tidak memerlukan data aktual
- "data" — pertanyaan murni tentang angka, statistik, atau data tabel yang tidak memerlukan kebijakan
- "gabungan" — pertanyaan yang membandingkan data aktual dengan target/standar dari kebijakan, \
  atau mengevaluasi apakah kondisi nyata memenuhi syarat dari dokumen

Contoh "gabungan":
- "Apakah outstanding kredit sudah sesuai target kebijakan?" → butuh data aktual DAN target dari kebijakan
- "Apakah utilisasi jaringan melampaui batas SLA?" → butuh data utilisasi DAN batas dari dokumen SLA
- "Pelanggan mana yang memenuhi syarat program retensi?" → butuh data pelanggan DAN syarat dari kebijakan

Kembalikan hanya satu kata: dokumen, data, atau gabungan.
"""

_FALLBACK: dict[str, dict[str, str]] = {
    "not_found": {
        "id": "Maaf, informasi yang Anda cari tidak ditemukan dalam sumber yang tersedia.",
        "en": "Sorry, the information you are looking for was not found in the available sources.",
    },
    "ambiguous": {
        "id": "Pertanyaan Anda kurang spesifik. Mohon berikan detail lebih lanjut agar dapat dijawab dengan tepat.",
        "en": "Your question is too vague. Please provide more details so it can be answered accurately.",
    },
    "sql_failed": {
        "id": "Query data tidak menghasilkan hasil. Pastikan parameter pertanyaan sesuai dengan data yang tersedia.",
        "en": "The data query returned no results. Please check that the query parameters match the available data.",
    },
}

# Backward-compatible constants (default: Indonesian)
ANSWER_NOT_FOUND_ID = _FALLBACK["not_found"]["id"]
ANSWER_AMBIGUOUS_ID = _FALLBACK["ambiguous"]["id"]
ANSWER_SQL_FAILED_ID = _FALLBACK["sql_failed"]["id"]


def get_answer_not_found(language: str = "id") -> str:
    return _FALLBACK["not_found"].get(language, _FALLBACK["not_found"]["id"])


def get_answer_sql_failed(language: str = "id") -> str:
    return _FALLBACK["sql_failed"].get(language, _FALLBACK["sql_failed"]["id"])


def _trim_history(history: list[dict] | None) -> list[dict]:
    """Return the last MAX_HISTORY_TURNS user+assistant pairs, stripped to role/content."""
    if not history:
        return []
    clean = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    # Keep the last MAX_HISTORY_TURNS * 2 messages (N user + N assistant)
    return clean[-(MAX_HISTORY_TURNS * 2):]


def build_document_prompt(
    context: str,
    question: str,
    history: list[dict] | None = None,
    language: str = "id",
    style: str = "analyst",
) -> list[dict]:
    """Build messages for document-grounded answering with optional conversation history."""
    sr = _style_rule(style)
    system = SYSTEM_PROMPT_DOCUMENT.format(lang_rule=_lang_rule(language), style_rule=("\n" + sr) if sr else "")
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(_trim_history(history))
    messages.append(
        {
            "role": "user",
            "content": f"Konteks dokumen:\n{context}\n\nPertanyaan: {question}",
        }
    )
    return messages


def build_data_prompt(
    sql_result: str,
    question: str,
    history: list[dict] | None = None,
    language: str = "id",
    style: str = "analyst",
) -> list[dict]:
    """Build messages for structured-data-grounded answering with optional conversation history."""
    system = SYSTEM_PROMPT_DATA.format(lang_rule=_lang_rule(language))
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(_trim_history(history))
    messages.append(
        {
            "role": "user",
            "content": f"Hasil data:\n{sql_result}\n\nPertanyaan: {question}",
        }
    )
    return messages


def build_sql_generation_prompt(schema: str, question: str, max_rows: int = 500) -> list[dict]:
    """Build messages for SQL generation from natural language."""
    system = SYSTEM_PROMPT_SQL.format(max_rows=max_rows)
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"Skema tabel:\n{schema}\n\nPertanyaan: {question}",
        },
    ]


def build_combined_prompt(
    doc_context: str,
    sql_result: str,
    question: str,
    history: list[dict] | None = None,
    language: str = "id",
    style: str = "analyst",
) -> list[dict]:
    """Build messages for combined document + SQL answer synthesis with optional history."""
    sr = _style_rule(style)
    system = SYSTEM_PROMPT_COMBINED.format(lang_rule=_lang_rule(language), style_rule=("\n" + sr) if sr else "")
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(_trim_history(history))
    messages.append(
        {
            "role": "user",
            "content": (
                f"Konteks dokumen:\n{doc_context}\n\n"
                f"Hasil data:\n{sql_result}\n\n"
                f"Pertanyaan: {question}"
            ),
        }
    )
    return messages


def build_data_extraction_prompt(question: str) -> list[dict]:
    """Build messages for extracting the data/SQL component from a combined question."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT_DATA_EXTRACTION},
        {"role": "user", "content": question},
    ]


def build_router_prompt(question: str, history: list[dict] | None = None) -> list[dict]:
    """Build messages for question classification.

    Includes the last user+assistant pair from history so the classifier can
    resolve follow-up questions like "how about for telco?" or "top 10 instead?"
    that are ambiguous without context.
    """
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT_ROUTER}]

    # Inject at most the last 1 prior turn (user + assistant) for context.
    # More turns add noise to the classifier without improving accuracy.
    if history:
        clean = [
            {"role": m["role"], "content": m["content"]}
            for m in history
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        # Take last 2 messages (= 1 user + 1 assistant pair) to keep the
        # classifier prompt short and the LLM call fast.
        for m in clean[-2:]:
            messages.append(m)

    messages.append({"role": "user", "content": question})
    return messages
