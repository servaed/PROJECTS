---
name: presales-flow
description: Complete presales demo execution guide — opening hook, demo flow, talking points, custom question handling, objection responses, and post-demo follow-up.
---

# Skill: Presales Demo Flow

## Audience Preparation (Before Opening the App)

1. Ask the customer: "Are there architects or IT decision-makers in the call?"
   - **Yes → Technical mode**: open `/presentation`, click the **Technical** toggle top-right
   - **No → Business mode**: keep the default **Business** toggle (9 slides)

2. Confirm the domain that resonates with the customer:
   - **Banking**: credit officers, compliance teams, risk managers
   - **Telco**: network ops, customer success, retention teams
   - **Government**: budget controllers, public service coordinators

3. Confirm language: use **Bahasa Indonesia** if the audience is primarily Indonesian-speaking; **English** for mixed or international audiences.

## Demo Flow

### Phase 1 — Context (3 min)
Open `/presentation`. Walk through **slides 1–3**:
- Slide 1: "Your Data Already Has All the Answers" — set the hook
- Slide 2: The Problem — pick one pain card that matches the customer's role
- Slide 3: The Solution — walk through the scenario that matches their domain

Say: *"Let me show you this live — the demo is running right now."*

### Phase 2 — Live Demo (20–25 min)

**Step 1 — Document mode** (5–8 min)
- Select the customer's domain in the sidebar
- Ask a policy question (click a sample prompt or type your own)
- After the answer: expand a **citation card** → "Show full chunk"
- Say: *"Every answer is traceable to the exact policy paragraph it came from."*

**Step 2 — Data mode** (5–8 min)
- Ask a data/aggregation question
- Expand the **SQL trace panel** → show the generated SQL
- Point to the bar chart if rendered
- Say: *"The SQL is shown verbatim — your audit team can validate every query."*

**Step 3 — Combined mode** (5–8 min)
- Ask a combined question (policy target vs. actual data)
- Wait for the mode badge to show "Combined"
- Say: *"It simultaneously checked the policy for the target AND queried live data for the actual number. One question, one answer."*

**Step 4 — Bilingual switch** (2 min, if relevant)
- Toggle language in sidebar
- Ask the same question in the other language
- Say: *"Same model, same data — just switch the language."*

**Step 5 — Customer's own question** (3–5 min)
- Invite the customer to type any question
- If it fails gracefully: acknowledge the guardrails, don't apologize excessively

### Phase 3 — Technical Deep Dive (optional, +10 min)
Switch to `/presentation` Technical mode. Walk through slides 10–14:
- T-01: Pipeline — "Here's exactly what happens when you hit send"
- T-02: Retrieval — "Three stages of quality filtering before a word is generated"
- T-03: Deployment — "Same code, different env vars for dev vs. production CDP"
- T-04: LLMs & APIs — "Pluggable — Cloudera AI Inference, OpenAI, Bedrock, Anthropic"
- T-05: Security — "SQL guardrails, vector store integrity, DOMPurify, MLflow"

### Phase 4 — Admin Pages (2 min)
- Open `/setup` — show all green indicators
- Open `/metrics` — show latency, token usage, mode breakdown
- Open `/configure` — show provider wizard; click **Test LLM**

## Talking Points by Audience

| Audience | Key message | Feature to highlight |
|----------|-------------|---------------------|
| C-suite | "Days to seconds for compliance decisions" | Auto-play demo, latency badge |
| Compliance officer | "Every answer is source-cited and auditable" | Citation cards, chunk preview |
| IT architect | "Zero new infrastructure — deploys on your existing Cloudera stack" | T-03 deployment slide |
| Data engineer | "SQL guardrails use AST walking, not regex — no bypass possible" | T-05 security slide, SQL trace |
| Operations manager | "Real-time data, always current — no ETL, no sync" | T-03: CDW/Trino connector |
| Indonesian-speaking user | "Ask in Bahasa Indonesia, get answers in Bahasa Indonesia" | Language toggle |

## Handling Difficult Questions

**"What if the AI makes something up?"**
> "It can't fabricate an answer from thin air — it only reads from your documents and data. If it can't find the answer, it says so explicitly rather than guessing. Watch — let me ask a question outside the knowledge base."

**"Is our data safe?"**
> "With Cloudera AI Inference, the LLM runs on your own infrastructure — no data leaves your cluster. With external providers, only the question and retrieved context are sent — never the full document or database."

**"How long does it take to set up with our own data?"**
> "The technical setup is a few hours — upload documents through the browser, point it at your data warehouse, done. Fine-tuning the sample prompts and testing with real questions takes a day or two."

**"Can it handle [specific domain/regulation]?"**
> "Yes — you upload your own policy documents and it learns them. The demo uses UMKM credit policy, OJK regulation, and APBD regulation as examples. You'd replace these with your actual documents."

**"What model is it using?"**
> Show `/configure` — point to the provider selector. "It's model-agnostic. For this demo I'm using [current provider]. For production, Cloudera AI Inference runs the model on your cluster."

## Common Issues During Demo

| Issue | Recovery |
|-------|---------|
| LLM slow (>15s) | "The model was cold — it warms up after the first question." Wait; next response will be fast. |
| Wrong language | Toggle language back and forth in sidebar |
| Auto-play stuck | Stop → "New conversation" → restart auto-play |
| SQL returns empty | Ask a different data question; the first one may have hit an edge case in the seeded data |
| App shows red in `/setup` | Check LLM config: open `/configure`, re-enter API key, Test LLM |

## Post-Demo Follow-Up

- [ ] Send the GitHub repo link
- [ ] Share `DEPLOYMENT.md` and architecture diagram
- [ ] Capture specific questions for the product team
- [ ] Propose a PoC engagement: "We can load your actual documents and connect to your data warehouse — typically 1–2 days for a working PoC"
- [ ] Click **"New conversation"** before leaving the session
