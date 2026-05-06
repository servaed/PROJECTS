# Session — 2026-05-06: Analytics Features, Dashboard, Presentation PDF

## Summary
Two major work streams across this session: (1) new analytics features added to the main chat interface and a new Executive Dashboard page; (2) presentation improvements including a new slide, WCAG contrast fixes, and a PDF download button.

## Work Done

### Stream 1 — Analytics & Dashboard (from previous session context)

**Executive Dashboard (`app/static/dashboard.html`)**
- New page at `GET /dashboard`
- 13 KPI cards: 4 banking (avg NPL, total credit, loan approval rate, avg ROI), 4 telco (avg churn, critical networks, avg latency, avg packet loss), 5 government (budget realization, avg IKM, pending services, total budget, population)
- Streaming LLM executive briefing via SSE (`POST /api/dashboard/summary`)
- Threshold alert feed
- Run Monitoring button → `POST /api/monitor/run` (5 threshold checks, SSE stream)
- Admin topbar consistent with setup.html / configure.html

**Anomaly Detection**
- `POST /api/anomaly`: LLM scans SQL results against industry benchmarks
- `AnomalyPanel` React component auto-appears below SqlPanel for data queries
- Severity: critical (red) / warning (amber) / ok (green)

**Vision Input**
- Image attachment button in InputBar (camera icon)
- Base64 image stored in message state; thumbnail preview shown
- `ChatRequest.image_b64` field on backend
- `_vision_content` attribute injected onto `AnswerPrep` in `_chat_sse`
- `stream_synthesis()` replaces last user message content with vision block

**Line Charts**
- Time-series column detection regex: `/\|\s*(month|year|date|period|quarter|bulan|tahun)\s*\|/i`
- Bezier canvas rendering with gradient fill under the line
- Hover snapping to nearest data point

**Without AI Raw Mode**
- Toggle on assistant messages that have SQL data
- Bypasses LLM synthesis, shows plain result table
- `noai-banner` CSS yellow strip indicator

**Predictive Forecasting**
- `POST /api/forecast`: accepts `{data, labels, periods}`, returns `{forecast, labels, trend, r2}`
- `_linear_regression(x, y)`: pure Python OLS, no scipy dependency
- `_generate_future_labels(labels, n)`: supports month/year/quarter label extension
- `▷ Forecast` button in DataChart; dashed overlay on existing line chart

**Bug Fixes (Dashboard)**
- `api_dashboard_kpis` made sync (not async) to avoid DuckDB threading deadlock with concurrent.futures
- Sequential queries instead of parallel — DuckDB single-connection thread safety
- Dict-aware row extraction: `isinstance(first, dict) → next(iter(first.values()))` — fixes all-None KPI values
- Same fix applied to monitor SSE row extraction

### Stream 2 — Presentation (this session)

**Slide T-07: Live Demo Guide**
- New technical slide (s16, `data-tech="1"`) 
- 3×2 grid of cards: Chat Interface, Executive Dashboard, Data Explorer, Document Intelligence, Inference Metrics, Setup & Config
- Each card has page URL, icon, and bulleted capability list
- JS dynamically renumbers slides (total 16 in tech mode, 9 in business mode)

**PDF Download**
- Download icon button at `top:16px; right:20px`
- Theme button shifted to `right:64px`; audience toggle to `right:112px`
- `downloadPDF()` JS: opens `window.open()` new window with copied `<style>` content + `data-theme`
- Clones all audience-filtered slides; uses `el.style.opacity = '1'` (not cssText+!important) to reset anim-* opacity
- `@page { size: A4 landscape; margin: 0 }` + `print-color-adjust: exact` in print overrides
- `pw.onload` triggers `pw.print()`; 800ms fallback
- `P` keyboard shortcut added
- kbd-hint updated: "← → navigate · F fullscreen · P save PDF · ← Back to app"

**WCAG AA Contrast Fixes**
- Dark mode `--t3`: #475569 → #8892A4 (was ~2.28:1, now ~5.9:1 on dark bg)
- Light mode `--t3`: #9AA0A6 → #6B7280 (was ~2.5:1, now ~4.67:1 on light bg)
- Light mode `--t2`: #4A5568 → #374151 (slightly darker for comfort)

**Cover Slide Branding**
- Logo-only in top bar (no wordmark)
- Lead paragraph: "Cloudera AI Enterprise Assistant — One question, multiple angles. Policy documents, live data, geographic maps, and trend forecasts. Breaks complex enterprise data into clear, actionable light."

## Decisions

### PDF download via new window, not @media print CSS
CSS-based print was unreliable due to:
1. `position: absolute` slides not re-flowing to `relative` correctly in Chrome's print engine
2. `.anim-*` classes hardcode `opacity: 0` as base style; `cssText += '!important'` is invalid in inline styles
The new-window approach gives a clean DOM with proper block flow and explicit opacity resets.

### DuckDB sequential queries for dashboard
`concurrent.futures.ThreadPoolExecutor` caused deadlocks with DuckDB's single-connection model.
Made `api_dashboard_kpis` a sync function (FastAPI auto-runs in thread pool) with sequential `_run_kpi_query` calls.

## Files Changed
- `app/api.py` — forecast, anomaly, dashboard/kpis, dashboard/summary, monitor/run endpoints; DuckDB fix
- `app/static/index.html` — AnomalyPanel, LineChart, ForecastOverlay, Without AI mode, Vision input
- `app/static/dashboard.html` — new file
- `app/static/presentation.html` — T-07 slide, PDF download, WCAG fixes, cover tagline
- `src/orchestration/answer_builder.py` — vision_content injection in stream_synthesis()
