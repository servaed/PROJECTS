---
name: app-deploy
description: Steps for preparing and validating deployment as a Cloudera AI Application. Covers Script (Python launcher) path, DuckDB/Parquet seed, env vars, configure wizard, startup scripts, and CML-specific constraints sourced from official Cloudera documentation.
---

# Skill: App Deployment (Cloudera AI Workbench)

## Key Facts from Official Cloudera Documentation

- **Script field accepts Python files only** — CML runs the Script as Python, not bash.
  To run a bash script, create a Python launcher (`run_app.py`) that calls it via `subprocess`.
- **No Docker image source in the UI** — CML uses Source-to-Image (S2I) internally.
  Users cannot specify a custom Docker image URL in the New Application form.
- **Port**: Use `CDSW_APP_PORT` environment variable (not hardcoded 8080). CML injects this.
  `APP_PORT=8080` works because CML sets `CDSW_APP_PORT=8080` by default.
- **Environment variable precedence**: Application-level vars override project-level vars.
- **Public access**: Disabled by default. Admin must explicitly enable
  "Allow applications to be configured with unauthenticated access" in Site Administration.
- **Auth headers**: CML injects `Remote-user=<username>` and `Remote-user-perm=<RO/RW/Unauthorized>`
  into every request — the app does not need its own auth logic.
- **Applications do not auto-timeout** — unlike Sessions (60 min). Must be stopped manually.
- **SSH through HTTP proxy is not supported** — use HTTPS for Git cloning instead.
- **Static subdomain support**: introduced in CML 2.0.45-b54.
- **Subdomain format**: DNS-compliant — letters a–z, digits 0–9, hyphens only.
- **Resource profiles**: Admin pre-configures and whitelists available profiles.
  Resources must be contiguous on a single node (pods cannot span nodes).

---

## Python Launcher (required for bash startup scripts)

CML's Script field runs Python, not bash. Use this wrapper to invoke `launch_app.sh`:

```python
# run_app.py — place at demos/cloudera-ai-id-rag-demo/run_app.py
import os
import subprocess
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.exit(subprocess.call(["bash", "deployment/launch_app.sh"]))
```

Set **Script** in the Application form to:
```
demos/cloudera-ai-id-rag-demo/run_app.py
```

---

## Pre-Deployment Checklist

- [ ] `run_app.py` exists and points to the correct `launch_app.sh` path
- [ ] `APP_PORT` left as default (8080) — matches CML's `CDSW_APP_PORT`
- [ ] LLM credentials set via Application env vars **or** saved via `/configure` wizard
- [ ] `SQL_APPROVED_TABLES` limits exposed tables (default: `msme_credit,customer,branch,subscriber,data_usage,network,resident,regional_budget,public_service`)
- [ ] No credentials in version control (`.env` and `data/.env.local` in `.gitignore`)
- [ ] `requirements.txt` is up to date
- [ ] All tests pass: `pytest tests/ -v`

---

## Creating a CML Application (UI)

**Navigate to:** Project → Applications → New Application

| Field | Value |
|---|---|
| **Name** | `Asisten Enterprise ID` |
| **Subdomain** | `asisten-enterprise` (a–z, 0–9, hyphens only) |
| **Script** | `demos/cloudera-ai-id-rag-demo/run_app.py` |
| **Editor** | `Workbench` |
| **Kernel** | `Python 3.10` |
| **Edition** | `Standard` (not Nvidia GPU — no GPU needed) |
| **Resource Profile** | `4 vCPU / 8 GiB` minimum (embedding model needs ~3 GB RAM) |
| **Enable Spark** | OFF |
| **Enable GPU** | OFF |

**Environment Variables** (click `+` for each):

| Key | Value |
|---|---|
| `LLM_PROVIDER` | `openai` / `azure` / `bedrock` / `anthropic` / `cloudera` |
| `LLM_API_KEY` | your API key |
| `LLM_MODEL_ID` | e.g. `gpt-4o` |

Application-level env vars override project-level env vars.

