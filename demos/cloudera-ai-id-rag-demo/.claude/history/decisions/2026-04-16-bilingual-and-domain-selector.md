# Decision — 2026-04-16: Bilingual and Domain Selector Architecture

## Bilingual: language injection via {lang_rule} placeholder

**Decision**: Instead of maintaining separate Indonesian and English system prompts,
inject a single `{lang_rule}` line into each system prompt at runtime based on the
`language` parameter from the request.

**Rationale**: The system prompts are internal directives, not user-facing text.
They can stay in Indonesian. Only the *response language instruction* needs to be
language-switched. A single placeholder keeps the prompts DRY and avoids a combinatorial
explosion of prompt variants.

**Implementation**: `_lang_rule("id")` → "Jawab selalu dalam Bahasa Indonesia yang formal
dan ringkas." `_lang_rule("en")` → "Always respond in formal, concise English."

## Domain selector: sidebar over topbar

**Decision**: Move domain and language controls from the topbar to the sidebar.

**Rationale**: The topbar was already crowded (logo, title, configure link, reset, theme toggle).
Domain and language are contextual settings that belong near the sample prompts they affect.
The sidebar provides more space and visual grouping.

**Implementation**: Sidebar tabs with emoji icons (🏦📡🏛) + short labels. Active state:
orange border + `var(--o-dim)` background. Language: full-label toggle below domain tabs.

## Document corpus: domain-segregated subdirectories

**Decision**: Store documents in `data/sample_docs/<domain>/` rather than a flat directory.

**Rationale**: Enables per-domain retrieval filtering without relying on filename prefixes.
Each document chunk is tagged with `domain` at ingest time; the retriever filters by domain.
Subdirectory structure also makes the corpus easier to extend without namespace collisions.

## Seed data: add temporal dimension

**Decision**: Add multi-month time series to kredit_umkm, penggunaan_data, anggaran_daerah,
and layanan_publik tables (2–4 months each).

**Rationale**: Presales queries often ask "per bulan" or compare periods. Flat single-period
data forces SQL to return trivial results. Multi-period data enables richer aggregation,
trend, and period-comparison queries.

## Number formatting in SQL results

**Decision**: Pre-format all numeric DataFrame columns in `executor.py` before `to_markdown()`.

**Rationale**: pandas `to_markdown()` renders large floats as scientific notation (2.368e+10).
Pre-formatting integers with `:,` and floats as `:.2f` produces human-readable IDR values
(23,680,000,000) that the LLM can quote correctly in its answer.
