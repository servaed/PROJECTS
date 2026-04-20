# Decisions — 2026-04-20: UX & Deploy/Configure Improvements

## Self-host QR code library
**Decision:** Downloaded `qrcode.min.js` (davidshimjs, 19,927 bytes) to `app/static/vendor/`
rather than loading from CDN.

**Why:** Consistent with the project's existing vendor-JS approach (React, htm, DOMPurify all
self-hosted). Cloudera AI Workbench environments may have restricted outbound internet; a CDN
dependency would silently fail in air-gapped deployments.

**Trade-off:** Minor increase in repo size; no version pinning issue since it's pinned by copy.

---

## Use `/health` (not `/api/status`) for fast polling
**Decision:** `maybeStartFastPoll` in `setup.html` fetches `/health`, not `/api/status`.

**Why:** `/api/status` returns `{vector_store:{ok:bool,...}, database:{...}, llm:{...}}` — a
verbose per-component object without `uptime_s`. `/health` returns
`{status, checks:{vector_store, database, llm_configured}, uptime_s}` — compact and already
consumed by the startup banner logic. Using the wrong endpoint caused silent key-access failures.

---

## localStorage over sessionStorage for chat persistence
**Decision:** Migrated from `sessionStorage` to `localStorage` (version bump 2→3).

**Why:** `sessionStorage` is tab-scoped — opening the demo in a new tab for a second audience
member or projector display started fresh with no history. `localStorage` persists across tabs
and page refreshes, which is better for demo continuity. The `_SS_VER` guard ensures old
data doesn't cause deserialization errors.

---

## LLM warm-up with 5s timeout in ThreadPoolExecutor
**Decision:** Warm-up uses `ThreadPoolExecutor(max_workers=1)` + `fut.result(timeout=5)`.

**Why:** LLM warm-up must not block the uvicorn startup or hold an async event loop thread.
A daemon thread + executor ensures the timeout is enforced and failure is non-fatal. Without
the executor, `thread.join(timeout=5)` would still let the thread run past 5s in the background
potentially causing resource leaks.

**Trade-off:** Azure GPT-4.1 can legitimately take >5s for cold model load; the non-critical
log message covers this case gracefully.

---

## Single docker-compose service (no separate service per component)
**Decision:** `docker-compose.yml` defines a single `app` service, not separate services for
MinIO, Nessie, Trino.

**Why:** The Docker image already embeds and starts all three services via `entrypoint.sh`.
Splitting them into separate Compose services would require inter-container networking config
and duplicate the orchestration logic. The single-container model matches how it runs in
Cloudera AI Workbench (one Application container).

---

## Redact secrets in .env download
**Decision:** `exportEnv()` fetches `/api/configure` (which already masks secrets as `***`)
and outputs masked values as `<REDACTED>` in the downloaded `.env`.

**Why:** Downloading real secrets to a client browser risks clipboard or disk exposure. The
download is useful for capturing non-secret settings (provider, model ID, base URL) and
serves as a template the user can complete manually.
