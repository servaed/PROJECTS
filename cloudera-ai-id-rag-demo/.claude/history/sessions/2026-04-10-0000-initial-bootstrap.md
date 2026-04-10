# Session Log — 2026-04-10 00:00

## Objective
Bootstrap the full `cloudera-ai-id-rag-demo` repository from scratch, following the master prompt specification across all 7 phases.

## Files Changed
- `CLAUDE.md` — created: project memory and working conventions
- `README.md` — created: full project overview, architecture diagram, quick start, demo script
- `requirements.txt` — created: all Python dependencies
- `.env.example` — created: full env var reference
- `.gitignore` — created
- `app/main.py` — created: Streamlit entry point
- `app/ui.py` — created: UI components, sample prompts, answer rendering
- `src/config/settings.py` — created: pydantic-settings configuration
- `src/config/logging.py` — created: logging setup
- `src/llm/base.py` — created: abstract LLM interface
- `src/llm/inference_client.py` — created: Cloudera/OpenAI-compatible client
- `src/llm/prompts.py` — created: Bahasa Indonesia system prompts and templates
- `src/retrieval/document_loader.py` — created: multi-format document loader
- `src/retrieval/chunking.py` — created: text chunker with overlap
- `src/retrieval/embeddings.py` — created: pluggable embeddings provider
- `src/retrieval/vector_store.py` — created: FAISS vector store (persist/load)
- `src/retrieval/retriever.py` — created: similarity search retrieval
- `src/sql/metadata.py` — created: approved table schema discovery
- `src/sql/guardrails.py` — created: SQL validation and blocking
- `src/sql/query_generator.py` — created: natural language to SQL
- `src/sql/executor.py` — created: query execution with timing
- `src/orchestration/router.py` — created: question classification
- `src/orchestration/answer_builder.py` — created: full answer pipeline
- `src/orchestration/citations.py` — created: citation assembler
- `src/connectors/files_adapter.py` — created: local file adapter
- `src/connectors/hdfs_adapter.py` — created: HDFS WebHDFS adapter stub
- `src/connectors/db_adapter.py` — created: SQLAlchemy database adapter
- `src/utils/ids.py` — created: ULID generation
- `src/utils/language.py` — created: language helpers and mode labels
- `data/sample_docs/kebijakan_kredit_umkm.txt` — created: demo policy document
- `data/sample_docs/regulasi_ojk_2025.txt` — created: demo regulation document
- `data/sample_tables/seed_database.py` — created: SQLite demo data seeder
- `data/manifests/sample_manifest.json` — created: ingestion manifest
- `deployment/launch_app.sh` — created: Cloudera AI Application startup script
- `deployment/cloudera_ai_application.md` — created: full deployment guide
- `deployment/app_config.md` — created: env var reference
- `tests/test_sql_guardrails.py` — created: comprehensive SQL guardrail tests
- `tests/test_retrieval.py` — created: chunking and loading tests
- `tests/test_router.py` — created: router classification tests
- `.claude/skills/*/SKILL.md` — created: 6 project skills
- `.claude/skills/session-history/templates/` — created: session and decision log templates
- `.claude/commands/resume.md` — created: /resume command

## Decisions Made
- **UI framework: Streamlit** — fastest path to a demo-ready chat UI, single process, compatible with port 8080
- **Embeddings: multilingual-e5-base** — local, no API key needed, supports Bahasa Indonesia
- **Vector store: FAISS** — demo-appropriate, file-based persistence, no separate service needed
- **SQL safety: allowlist + keyword blocklist** — defense-in-depth; allowlist prevents table discovery, blocklist prevents destructive SQL
- **Language policy: English for code/docs, Bahasa Indonesia for LLM prompts and UI** — confirmed with user

## Unresolved Issues
- [ ] `data/sample_docs/` does not yet have a PDF or DOCX file — only TXT for now
- [ ] HDFS adapter is a stub — needs real testing against a Cloudera cluster
- [ ] No conversation memory across turns (stateless per question) — future enhancement

## Next Steps
1. Seed the SQLite demo database: `python data/sample_tables/seed_database.py`
2. Configure `.env` with a working LLM endpoint
3. Ingest sample docs: `python -m src.retrieval.document_loader`
4. Run the app: `streamlit run app/main.py --server.port 8080`
5. Run tests: `pytest tests/ -v`
6. Customize sample prompts in `app/ui.py` for target customer domain
