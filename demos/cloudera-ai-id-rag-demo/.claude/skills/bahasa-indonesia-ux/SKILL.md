---
name: bahasa-indonesia-ux
description: Rules for Bahasa Indonesia UX — LLM prompts, UI strings, tone, bilingual schema handling, and fallback behavior.
---

# Skill: Bahasa Indonesia UX

## Rule: What Must Be in Bahasa Indonesia

| Component | Language |
|-----------|----------|
| LLM system prompts | Bahasa Indonesia |
| LLM user prompts sent to model | Bahasa Indonesia |
| Final LLM answers | Bahasa Indonesia |
| UI labels, buttons, headers | Bahasa Indonesia |
| Error messages shown to user | Bahasa Indonesia |
| Sample prompts in sidebar | Bahasa Indonesia |
| Code, docstrings, comments | English |
| Documentation (README, CLAUDE.md) | English |
| Schema names, table names, column names | English (technical labels) |
| SQL queries | English (SQL is a technical language) |

## Tone for Enterprise Demos

- Formal (Anda, bukan kamu)
- Concise — no filler phrases
- Factual — cite sources, no speculation
- Avoid casual or colloquial expressions

## Fallback Messages

These strings are defined in `src/llm/prompts.py` and must remain in Bahasa Indonesia:

| Variable | When used |
|----------|-----------|
| `ANSWER_NOT_FOUND_ID` | No relevant documents found |
| `ANSWER_AMBIGUOUS_ID` | Question is too vague |
| `ANSWER_SQL_FAILED_ID` | SQL query failed or returned empty |

## Bilingual Handling

The LLM system prompt explicitly tells the model:
> "Nama skema, tabel, dan kolom boleh tetap dalam bahasa Inggris."

This allows the LLM to produce answers like:
> "Berdasarkan data tabel `kredit_umkm`, total outstanding UMKM Jakarta adalah Rp 18,07 miliar."

## Answer Mode Badges

Rendered in `app/ui.py` as colored HTML badges:

| Mode | Label | Color |
|------|-------|-------|
| `dokumen` | Dokumen | Blue |
| `data` | Data Terstruktur | Green |
| `gabungan` | Gabungan | Orange |

## Sample Prompts

Five canonical demo prompts are defined in `app/ui.py` under `SAMPLE_PROMPTS`. Update them to match the customer's actual data domain before a presales demo.
