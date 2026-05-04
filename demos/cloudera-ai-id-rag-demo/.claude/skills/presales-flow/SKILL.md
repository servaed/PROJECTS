---
name: presales-flow
description: Complete presales demo execution guide — opening hook, demo flow, talking points, custom question handling, objection responses, and post-demo follow-up.
---

# Skill: Presales Demo Flow

## Audience Preparation (Before Opening the App)

1. Ask: "Are there architects or IT decision-makers in the call?"
   - **Yes → Technical mode**: open `/presentation`, click the **Technical** toggle top-right
   - **No → Business mode**: keep the default **Business** toggle (9 slides)

2. Confirm the domain that resonates with the customer:
   - **Banking**: credit officers, risk managers, compliance teams → domain "Banking"
   - **Telco**: network ops, customer success, retention teams → domain "Telco"
   - **Government**: budget controllers, public service coordinators → domain "Government"
   - **Cross-domain**: executives seeing the full picture → domain "All"

3. Confirm language: **Bahasa Indonesia** for Indonesian-speaking audiences; **English** for mixed/international.

4. Optionally pick a **Persona** (Rina / David / Budi) for a role-led demo flow.

---

## Demo Flow

### Phase 1 — Context (3 min)
Open `/presentation`. Walk through **slides 1–3**:
- Slide 1: "Your Data Already Has All the Answers" — set the hook
- Slide 2: The Problem — pick the pain card that matches the customer's role
- Slide 3: The Solution — walk through the scenario that matches their domain

Say: *"Let me show you this live — the demo is running right now."*

### Phase 2 — Live Demo (20–25 min)

**Step 1 — Document mode** (5 min)
- Select the customer's domain in the sidebar
- Click a document-mode sample prompt (policy/procedure question)
- After answer: expand a **citation card** → "Show full chunk"
- Say: *"Every answer is traceable to the exact policy paragraph it came from."*

**Step 2 — Data mode with Map** (8 min)
- Ask a geo-aware data question from the "Try Asking" sidebar:
  - Banking: *"Tampilkan peta risiko NPL kredit UMKM per kota"*
  - Telco: *"Tampilkan peta utilisasi jaringan per kota"*
- The **Map view auto-activates** — show the Indonesia heatmap
- Point to bubble sizing (larger = higher metric), color (teal→orange→red)
- Switch between **Map / Bar / Table** tabs
- Expand the SQL trace panel → show generated SQL
- Say: *"Geography is in the data — Cloudera AI turns SQL results into a live heatmap."*

**Step 3 — Combined mode** (8 min)
- Ask a combined question (policy target vs. actual data)
- Wait for mode badge to show "Combined"
- Say: *"It simultaneously checked the policy for the target AND queried live data for the actual number."*

**Step 4 — AI Reasoning / Debate** (optional, 5 min, advanced audiences)
- Toggle **Think** ON → ask a complex question → show chain-of-thought reasoning panel
  - Say: *"The model shows its work — no black box."*
- OR toggle **Debate** ON → show Researcher + Critic cards before the answer
  - Say: *"We have one AI challenge another's assumptions — adversarial review built in."*

**Step 5 — Bilingual switch** (2 min, if relevant)
- Toggle language in sidebar → ask the same question
- Say: *"Same model, same data — just switch the language."*

**Step 6 — Customer's own question** (3–5 min)
- Invite the customer to type any question
- If it fails gracefully: acknowledge the guardrails; don't apologize excessively

### Phase 3 — Technical Deep Dive (optional, +10 min)
Switch to `/presentation` Technical mode. Walk through slides 10–14:
- T-01: Pipeline architecture
- T-02: Three-stage retrieval (FAISS + BM25 + cross-encoder)
- T-03: Deployment (dev DuckDB → production CDW/Trino, same connectors)
- T-04: LLM providers (pluggable)
- T-05: Security (SQL AST guardrails, vector store integrity, DOMPurify)

