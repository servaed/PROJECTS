#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────
# launch_app.sh — Cloudera AI Application startup script
#
# CML Applications execute a Python file as the Script, not bash directly.
# Point the CML Application Script field to run_app.py, which calls this file:
#   Script: demos/cloudera-ai-id-rag-demo/run_app.py
#
# Startup sequence:
#   1. Install Python dependencies (skipped after first run)
#   2. Install optional provider SDK if needed (bedrock / anthropic)
#   3. Seed the demo SQLite database (idempotent — skips if already seeded)
#   4. Ingest documents into FAISS vector store (skips if index exists)
#   5. Start FastAPI + React UI via uvicorn on $CDSW_APP_PORT (default 8080)
#
# Required environment variables (set in CML Application env vars panel):
#   LLM_PROVIDER, and the credentials for your chosen provider.
# ──────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Step 0: Load saved config overrides (written by the /configure wizard) ──
OVERRIDE_FILE="data/.env.local"
if [ -f "$OVERRIDE_FILE" ]; then
    echo "[0/5] Loading config overrides from $OVERRIDE_FILE ..."
    # Export each non-comment KEY=VALUE line; platform env vars take precedence
    # so we only set a variable if it is not already exported.
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        key="${key// /}"    # trim spaces
        if [ -z "${!key+x}" ]; then
            export "$key=$value"
            echo "    set $key from override file"
        else
            echo "    skip $key — already set by environment"
        fi
    done < <(grep -v '^\s*#' "$OVERRIDE_FILE" | grep '=')
    echo "[0/5] Override file loaded."
else
    echo "[0/5] No override file found at $OVERRIDE_FILE (use /configure to create one)."
fi

PORT="${CDSW_APP_PORT:-${APP_PORT:-8080}}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
VECTOR_STORE_PATH="${VECTOR_STORE_PATH:-./data/vector_store}"
LLM_PROVIDER="${LLM_PROVIDER:-cloudera}"

echo "========================================================"
echo " Cloudera AI Application — Startup"
echo "========================================================"
echo " Python   : $(python --version)"
echo " Port     : $PORT"
echo " Provider : $LLM_PROVIDER"
echo " CWD      : $(pwd)"
echo "========================================================"

# ── Step 1: Install core dependencies ─────────────────────────────────────
DEPS_MARKER=".deps_installed"
if [ ! -f "$DEPS_MARKER" ]; then
    echo "[1/5] Installing Python dependencies..."
    python3 - <<'PYEOF'
import subprocess, sys
from pathlib import Path

listed = [l for l in Path("requirements.txt").read_text().splitlines()
          if l.strip() and not l.startswith("#")]
total = len(listed)
print(f"  {total} packages listed in requirements.txt", flush=True)

proc = subprocess.Popen(
    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
)
count = 0
for line in proc.stdout:
    line = line.rstrip()
    if line.startswith("Collecting "):
        count += 1
        pkg = line[11:].split()[0] if len(line) > 11 else "?"
        pct  = min(count * 100 // max(total, 1), 99)
        bar  = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"  [{bar}] {pct:3d}%  {pkg}", flush=True)
    elif line.startswith("ERROR") or "error:" in line.lower():
        print(f"  {line}", flush=True)

proc.wait()
if proc.returncode != 0:
    sys.exit(proc.returncode)
print(f"  [{'█' * 20}] 100%  {count} packages processed", flush=True)
PYEOF
    touch "$DEPS_MARKER"
    echo "[1/5] Dependencies installed."
else
    echo "[1/5] Dependencies: already installed (delete '$DEPS_MARKER' to force reinstall)."
fi

# ── Step 2: Install provider-specific SDK if needed ───────────────────────
if [ "$LLM_PROVIDER" = "bedrock" ]; then
    python -c "import boto3" 2>/dev/null || {
        echo "[2/5] Installing boto3 for Amazon Bedrock..."
        pip install --quiet "boto3>=1.34.0"
    }
    echo "[2/5] Provider SDK: boto3 (Bedrock) — OK."
elif [ "$LLM_PROVIDER" = "anthropic" ]; then
    python -c "import anthropic" 2>/dev/null || {
        echo "[2/5] Installing anthropic SDK..."
        pip install --quiet "anthropic>=0.30.0"
    }
    echo "[2/5] Provider SDK: anthropic — OK."
else
    echo "[2/5] Provider SDK: not required for '$LLM_PROVIDER'."
fi

# ── Step 3: Seed demo database ────────────────────────────────────────────
DB_PATH="./data/sample_tables/demo.db"
if [ ! -f "$DB_PATH" ]; then
    echo "[3/5] Seeding demo database..."
    python data/sample_tables/seed_database.py
    echo "[3/5] Database seeded at $DB_PATH."
else
    # Verify it has the expected tables
    TABLE_COUNT=$(python -c "
import sqlite3; conn = sqlite3.connect('$DB_PATH')
count = len(conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall())
print(count)
conn.close()
" 2>/dev/null || echo "0")
    echo "[3/5] Database: found ($TABLE_COUNT tables)."
    if [ "$TABLE_COUNT" = "0" ]; then
        echo "[3/5] Database appears empty — re-seeding..."
        python data/sample_tables/seed_database.py
    fi
fi

# ── Step 4: Ingest documents into vector store ────────────────────────────
FAISS_INDEX="${VECTOR_STORE_PATH}/index.faiss"
if [ ! -f "$FAISS_INDEX" ]; then
    echo "[4/5] Vector store not found — running document ingestion..."
    echo "      (First run downloads the embedding model ~500 MB — please wait)"
    python -m src.retrieval.document_loader
    echo "[4/5] Ingestion complete."
else
    echo "[4/5] Vector store: found at $VECTOR_STORE_PATH — skipping ingestion."
    echo "      (Delete '$VECTOR_STORE_PATH' to force re-ingestion on next restart.)"
fi

# ── Step 5: Start FastAPI + React UI ─────────────────────────────────────
# Kill any orphaned uvicorn. Two patterns to cover:
#   - "uvicorn app.api:app"   — direct exec from launch_app.sh
#   - "python.*-m uvicorn"    — spawned by /api/restart background script
# The /api/restart endpoint uses start_new_session=True (detached), so it
# survives CML kernel restarts and causes Errno 98 on the next start.
echo "[5/5] Clearing port $PORT of any previous process..."
pkill -9 -f "uvicorn" 2>/dev/null || true
fuser -k "${PORT}/tcp" 2>/dev/null || true
sleep 2

echo "[5/5] Starting FastAPI server (React UI) on port $PORT..."
echo "========================================================"

exec uvicorn app.api:app \
    --host "127.0.0.1" \
    --port "$PORT" \
    --log-level "$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')"
