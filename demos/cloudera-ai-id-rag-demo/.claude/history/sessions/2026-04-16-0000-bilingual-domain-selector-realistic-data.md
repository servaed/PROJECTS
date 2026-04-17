# Session — 2026-04-16: Bilingual, Domain Selector, Realistic Data

## Objectives
- P0: Enhance sample documents and seed data to be realistic and demo-ready
- P0: Add domain selector to sidebar (Banking / Telco / Government tabs)
- P1: Bilingual response support — LLM replies in same language as user question

## Work Completed

### 1. Document corpus (10 files, 90 chunks)
All documents in domain-segregated subdirectories (`data/sample_docs/<domain>/`).

Banking documents enhanced with specific targets (15% YoY, NPL ≤3.5%), POJK references,
CKPN rates, KYC risk tiers, and PPATK thresholds that align with sample questions.

Telco documents written from scratch with P1–P4 SLA tiers, churn risk scoring (≥70 = high,
≥85 = very high), retention eligibility criteria (12+ months tenure + score ≥70), and
spectrum utilisation thresholds (70/85/95%) matching the jaringan table values.

Government documents written from scratch with processing times per service (KTP 3 days,
IMB 14 days), IKM target 82.0, and APBD penalty rules (realisasi <75% at year-end triggers
pagu cut 2× the shortfall) matching the anggaran_daerah and layanan_publik tables.

### 2. Seed database (9 tables, 148+ rows)
Major additions:
- `kredit_umkm`: 45 rows covering 2025-12 to 2026-03, 10 cities
- `cabang`: expanded to 14 with target vs realisasi columns (enables gabungan queries)
- `nasabah`: 15 rows with `rating_internal` and `tanggal_onboard`
- `pelanggan`: 20 rows with `arpu_monthly`
- `penggunaan_data`: 30 rows, 3-month history
- `jaringan`: 15 rows including Malang (Tinggi) and Bekasi (Tinggi) for richer analysis
- `anggaran_daerah`: 26 rows with TW1/TW2/TW3 — enables trend and period queries
- `layanan_publik`: 23 rows with 3-month history, Paspor and BPJS service types added

### 3. Domain selector in sidebar
Removed domain dropdown and language toggle from the topbar (less clutter).
Added to sidebar:
- Three domain tabs with emoji icons and short labels (Banking/Telco/Gov)
- Active tab has orange border + dim background
- Language toggle below: full "Bahasa Indonesia" / "English" labels
- `onDomainChange` and `onLanguageChange` callbacks wired from `App` to `Sidebar`

### 4. Bilingual response support
Language flows: `ChatRequest.language` → `_chat_sse(language)` → `prepare_answer(language)` → `AnswerPrep.language` → `_build_messages(prep)` → prompt builders.

System prompts no longer hard-code "Jawab selalu dalam Bahasa Indonesia". Instead each
prompt has a `{lang_rule}` placeholder filled by `_lang_rule(language)` at call time.

Fallback messages also localised: `get_answer_not_found("en")` returns English text.

Verified: English question → English answer (tested via direct POST to /api/chat with `"language": "en"`).

### 5. Documentation
Full refresh of all 5 MD files: README, DEPLOYMENT, CLAUDE.md, deployment/app_config.md,
deployment/cloudera_ai_application.md. All now reflect e5-large, 9-table schema, bilingual,
domain selector, and realistic data.

## Eval Result
36/36 passing — all 6 domains × languages × modes correct.

## Key Decisions
- See `decisions/2026-04-16-bilingual-and-domain-selector.md`
