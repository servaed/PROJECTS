#!/usr/bin/env python3
"""
RAG Demo - Full SSE test runner
Tests all sample questions across 3 domains x 2 languages
"""
import subprocess, json, sys

BASE_URL = "http://localhost:8080"

SAMPLES = {
    "banking": {
        "id": [
            {"text": "Apa saja syarat pengajuan kredit UMKM dan dokumen yang wajib dilengkapi?", "mode": "dokumen"},
            {"text": "Bagaimana prosedur restrukturisasi kredit jika debitur mengalami kesulitan pembayaran?", "mode": "dokumen"},
            {"text": "Berapa total outstanding kredit UMKM di Jakarta per Maret 2026?", "mode": "data"},
            {"text": "Tampilkan 5 nasabah dengan total eksposur kredit tertinggi.", "mode": "data"},
            {"text": "Apakah outstanding kredit UMKM di Jakarta sudah sesuai target ekspansi 15% yang ditetapkan kebijakan 2026?", "mode": "gabungan"},
            {"text": "Bagaimana kualitas kredit di Bandung dibandingkan kondisi yang memenuhi syarat restrukturisasi menurut kebijakan bank?", "mode": "gabungan"},
        ],
        "en": [
            {"text": "What are the MSME credit requirements and mandatory documents?", "mode": "dokumen"},
            {"text": "What is the credit restructuring procedure when a debtor has payment difficulties?", "mode": "dokumen"},
            {"text": "What is the total outstanding MSME credit in Jakarta as of March 2026?", "mode": "data"},
            {"text": "Show the top 5 customers by total credit exposure.", "mode": "data"},
            {"text": "Does the Jakarta MSME credit outstanding align with the 15% expansion target set by the 2026 policy?", "mode": "gabungan"},
            {"text": "How does Bandung's credit quality compare to the restructuring eligibility conditions per bank policy?", "mode": "gabungan"},
        ],
    },
    "telco": {
        "id": [
            {"text": "Apa saja standar waktu penanganan keluhan pelanggan yang ditetapkan dalam SLA?", "mode": "dokumen"},
            {"text": "Bagaimana kebijakan retensi pelanggan dan syarat mendapatkan diskon perpanjangan kontrak?", "mode": "dokumen"},
            {"text": "Tampilkan utilisasi jaringan per wilayah dan identifikasi wilayah yang mendekati kapasitas kritis.", "mode": "data"},
            {"text": "Berapa pelanggan dengan churn risk score di atas 70 dan di wilayah mana saja?", "mode": "data"},
            {"text": "Apakah utilisasi jaringan di Bali sudah melampaui batas SLA ketersediaan yang ditetapkan dalam kebijakan?", "mode": "gabungan"},
            {"text": "Pelanggan mana yang berisiko churn tinggi dan apakah mereka memenuhi syarat program retensi berdasarkan kebijakan?", "mode": "gabungan"},
        ],
        "en": [
            {"text": "What are the customer complaint resolution time standards defined in the SLA?", "mode": "dokumen"},
            {"text": "What is the customer retention policy and the conditions for contract renewal discounts?", "mode": "dokumen"},
            {"text": "Show network utilization by region and identify areas approaching critical capacity.", "mode": "data"},
            {"text": "How many subscribers have a churn risk score above 70 and in which regions?", "mode": "data"},
            {"text": "Has network utilization in Bali exceeded the availability SLA threshold defined in the policy?", "mode": "gabungan"},
            {"text": "Which high-churn-risk subscribers qualify for the retention program based on the policy criteria?", "mode": "gabungan"},
        ],
    },
    "government": {
        "id": [
            {"text": "Berapa standar waktu penyelesaian layanan KTP elektronik dan apa kompensasi jika terlambat?", "mode": "dokumen"},
            {"text": "Apa saja kanal pengaduan yang tersedia dan bagaimana prosedur penanganannya?", "mode": "dokumen"},
            {"text": "Tampilkan realisasi anggaran per satuan kerja dan identifikasi yang realisasinya di bawah target.", "mode": "data"},
            {"text": "Layanan publik mana yang memiliki tingkat kepuasan masyarakat terendah per Maret 2026?", "mode": "data"},
            {"text": "Apakah layanan IMB sudah memenuhi standar waktu dan IKM yang ditetapkan dalam kebijakan pelayanan publik?", "mode": "gabungan"},
            {"text": "Satuan kerja mana yang realisasi anggarannya rendah dan apakah ada risiko penalti sesuai regulasi APBD?", "mode": "gabungan"},
        ],
        "en": [
            {"text": "What is the processing time standard for electronic ID cards and what compensation is given for delays?", "mode": "dokumen"},
            {"text": "What complaint channels are available and what is the handling procedure?", "mode": "dokumen"},
            {"text": "Show budget realization per work unit and identify those below target.", "mode": "data"},
            {"text": "Which public services have the lowest citizen satisfaction rate as of March 2026?", "mode": "data"},
            {"text": "Does the building permit (IMB) service meet the processing time and satisfaction standards set by the public service policy?", "mode": "gabungan"},
            {"text": "Which work units have low budget realization and face penalty risk under the APBD regulation?", "mode": "gabungan"},
        ],
    },
}


