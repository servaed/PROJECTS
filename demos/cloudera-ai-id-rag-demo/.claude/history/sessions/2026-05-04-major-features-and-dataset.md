# Session: Major Features — Maps, AI Modes, Dataset Enrichment
**Date:** 2026-05-04  
**Duration:** Long session (multi-context)

---

## Features Delivered

### 1. Indonesia Heatmap / Map Visualization
- Leaflet 1.9.4 downloaded to `app/static/vendor/` (offline-safe, no CDN)
- `MapChart` React component: bubble map with teal→orange→red color encoding, city+province coordinate lookup, tooltips showing all result columns, Low→High legend
- Auto-detection: any SQL result with `city | region | province | kota | provinsi | wilayah` column + ≤50 rows auto-selects Map view
- `DataChart` now supports Map / Bar / Table tabs; Map auto-selected for geo data
- Fixed `SqlPanel` row limit: was `≤12` rows for chart; now `≤12 for bar, ≤50 for map`
- `_CITY_COORDS` covers 27 cities + 24 province centers

**Files changed:** `index.html`, `app/api.py` (SQL prompt examples)

### 2. Reasoning Mode (Think Toggle)
- `_ThinkingFilter.feed()` now returns `(visible_text, thinking_text)` tuple — captures CoT separately
- `ChatRequest.thinking: bool = False` — opt-in per request
- Backend emits `thinking_token` SSE events when enabled
- `ThinkingPanel` component: collapsible, auto-opens during thinking, shows word count when done
- Think toggle button (teal) added to InputBar alongside Agent toggle

**Files changed:** `app/api.py`, `index.html`

### 3. AI Debate Mode (Researcher + Critic)
- `_debate_sse` async generator: Researcher gathers evidence → Critic streams challenges → Synthesis streams final answer
- `POST /api/debate/chat` endpoint
- `DebatePanel` component: Researcher card (teal), Critic card (orange), Synthesis row (indigo)
- Debate toggle button (orange) added to InputBar
- New SSE events: `debate_researcher_done`, `debate_critic_start`, `debate_critic_token`, `debate_synthesis_start`
- New reducer cases: `DEBATE_ASSISTANT`, `DEBATE_RESEARCHER_DONE`, `DEBATE_CRITIC_START`, `DEBATE_CRITIC_TOKEN`, `DEBATE_SYNTH_START`

**Files changed:** `app/api.py`, `index.html`

### 4. Document Intelligence (PDF Table Extraction)
- `pdfplumber>=0.11.0` added to `requirements.txt`, confirmed installed (v0.11.9)
- New `src/retrieval/table_extractor.py`: `extract_tables_from_pdf()` → `register_tables_as_views()`
- PDF upload via `POST /api/docs/upload` auto-triggers table extraction; extracted tables registered as DuckDB views with `doc_` prefix
- Graceful no-op when pdfplumber unavailable

**Files changed:** `requirements.txt`, `src/retrieval/table_extractor.py`, `app/api.py`

### 5. Enhanced Sample Dataset (11 tables, 2,286 rows)
**New tables:**
- `loan_application` (600 rows): 25 branches × 3 loan types × 8 months; approval_rate_pct, avg_processing_days, rejection counts
- `network_incident` (162 rows): 27 cities × 6 months; incident_count, sla_breach_count, mttr_hrs

**New columns on existing tables:**
- `customer`: industry, annual_revenue, debt_service_ratio
- `branch`: npl_amount, deposit_balance, roi_pct (NPL tiers: 3-6% Java, 7-12% Sumatra, 13-22% outer islands)
- `subscriber`: tenure_months, monthly_complaints (both correlated with churn_risk_score)
- `network`: avg_latency_ms, packet_loss_pct (correlated with utilization/status)
- `public_service`: pending_count, complaint_count

**DOMAIN_CONFIG updated:** `loan_application` added to banking; `network_incident` added to telco

**Files changed:** `sample_data.py`, `seed_parquet.py`, `metadata.py`, `prompts.py`, `api.py`

### 6. Complex Sample Questions
22 hard questions across all domains + 2 cross-domain "All" questions:
- Dual-filter HAVING (NPL >8% AND volume >5T)
- Revenue at risk (conditional aggregation)
- Composite network risk score
- Branch ROI vs NPL efficiency comparison
- KUR loan approval rate trends
- Economic stress index (cross-domain)
- Digital infrastructure gap (cross-domain)

**Files changed:** `app/api.py` (_SAMPLES), `prompts.py` (15+ new few-shot examples)

### 7. Bug Fixes
- **Giant blue question mark**: agent panel header SVG had no size → expanded to fill container. Fixed: `style={{width:'14px',height:'14px'}}` added
- **Pill height mismatch (AGENT vs GROUNDED)**: ModeBadge had `border:1px` that GroundingBadge lacked. Fixed: `border:1px solid transparent` + `display:inline-flex` on GroundingBadge
- **Agent mode SQL planner**: was generating SQL in `query` field instead of natural language. Fixed: `_AGENT_PLAN_SYSTEM` now has explicit rule with good/bad examples
- **Province geo detection**: `hasGeo` regex now includes `province|kota|provinsi|wilayah`
- **Persona labels**: BNI → Bank Indonesia, Telkomsel → Indosat
- **Debate/Agent mode fixed**: `DEBATE_ASSISTANT` and `AGENT_ASSISTANT` reducer cases properly initialize message state
- **Token count in agent mode**: `_agent_sse` now emits `usage` in done event and increments `_session_stats`
- **Synthesizing spinner**: `DONE` reducer sets `agentPhase:'done'` for agent messages

---

## Architecture Decisions

### Why local Leaflet instead of CDN
Cloudera AI Workbench environments are often air-gapped or have restricted outbound internet. CDN failures would break the map silently. All JS dependencies must be self-hosted per project convention.

### Why Debate uses non-streaming Researcher + streaming Critic
The Researcher needs complete context to summarize evidence coherently; streaming fragments would make it incoherent. The Critic works well as a live stream since it's reacting to already-complete content and the streaming gives visual indication of "AI thinking about challenges".

### Why NPL tiers are hardcoded by city (not random)
Demo needs to tell a consistent geographic story: Java = well-managed credit, outer islands = higher risk. Random distribution would make the map uninteresting and unpredictable during live demos.

### Why loan_application uses branch×month (not city×month)
Branch-level data enables questions like "Which branch has the slowest processing?" and "Compare Jakarta Pusat vs Jakarta Selatan approval rates" — more granular and impressive.

---

## Test Results
86/86 tests passing after all changes.