---

## Creating a CML Application (API v2)

```python
import cmlapi

client = cmlapi.default_client(url="https://ml-xxxx.cloudera.com", cml_api_key="...")

app = client.create_application(
    body=cmlapi.CreateApplicationRequest(
        name="Asisten Enterprise ID",
        subdomain="asisten-enterprise",
        project_id="<project-id>",
        script="demos/cloudera-ai-id-rag-demo/run_app.py",
        kernel="python3",
        cpu=4,
        memory=8,
        environment={"LLM_PROVIDER": "openai", "LLM_API_KEY": "sk-..."}
    ),
    project_id="<project-id>"
)
```

---

## Git Project Setup (cloning into CML)

**HTTPS** (recommended — SSH through HTTP proxy is not supported):
```
https://github.com/servaed/PROJECTS.git
```
With PAT for private repos:
```
https://servaed:<GITHUB_PAT>@github.com/servaed/PROJECTS.git
```

**SSH** (only if workspace has direct internet access):
```
git@github.com:servaed/PROJECTS.git
```
Requires: User Settings → SSH Keys → copy public key → add to GitHub.

Branch: `master`

---

## What launch_app.sh Does (Git source mode)

```
[0/5] Source data/.env.local (written by /configure wizard on prior runs)
[1/5] pip install -r requirements.txt (skipped after first run via marker file)
[2/5] Install provider-specific SDK if needed (boto3 / anthropic)
[3/5] Seed Parquet files for DuckDB — 9 tables, 1485 rows (idempotent, checks msme_credit.parquet)
[4/5] Build FAISS vector store (skipped if index.faiss already exists)
[5/5] exec uvicorn app.api:app --host 0.0.0.0 --port $APP_PORT
```

First boot: ~3–5 min (embedding model download ~500 MB).
Warm restart: ~30 s (pip and vector store both skipped).

---

## Credential Configuration

### Method A — Application env vars (UI, before or after deploy)
Set in Applications → your app → ⋯ → Edit → Environment Variables.
Takes highest precedence. Field appears locked ("From environment") in `/configure` wizard.

### Method B — /configure browser wizard (after deploy, no shell needed)
1. Open `http://<app-url>/configure`
2. Select provider, fill credentials, click **Save Configuration**
3. Restart from Applications UI → changes take effect

### Method C — Project-level env vars
Set in Project Settings → Advanced → Environment Variables.
Application-level vars (Method A) override these.

---

## Access Control

- **Authenticated (SSO)**: Default. CML injects `Remote-user` / `Remote-user-perm` headers.
  The app reads these if needed — no custom auth logic required.
- **Unauthenticated (public)**: Must be explicitly enabled by admin in Site Administration.
  Use only for internal demos — never with real customer data.

---

## Updating a Running Application

| Change | Action |
|---|---|
| Code change | `git pull` in a CML Session, then Applications → Restart |
| Credential change | `/configure` → Save, then Applications → Restart |
| New documents | `/setup` → ⟳ Re-ingest button (no restart needed) |
| Force full re-seed | Delete `data/vector_store/` in Session, then Restart |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `SyntaxError` in app logs | Script field pointing to `.sh` file | Change Script to `run_app.py` Python launcher |
| App stuck at "Starting" | pip install or embedding model download | Check logs; first boot takes 3–5 min |
| `ModuleNotFoundError` | `requirements.txt` incomplete | Add missing package, restart |
| LLM indicator red | Wrong credentials or URL | Open `/configure` → Test LLM → fix |
| `/configure` field shows "From environment" | Application env var overrides wizard | Update via Applications UI → env vars |
| `integrity check FAILED` | `index.sha256` mismatch | Delete `data/vector_store/` → restart |
| SSH clone fails | SSH through HTTP proxy not supported | Switch to HTTPS with PAT |
| App URL not accessible | Subdomain has invalid characters | Use only a–z, 0–9, hyphens |
| Public access denied | Unauthenticated access not enabled | Ask admin to enable in Site Administration |