def parse_sse(raw: str) -> dict:
    """Parse SSE stream into structured result."""
    mode = None
    tokens = []
    citations = []
    has_sql = False
    done_data = None

    current_event = None
    current_data_lines = []

    for line in raw.split('\n'):
        line = line.rstrip('\r')
        if line.startswith('event:'):
            current_event = line[6:].strip()
            current_data_lines = []
        elif line.startswith('data:'):
            current_data_lines.append(line[5:].strip())
        elif line == '':
            if current_event and current_data_lines:
                data_str = '\n'.join(current_data_lines)
                try:
                    data = json.loads(data_str)
                except Exception:
                    data = data_str

                if current_event == 'mode':
                    mode = data.get('mode') if isinstance(data, dict) else str(data)
                elif current_event == 'token':
                    t = None
                    if isinstance(data, dict):
                        t = data.get('text') or data.get('token')
                    elif isinstance(data, str):
                        t = data
                    if t:
                        tokens.append(t)
                elif current_event == 'done':
                    done_data = data
                    if isinstance(data, dict):
                        # Citations may be in doc_citations or citations
                        citations = data.get('citations') or data.get('doc_citations', [])
                        if data.get('sql_citation'):
                            has_sql = True
                elif current_event == 'sql':
                    has_sql = True
                elif current_event == 'error':
                    pass
            current_event = None
            current_data_lines = []

    answer = ''.join(tokens)
    return {
        'mode': mode,
        'answer': answer,
        'answer_len': len(answer),
        'citations': len(citations),
        'has_sql': has_sql,
    }


def call_chat(question: str, domain: str) -> dict:
    """Call the chat API and parse SSE response."""
    payload = json.dumps({
        "question": question,
        "history": [],
        "domain": domain
    })
    try:
        result = subprocess.run(
            ['curl', '-N', '-s', '--max-time', '60', '-X', 'POST',
             f'{BASE_URL}/api/chat',
             '-H', 'Content-Type: application/json',
             '-d', payload],
            capture_output=True,
            timeout=65
        )
        raw = result.stdout.decode('utf-8', errors='replace')
        if not raw:
            return {'mode': 'ERROR', 'answer': '', 'answer_len': 0, 'citations': 0, 'has_sql': False}
        return parse_sse(raw)
    except subprocess.TimeoutExpired:
        return {'mode': 'TIMEOUT', 'answer': '', 'answer_len': 0, 'citations': 0, 'has_sql': False}
    except Exception as e:
        return {'mode': f'ERROR:{e}', 'answer': '', 'answer_len': 0, 'citations': 0, 'has_sql': False}


def evaluate(result: dict, expected_mode: str, lang: str) -> tuple:
    """
    Returns (quality_label, notes_list)
    quality: Good / Partial / Failed
    """
    notes = []
    actual_mode = result['mode']
    answer_len = result['answer_len']
    citations = result['citations']
    has_sql = result['has_sql']

    # Check routing
    if actual_mode == expected_mode:
        routing_ok = True
    elif actual_mode in ('ERROR', 'TIMEOUT', None):
        routing_ok = False
        notes.append(f"No mode received ({actual_mode})")
    else:
        routing_ok = False
        notes.append(f"Routing mismatch: expected {expected_mode}, got {actual_mode}")

    # Check answer quality
    if answer_len == 0:
        quality = "Failed"
        notes.append("Empty answer")
    elif answer_len < 50:
        quality = "Partial"
        notes.append(f"Very short answer ({answer_len} chars)")
    else:
        # Check for fallback/not-found patterns
        answer_lower = result['answer'].lower()
        fallback_phrases = [
            'tidak ditemukan', 'not found', 'maaf', 'tidak tersedia',
            'tidak ada informasi', 'no information', 'sorry', 'unable to find'
        ]
        if any(p in answer_lower for p in fallback_phrases):
            quality = "Partial"
            notes.append("Answer contains fallback/not-found language")
        else:
            quality = "Good"

    # Check citations for dokumen/gabungan
    if expected_mode in ('dokumen', 'gabungan'):
        if citations == 0:
            notes.append("No document citations returned")
            if quality == "Good":
                quality = "Partial"

    # Check SQL for data/gabungan
    if expected_mode in ('data', 'gabungan'):
        if not has_sql:
            notes.append("No SQL citation found")

    # Routing mismatch is a critical issue
    if not routing_ok and actual_mode not in ('ERROR', 'TIMEOUT'):
        if quality == "Good":
            quality = "Partial"

    if not notes:
        notes.append("OK")

    return quality, notes


def main():
    results = []
    total = sum(len(qs) for domain in SAMPLES.values() for qs in domain.values())
    count = 0

    for domain, langs in SAMPLES.items():
        for lang, questions in langs.items():
            for q in questions:
                count += 1
                question_text = q['text']
                expected_mode = q['mode']
                print(f"[{count}/{total}] {domain}/{lang} [{expected_mode}]: {question_text[:60]}...", file=sys.stderr)

                result = call_chat(question_text, domain)
                quality, notes = evaluate(result, expected_mode, lang)

                row = {
                    'domain': domain,
                    'lang': lang,
                    'question': question_text,
                    'expected_mode': expected_mode,
                    'actual_mode': result['mode'],
                    'answer_len': result['answer_len'],
                    'citations': result['citations'],
                    'has_sql': result['has_sql'],
                    'quality': quality,
                    'notes': '; '.join(notes),
                    'answer_preview': result['answer'][:150].replace('\n', ' '),
                }
                results.append(row)
                print(f"    -> mode={result['mode']}, quality={quality}, ans_len={result['answer_len']}, cit={result['citations']}, sql={result['has_sql']}", file=sys.stderr)
                print(f"    -> notes: {'; '.join(notes)}", file=sys.stderr)

    # Output JSON
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
