# Session: Demo UX & Deploy/Configure Improvements
**Date:** 2026-04-20  
**Topics:** 9 demo UX seamlessness improvements + 10 deploy/configure improvements

## What was done

### Session 1 — Demo UX (continued from prior context)
Resumed from a prior session that was compacted. Implemented remaining UX improvements:

1. **LLM warm-up** — daemon thread in `lifespan()` before `yield`; 5s timeout via `ThreadPoolExecutor`
2. **Auto-play pause/resume** — `autoPausedRef` + `pausedAtIdxRef` + `playNextRef`; sidebar shows ⏸/▶/⏹ buttons
3. **localStorage v3** — replaced all `sessionStorage` refs; bumped `_SS_VER` 2→3
4. **Latency badge** — `t0 = Date.now()` before submit, `⚡ X.Xs` badge on assistant message
5. **Full reset** — `↺ Reset Demo` button in sidebar footer; resets domain, language, history, localStorage
6. **Keyboard shortcuts** — Ctrl+Shift+D (demo), Ctrl+K (clear), Ctrl+Shift+R (full reset), Escape (stop)
7. **Domain-aware welcome** — icon + name + description + 3 clickable sample prompts
8. **DataChart** — Canvas bar chart for SQL results with 2–12 rows using `ctx.roundRect()`
9. **Setup overlay** — full-screen on first launch when LLM not configured; dismiss via sessionStorage

### Session 2 — Deploy/Configure (10 improvements)
User asked: "make my demo easiest to deploy anywhere and also easiest to configure"
User approved: "Implement everything"

1. **Makefile** — `make dev`, `make docker`, `make test`, etc.
2. **docker-compose.yml** — single-container, named volumes, healthcheck, resource limits
3. **GitHub Actions** — `.github/workflows/docker-build.yml` → GHCR push on main/semver tags
4. **Fast polling** — `/setup` polls `/health` every 5s for first 120s; pulsing startup banner
5. **Inline Test LLM** — `testLlm()` in configure.html; shows provider/model/latency inline
6. **Setup overlay** — (same as P1 item 9)
7. **Model ID datalists** — 6 `<datalist>` elements; `updateModelDatalist()` on provider change
8. **.env download** — `exportEnv()` generates and triggers browser download (secrets redacted)
9. **Log viewer** — already existed; verified working at `/setup`
10. **QR code** — self-hosted `qrcode.min.js`; popup in `/setup` topbar pointing to app root

## Files modified
- `app/api.py` — LLM warm-up thread, `_STARTUP_TIME`, `uptime_s` in `/health` response
- `app/static/index.html` — all 9 UX improvements + setup overlay
- `app/static/configure.html` — datalists, Test LLM, .env download, action bar
- `app/static/setup.html` — QR popup, startup banner, fast polling via `/health`
- `app/static/vendor/qrcode.min.js` — new (self-hosted, 19,927 bytes)
- `Makefile` — new
- `docker-compose.yml` — new
- `.github/workflows/docker-build.yml` — new

## Key debugging
- Windows `pkill` silently does nothing — use Python `subprocess.run(['taskkill', '/PID', '...', '/F'])`
- `/api/status` vs `/health` structure: fast-poll must use `/health` (has `checks.*` + `uptime_s`)
- LLM warm-up logged "OK" in ~3s for Azure GPT-4.1; caught cleanly if timeout exceeded

## Verification
All features confirmed in served HTML:
- `/health` → `{"status":"ok","checks":{...},"uptime_s":N}`
- `/setup` → `qr-wrap`, `startupBanner`, `maybeStartFastPoll`, `/health` references
- `/configure` → `testResult`, `datalist`, `exportEnv`, `testLlm`, `Download`
- `/` → `setup-overlay`, `SetupOverlay`, `_SS_VER = 3`, `localStorage`
- `Makefile`, `docker-compose.yml`, `.github/workflows/docker-build.yml` all present
