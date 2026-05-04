# Presales Demo Checklist

Quick reference for running cloudera-ai-id-rag-demo in front of a customer.
Complete all pre-demo steps before the call. Estimated run time: **25–35 minutes** for a full demo.
Add **10 minutes** for the Technical deep-dive if the audience includes architects or IT decision-makers.

---

## Pre-Demo (Day Before)

- [ ] Git repo accessible from the Cloudera AI workspace (HTTPS with PAT, or SSH if no HTTP proxy)
- [ ] CML project created from Git repo; `run_app.py` set as the Application Script
- [ ] Cloudera AI Application created with correct resource profile (4 vCPU / 8 GiB minimum)
- [ ] LLM provider configured via `/configure` wizard — test with **⚡ Test LLM**
- [ ] All status indicators green at `/setup`
- [ ] Auto-play tested end-to-end in the correct domain (Banking / Telco / Government)
- [ ] Map visualization tested — ask a geo query like "Tampilkan utilisasi jaringan per kota" and confirm the Map tab appears
- [ ] Browser opened in **Incognito/Private mode** to clear any prior session history
- [ ] Display resolution: **1920×1080** or wider; font size normal (100%)
- [ ] Disable notifications and Do Not Disturb enabled
- [ ] Backup slides ready in case of network failure

---

## Pre-Demo (30 Minutes Before)

- [ ] Open the app URL in browser
- [ ] Choose audience mode in `/presentation`: **Business** (default) or **Technical** (for architects/IT)
- [ ] Select the correct domain (Banking / Telco / Government / All) in the chat sidebar
- [ ] Select the correct language (Indonesian / English)
- [ ] Confirm all sidebar indicators show green
- [ ] Select a persona (Rina / David / Budi) if using persona-led demo flow
- [ ] Run one sample question manually to warm up the LLM cache
- [ ] Click **Reset Demo** to clear the warm-up history
- [ ] Test auto-play once quickly to confirm sequencing works

---

## Demo Flow (25–35 min, +10 min for Technical audience)

### 0. Slide Deck — Context Setting (3 min, optional)
- Open `/presentation` in a second tab or full-screen
- **Business audience**: walk slides 1–3 (problem → solution → scenarios) then jump to live demo
- **Technical audience**: after live demo, switch to Technical mode and walk slides 10–14 (pipeline, retrieval, deployment, LLM APIs, security)

### 1. Opening Hook (2 min)
- Show the clean interface — no infrastructure visible
- Mention: "This runs entirely on Cloudera AI, with your data staying in your cluster"
- Optionally activate a **Persona** to show role-based context

### 2. Document RAG — Policy Questions (6 min)
- Run 2 document-mode questions from the sidebar
- Expand citation cards → show exact source text + chunk index + ingest timestamp
- Highlight: full audit trail, no hallucination, source always shown

### 3. Structured Data + Map (8 min)
- Ask a geo-aware data question: *"Tampilkan peta risiko NPL per kota"* or *"Show network utilization map by city"*
- The **Map view auto-activates** — show Indonesia heatmap with bubble sizing
- Switch between Map / Bar / Table views using the chart switcher
- Expand SQL trace panel → show generated SQL
- Point out: latency badge, row count, formatted numbers

### 4. Combined — Policy vs Reality (8 min)
- Run 2 combined-mode questions (the "money slide")
- Explain: assistant retrieves live data AND policy document in one call
- Highlight: mode badge shows "Combined" — transparent about what it's doing

### 5. AI Reasoning / Debate (5 min, advanced audiences)
- Toggle **Think** ON → ask a complex question → show chain-of-thought reasoning panel
- OR toggle **Debate** ON → show Researcher + Critic two-card debate before the answer
- Say: "The model shows its work — you can see how it arrived at the answer"

### 6. Q&A / Custom Question (5 min)
- Invite the customer to type their own question
- If it fails gracefully: explain guardrails
- Use the **language toggle** if a multilingual demo is needed

---

## Talking Points

| Feature | What to Say |
|---------|-------------|
| Citation cards | "Every answer is traceable — click to read the exact policy paragraph it came from" |
| SQL trace | "The SQL is shown verbatim — your audit team can validate what the model queried" |
| Map heatmap | "NPL risk across 27 Indonesian cities instantly visualized — not possible with legacy BI tools" |
| Think mode | "The model shows its reasoning chain before answering — no black box" |
| Debate mode | "We have one AI challenge another's assumptions — built-in adversarial review" |
| Guardrails | "Only SELECT queries against an approved table list — no write access, ever" |
| Mode badge | "The badge shows whether the answer came from documents, data, or both — total transparency" |
| Language toggle | "Same model, same data — switch the language and responses follow" |
| Domain tabs | "One deployment, three business domains — add your own by changing the config" |
| Persona | "Each persona has domain context and pre-loaded questions — instant role-play" |
| Leaflet map | "Geography is in the data — Cloudera AI turns city-level SQL results into a live heatmap" |

---

## Impressive Complex Questions to Use Live

**Banking (use with Banking domain):**
- *"Kota mana yang NPL di atas 8% DAN volume kredit di atas 5 triliun?"* — dual-threshold hotspot map
- *"Bandingkan ROI cabang vs NPL rate — cabang mana yang paling efisien?"* — branch efficiency ranking
- *"Tampilkan tingkat persetujuan KUR per kota dan jenis pinjaman"* — loan approval heatmap

**Telco (use with Telco domain):**
- *"Hitung revenue at risk: total ARPU pelanggan churn >70 per kota"* — business impact map
- *"Tampilkan composite risk score jaringan: utilisasi × packet loss per kota"* — network risk map

**Cross-domain (use with All domain):**
- *"Tampilkan economic stress index per kota: NPL kredit + churn risk + keluhan layanan"* — cross-domain intelligence

---

## Known Issues & Mitigations

| Symptom | Fix |
|---------|-----|
| LLM response slow (>15s) | Pre-warm with one question before demo |
| "No data available" for data questions | Check `/setup` → Database card; run `make seed` |
| Map not appearing | Ensure query returns city/region/province column + ≤50 rows; check Leaflet loaded |
| Wrong language in response | Toggle ID then back; refresh page |
| Auto-play skips a question | Stop demo, click Reset Demo, restart auto-play |
| Sidebar shows red indicator | Open `/configure`, set LLM_BASE_URL + LLM_API_KEY |
| Pod OOM killed | Ensure ≥8 GiB; set `EMBEDDINGS_PROVIDER=openai` to reduce to 2 GiB |
| Think/Debate mode no output | Model may not support `<think>` tags; switch to DeepSeek-R1 or Claude 4 |

---

## Post-Demo

- [ ] Send follow-up email with the GitHub repo link
- [ ] Share architecture diagram from `DEPLOYMENT.md`
- [ ] Capture any customer-specific questions for the product team
- [ ] Click **Reset Demo** to clear session before next presenter uses the app
