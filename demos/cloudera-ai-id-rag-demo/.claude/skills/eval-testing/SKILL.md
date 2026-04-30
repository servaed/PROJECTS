---
name: eval-testing
description: Running the test suite (86 pytest tests) and full evaluation (36 bilingual questions + 10 multi-turn scenarios) against the running app. Makefile targets and interpretation.
---

# Skill: Evaluation & Testing

## Test Suite (pytest — 86 tests)

```bash
# Run all tests
pytest tests/ -v

# Via Makefile
make test          # same as pytest tests/ -v
make test-fast     # pytest -x (stop on first failure)
```

### Test Suites

| File | Tests | What it covers |
|------|-------|---------------|
| `test_sql_guardrails.py` | 30 | SQL injection, subquery bypass, CTE tricks, table allowlist enforcement, LIMIT rewriting |
| `test_router.py` | 12 | Classification accuracy (document/data/combined), alias mapping, LLM fallback, error recovery |
| `test_retrieval.py` | 17 | Chunking with overlap, citation building, deduplication, mocked FAISS store |
| `test_api.py` | 27 | FastAPI endpoint shapes, SSE stream events (mode/token/done), health/status response schemas |

### Important notes
- Tests use mocked LLM responses — they verify **code correctness**, not model quality
- `test_api.py` uses `TestClient` — no running server needed
- Never mock the database in these tests (lesson from a prior incident: mock/prod divergence hid a broken migration)

## Full Evaluation (eval_all.py)

Runs against the **live running app**. Start the app first (`make dev` or uvicorn).

```bash
python eval_all.py

# Via Makefile
make eval
```

### What it tests
- **36 single-turn questions** — bilingual (ID + EN), all three domains, all three modes
- **10 multi-turn scenarios** — follow-ups, drill-downs, pronoun resolution across turns
- Reports per-question pass/fail + grand total score

### Interpreting results
- A question passes if: the response contains the expected keywords/values AND no error markers
- Multi-turn passes if: the follow-up correctly resolves context from the prior turn
- Grand total reported at end: `X / 46 passed`

### Running a subset
```bash
# Only banking domain questions
python eval_all.py --domain banking

# Only Indonesian questions
python eval_all.py --lang id

# Verbose (show full LLM response per question)
python eval_all.py --verbose
```

## Makefile Targets

```bash
make dev           # pip install + seed Parquet + start uvicorn (hot-reload)
make seed          # seed Parquet files only (idempotent)
make demo-reset    # full factory reset: clear VS + reseed + reingest
make reingest      # rebuild FAISS vector store only
make test          # pytest tests/ -v
make test-fast     # pytest -x
make eval          # run eval_all.py against running server
make reset-vs      # delete data/vector_store/ only
```

## When Tests Are Not Enough

Type checking and test suites verify code correctness, not feature correctness. For UI or chat behavior changes:
1. Start the app with `make dev`
2. Test the golden path manually in the browser
3. Test edge cases: empty results, guardrail rejections, language switching, All-Domains mode
4. Monitor for regressions in other features (auto-play, domain selector, sidebar status)

## Adding New Tests

- SQL guardrail tests: `tests/test_sql_guardrails.py` — add cases for new blocked patterns or table allowlist changes
- Router tests: `tests/test_router.py` — add cases when adding new heuristic tiers
- API tests: `tests/test_api.py` — add cases for new endpoints following the existing `TestClient` pattern
- Always run `make test-fast` after adding tests to catch failures quickly
