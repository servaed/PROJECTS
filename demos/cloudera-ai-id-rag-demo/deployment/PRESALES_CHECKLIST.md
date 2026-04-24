# Presales Demo Checklist

Quick reference for running the cloudera-ai-id-rag-demo in front of a customer.
Complete all pre-demo steps before the call. Estimated run time: **25–35 minutes** for a full demo.

---

## Pre-Demo (Day Before)

- [ ] Git repo accessible from the Cloudera AI workspace (HTTPS with PAT, or SSH if no HTTP proxy)
- [ ] CML project created from Git repo; `run_app.py` set as the Application Script
- [ ] Cloudera AI Application created with correct resource profile (4 vCPU / 8 GiB minimum)
- [ ] LLM provider configured via `/configure` wizard — test with `/api/test/llm`
- [ ] All status indicators green at `/setup`
- [ ] Auto-play tested end-to-end in the correct domain (Banking / Telco / Government)
- [ ] Browser opened in **Incognito/Private mode** to clear any prior session history
- [ ] Display resolution: **1920×1080** or wider; font size normal (100%)
- [ ] Disable notifications and Do Not Disturb enabled
- [ ] Backup slides ready in case of network failure

---

## Pre-Demo (30 Minutes Before)

- [ ] Open the app URL in browser
- [ ] Select the correct domain (Banking 🏦 / Telco 📡 / Government 🏛)
- [ ] Select the correct language (Indonesian / English)
- [ ] Confirm all sidebar indicators show green
- [ ] Run one sample question manually to warm up the LLM cache
- [ ] Click **"New conversation"** (trash icon) to clear the warm-up history
- [ ] Test auto-play once quickly to confirm sequencing works

---

## Demo Flow (25–35 min)

### 1. Opening Hook (2 min)
- Show the clean interface — no setup, no infrastructure visible
- Mention: "This runs entirely on Cloudera AI, with your data staying in your cluster"

### 2. Document RAG — Policy Questions (8 min)
- Run 2 document-mode questions from the sidebar
- Point out: **citation cards** expand to show the exact source text
- Highlight: **chunk index + ingest timestamp** = full audit trail

### 3. Structured Data — SQL Generation (8 min)
- Run 2 data-mode questions
- Expand the **SQL trace panel** → show generated SQL
- Point out: latency indicator (green = fast), row count, formatted numbers

### 4. Combined — Policy vs Reality (10 min)
- Run 2 combined-mode questions (the "money slide")
- Explain: assistant retrieves live data AND policy document in one call
- Highlight: mode badge shows "Combined" — transparent about what it's doing

### 5. Q&A / Custom Question (5 min)
- Invite the customer to type their own question
- If it fails gracefully: explain guardrails ("We only allow read queries against approved tables")
- Use the **language toggle** if a multilingual demo is needed

---

## Talking Points

| Feature | What to Say |
|---------|-------------|
| Citation cards | "Every answer is traceable — you can click to read the exact policy paragraph it came from" |
| SQL trace | "The SQL is shown verbatim so your audit team can validate what the model queried" |
| Guardrails | "The system only allows SELECT queries against an approved table list — no write access, ever" |
| Mode badge | "The badge tells you whether the answer came from documents, data, or both — no black box" |
| Language toggle | "Same model, same data — just switch the language and the responses follow" |
| Domain tabs | "One deployment, three business domains — add your own by changing the config" |

---

## Known Issues & Mitigations

| Symptom | Cause | Fix |
|---------|-------|-----|
| LLM response slow (>15s) | Model cold start or quota | Pre-warm by sending one question before demo |
| "No data available" for data questions | DuckDB Parquet files not seeded | Check `/setup` → Database card; run `make seed` |
| Wrong language in response | Language toggle out of sync | Toggle to ID then back; refresh page |
| Auto-play skips a question | SSE stream timed out | Stop demo, click "New conversation", restart auto-play |
| Sidebar shows red indicator | LLM not configured | Open `/configure`, set LLM_BASE_URL + LLM_API_KEY |
| Pod OOM killed | Embedding model RAM (~3 GB) + app RAM | Ensure pod has ≥8 GiB; use OpenAI embeddings to reduce to 2 GiB |

---

## Post-Demo

- [ ] Send follow-up email with the GitHub repo link
- [ ] Share architecture diagram from `DEPLOYMENT.md`
- [ ] Capture any customer-specific questions for the product team
- [ ] Click **"New conversation"** to clear session before next presenter uses the app
