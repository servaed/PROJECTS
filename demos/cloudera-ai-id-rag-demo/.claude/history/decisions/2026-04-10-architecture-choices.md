# Decision Log — 2026-04-10: Core Architecture Choices

## Context
Building a Bahasa Indonesia enterprise RAG assistant for Cloudera AI Applications. Need a deployable demo that works locally in dev mode and can be wired to enterprise systems for actual presales demos.

---

## Decision 1: UI Framework

### Options Considered
1. **Streamlit** — single-file chat UI, runs as one process, minimal boilerplate
2. **Gradio** — similar to Streamlit, but less flexible for custom layouts
3. **FastAPI + React** — full flexibility, but requires significant frontend work

### Chosen Option
**Streamlit**

### Rationale
Demo timeline favors Streamlit. It produces a professional-looking chat UI, handles session state natively, runs on a single port (8080), and is deployable directly as a Cloudera AI Application without a build step. Gradio was rejected because it has less control over layout. FastAPI+React was rejected as over-engineering for a presales demo.

### Impact
- `app/main.py`, `app/ui.py` are Streamlit files
- `deployment/launch_app.sh` uses `streamlit run`

---

## Decision 2: Embeddings Provider Default

### Options Considered
1. **sentence-transformers (local)** — no API key, runs on CPU, supports multilingual
2. **OpenAI text-embedding-3-small** — better quality, requires API key and internet
3. **Cloudera AI Inference embeddings** — enterprise-aligned, requires a deployed model

### Chosen Option
**sentence-transformers with `intfloat/multilingual-e5-base`**

### Rationale
Demo must work offline and without customer API keys. `multilingual-e5-base` has strong Bahasa Indonesia support. Abstraction layer in `src/retrieval/embeddings.py` allows swapping to OpenAI or Cloudera embeddings with a single env var change.

### Impact
- `EMBEDDINGS_PROVIDER=local` is the default
- `src/retrieval/embeddings.py` has the provider switch

---

## Decision 3: SQL Safety Architecture

### Options Considered
1. **Allowlist + keyword blocklist** — defense-in-depth, blocks both by table name and by keyword
2. **Keyword blocklist only** — simpler, but allows table discovery
3. **Semantic layer only** — cleanest, but requires customer to have a semantic layer

### Chosen Option
**Allowlist + keyword blocklist**

### Rationale
Allowlist prevents the LLM from discovering or querying tables not intended for the demo. Keyword blocklist is a second layer preventing destructive SQL even if the allowlist is misconfigured. This combination is simple to explain to enterprise customers as a security control.

### Impact
- `src/sql/guardrails.py` implements both layers
- `SQL_APPROVED_TABLES` env var controls the allowlist
- Tests in `tests/test_sql_guardrails.py` verify all blocked patterns

---

## Decision 4: Language Policy

### Options Considered
1. **Everything in Bahasa Indonesia** — fully localized, harder to maintain
2. **Everything in English** — standard, but poor demo experience for Indonesian customers
3. **English for code/docs, Bahasa Indonesia for LLM prompts and UI** — clean separation

### Chosen Option
**English for all code, comments, and documentation; Bahasa Indonesia only for LLM prompts sent to the model and user-facing UI strings**

### Rationale
Confirmed with the user. Code in English is maintainable by any engineer. Bahasa Indonesia in LLM prompts ensures the model answers in the right language. UI strings in Bahasa Indonesia make the demo authentic for Indonesian customers.

### Impact
- `src/llm/prompts.py` — system prompts and templates in Bahasa Indonesia
- `app/ui.py` — all user-visible labels in Bahasa Indonesia
- All docstrings, comments, and documentation in English
