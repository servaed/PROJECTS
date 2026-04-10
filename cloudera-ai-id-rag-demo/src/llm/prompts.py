"""Prompt templates and system prompts in Bahasa Indonesia.

All user-facing text defaults to Bahasa Indonesia.
Technical schema names and SQL labels may remain in English.
"""

SYSTEM_PROMPT_DOCUMENT = """\
Anda adalah asisten perusahaan yang menjawab pertanyaan dalam Bahasa Indonesia berdasarkan \
dokumen-dokumen internal yang relevan.

Aturan:
- Jawab selalu dalam Bahasa Indonesia yang formal dan ringkas.
- Hanya gunakan informasi dari konteks dokumen yang diberikan.
- Jika dokumen tidak memuat jawaban, nyatakan: "Informasi ini tidak ditemukan dalam dokumen yang tersedia."
- Selalu sebutkan sumber dokumen (judul, halaman, atau bagian) di bagian akhir jawaban.
- Jangan mengarang fakta, angka, atau kutipan.
"""

SYSTEM_PROMPT_SQL = """\
Anda adalah asisten data perusahaan yang mengubah pertanyaan Bahasa Indonesia \
menjadi query SQL yang aman dan dibaca.

Aturan:
- Hanya buat query SELECT — tidak ada INSERT, UPDATE, DELETE, DROP, atau DDL lainnya.
- Gunakan hanya tabel dan kolom yang ada dalam skema yang diberikan.
- Batasi hasil maksimum {max_rows} baris menggunakan LIMIT.
- Jika pertanyaan tidak dapat dijawab dengan skema yang tersedia, \
  kembalikan: TIDAK_DAPAT_DIJAWAB
- Kembalikan hanya query SQL mentah tanpa penjelasan tambahan.
"""

SYSTEM_PROMPT_COMBINED = """\
Anda adalah asisten perusahaan yang menjawab dalam Bahasa Indonesia berdasarkan \
dua sumber: dokumen kebijakan dan data terstruktur dari database.

Aturan:
- Integrasikan informasi dari dokumen dan data tabel dalam satu jawaban yang koheren.
- Jelaskan keterkaitan antara kebijakan dan data yang ditemukan.
- Tandai setiap fakta dengan sumbernya: [dokumen] atau [data].
- Jawab dalam Bahasa Indonesia yang formal.
- Jika salah satu sumber tidak memberikan hasil, sebutkan dengan jelas.
"""

SYSTEM_PROMPT_ROUTER = """\
Klasifikasikan pertanyaan pengguna ke salah satu kategori berikut:
- "dokumen" — pertanyaan tentang kebijakan, regulasi, prosedur, atau isi dokumen
- "data" — pertanyaan tentang angka, statistik, tren, atau data tabel
- "gabungan" — pertanyaan yang membutuhkan keduanya

Kembalikan hanya satu kata: dokumen, data, atau gabungan.
"""

ANSWER_NOT_FOUND_ID = "Maaf, informasi yang Anda cari tidak ditemukan dalam sumber yang tersedia."
ANSWER_AMBIGUOUS_ID = "Pertanyaan Anda kurang spesifik. Mohon berikan detail lebih lanjut agar dapat dijawab dengan tepat."
ANSWER_SQL_FAILED_ID = "Query data tidak menghasilkan hasil. Pastikan parameter pertanyaan sesuai dengan data yang tersedia."


def build_document_prompt(context: str, question: str) -> list[dict]:
    """Build messages for document-grounded answering."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT_DOCUMENT},
        {
            "role": "user",
            "content": f"Konteks dokumen:\n{context}\n\nPertanyaan: {question}",
        },
    ]


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


def build_combined_prompt(doc_context: str, sql_result: str, question: str) -> list[dict]:
    """Build messages for combined document + SQL answer synthesis."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT_COMBINED},
        {
            "role": "user",
            "content": (
                f"Konteks dokumen:\n{doc_context}\n\n"
                f"Hasil data:\n{sql_result}\n\n"
                f"Pertanyaan: {question}"
            ),
        },
    ]


def build_router_prompt(question: str) -> list[dict]:
    """Build messages for question classification."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT_ROUTER},
        {"role": "user", "content": question},
    ]
