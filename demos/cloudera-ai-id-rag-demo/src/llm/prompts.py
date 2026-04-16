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
"""

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
- Gunakan hanya tabel dan kolom yang ada dalam skema yang diberikan.
- Batasi hasil maksimum {max_rows} baris menggunakan LIMIT.
- Jika pertanyaan tidak dapat dijawab dengan skema yang tersedia, \
  kembalikan: TIDAK_DAPAT_DIJAWAB
- Kembalikan hanya query SQL mentah tanpa penjelasan tambahan.
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
"""

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
) -> list[dict]:
    """Build messages for document-grounded answering with optional conversation history."""
    system = SYSTEM_PROMPT_DOCUMENT.format(lang_rule=_lang_rule(language))
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
) -> list[dict]:
    """Build messages for combined document + SQL answer synthesis with optional history."""
    system = SYSTEM_PROMPT_COMBINED.format(lang_rule=_lang_rule(language))
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


def build_router_prompt(question: str) -> list[dict]:
    """Build messages for question classification."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT_ROUTER},
        {"role": "user", "content": question},
    ]