### Phase 4 — Admin Pages (2 min)
- Open `/setup` — show all green indicators + token usage
- Open `/metrics` — show latency, token usage, mode breakdown
- Open `/configure` — show provider wizard; click **Test LLM**

---

## High-Impact Complex Questions

Use these for maximum "wow" — each produces a map and a multi-metric SQL result:

**Banking:**
- *"Kota mana yang NPL di atas 8% DAN volume kredit di atas 5 triliun?"* → dual-threshold hotspot map
- *"Bandingkan ROI cabang vs NPL rate — cabang mana yang paling efisien?"* → branch efficiency ranking
- *"Tampilkan tingkat persetujuan KUR per kota — identifikasi kota dengan backlog tinggi"* → loan approval map

**Telco:**
- *"Hitung revenue at risk: total ARPU pelanggan churn >70 per kota"* → business impact map
- *"Tampilkan composite risk score jaringan: utilisasi × packet loss per kota"* → network risk map

**Cross-domain (All tab):**
- *"Tampilkan economic stress index per kota: gabungkan NPL + churn risk + keluhan layanan"* → triple-metric map

---

## Talking Points by Audience

| Audience | Key message | Feature to highlight |
|----------|-------------|---------------------|
| C-suite | "Days to seconds for compliance decisions" | Map heatmap, latency badge, auto-play |
| Compliance officer | "Every answer is source-cited and auditable" | Citation cards, chunk preview, SQL trace |
| IT architect | "Zero new infrastructure — deploys on your existing Cloudera stack" | T-03 deployment slide |
| Data engineer | "SQL guardrails use AST walking, not regex — no bypass possible" | T-05 security, SQL trace |
| Operations manager | "Real-time data, always current — no ETL, no sync" | CDW/Trino connector |
| Risk manager | "Geographic NPL visualization across all 27 cities — instantly" | Indonesia heatmap |
| Indonesian user | "Ask in Bahasa Indonesia, get answers in Bahasa Indonesia" | Language toggle |

---

## Handling Difficult Questions

**"What if the AI makes something up?"**
> "It can't fabricate from thin air — it only reads your documents and data. If it can't find the answer, it says so explicitly. Watch — let me ask a question outside the knowledge base."

**"Is our data safe?"**
> "With Cloudera AI Inference, the LLM runs on your own infrastructure — no data leaves your cluster. With external providers, only the question and retrieved context are sent — never the full document or database."

**"How long does it take to set up with our own data?"**
> "Technical setup is a few hours — upload documents through the browser, point it at your data warehouse, done. Testing with real questions takes a day or two."

**"Can it handle [specific domain/regulation]?"**
> "Yes — you upload your own policy documents and it learns them. The demo uses OJK regulation, APBD, and telco SLA as examples. You'd replace these with your actual documents."

**"What model is it using?"**
> Show `/configure`. "It's model-agnostic. For this demo I'm using [current provider]. For production, Cloudera AI Inference runs the model on your cluster."

**"Can it show its reasoning?"**
> "Yes — toggle Think mode and the model streams its chain-of-thought before answering. With Debate mode, a second AI challenges the first's assumptions." Show live.

---

## Common Issues During Demo

| Issue | Recovery |
|-------|---------|
| LLM slow (>15s) | "The model was cold — it warms up after the first question." |
| Map not appearing | Ensure the query returns a city/region/province column; try "Tampilkan jaringan per kota" |
| Wrong language | Toggle language back and forth in sidebar |
| Auto-play stuck | Stop → Reset Demo → restart auto-play |
| SQL returns empty | Ask a different data question |
| App shows red in `/setup` | Open `/configure`, re-enter API key, click Test LLM |

---

## Post-Demo Follow-Up

- [ ] Send GitHub repo link
- [ ] Share `DEPLOYMENT.md` and architecture diagram
- [ ] Capture specific questions for the product team
- [ ] Propose a PoC: "We can load your actual documents and connect to your data warehouse — typically 1–2 days for a working PoC"
- [ ] Click **Reset Demo** before leaving the session
