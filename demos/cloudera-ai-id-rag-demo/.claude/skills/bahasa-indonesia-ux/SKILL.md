---
name: bahasa-indonesia-ux
description: Rules for bilingual UX — LLM prompts in Bahasa Indonesia, UI strings in English, tone, bilingual schema handling, and fallback behavior.
---

# Skill: Bilingual UX (Bahasa Indonesia + English)

## Language Policy (as of 2026-04-22)

| Component | Language |
|-----------|----------|
| LLM system prompts | Bahasa Indonesia (with `{lang_rule}` placeholder) |
| LLM user prompts sent to model | Bahasa Indonesia (internal framing only) |
| Final LLM answers | Matches user's input language (ID or EN) |
| UI labels, buttons, headers | **English** |
| Error messages shown to user | **English** |
| Fallback strings (not_found, sql_failed) | Localised — ID or EN via `get_answer_not_found(language)` |
| Sample prompts in sidebar | Bilingual — `text_id` (Indonesian) and `text_en` (English) |
| Code, docstrings, comments | English |
| Documentation (README, CLAUDE.md) | English |
| Schema names, table names, column names | English (technical labels) |
| Status/segment values in data (e.g. Active, Micro) | English |
| Domain-authentic codes (e.g. Lancar, DPK, Macet) | Indonesian (OJK standard) |
| Indonesian government agency names | Indonesian (official names) |
| SQL queries | English (SQL dialect) |

## Tone for Enterprise Demos

- Formal (Anda, bukan kamu) in Indonesian responses
- Concise — no filler phrases
- Factual — cite sources, no speculation
- Avoid casual or colloquial expressions

## Bilingual Handling

The `ChatRequest.language` field (`"id"` or `"en"`) is sent from the frontend and
threaded through to all prompt builders. The LLM system prompt uses the `{lang_rule}`
placeholder which resolves to:
- `"id"`: "Jawablah dalam Bahasa Indonesia."
- `"en"`: "Answer in English."

The LLM system prompt explicitly allows English table/column names:
> "Nama skema, tabel, dan kolom boleh tetap dalam bahasa Inggris."

## Fallback Messages

These are bilingual and resolved at runtime via `prompts.py`:

| Function | When used |
|----------|-----------|
| `get_answer_not_found(language)` | No relevant documents found |
| `get_answer_sql_failed(language)` | SQL query failed or returned empty |
| `ANSWER_AMBIGUOUS_ID` | Question too vague (ID only, internal) |

## Answer Mode Badges

Rendered in the React SPA (`index.html`) as colored badges:

| Mode | Label | Color |
|------|-------|-------|
| `dokumen` | Document | Blue |
| `data` | Structured Data | Green |
| `gabungan` | Combined | Orange |

## Sample Prompts

Sample prompts are defined in `app/api.py` `SAMPLE_PROMPTS` and exposed via `GET /api/samples`.
Each prompt has `text_id` (Bahasa Indonesia) and `text_en` (English) fields.
The frontend sends whichever matches the active language toggle.

## Document Knowledge Base

14 source documents (7 Indonesian + 7 English). Language detected from filename:
- Files ending in `_en.txt` → `language="en"`
- All others → `language="id"`

Retrieval filters by `language` so a user in EN mode never sees Indonesian chunks.
