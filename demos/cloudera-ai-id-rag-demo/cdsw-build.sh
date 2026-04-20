#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# cdsw-build.sh — CML project build script
#
# Cloudera AI Workbench runs this file automatically when the project is first
# loaded from Git (before any Application, Job, or Session starts).
# Pre-installing here means Application boots skip the pip-install step,
# reducing cold-start time by 2–3 minutes.
#
# Reference: https://docs.cloudera.com/machine-learning/cloud/runtimes/topics/ml-cdsw-build-script.html
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

echo "========================================================"
echo " CML Build — cloudera-ai-id-rag-demo"
echo " Python : $(python --version 2>&1)"
echo " pip    : $(pip --version 2>&1)"
echo "========================================================"

echo "[build 1/3] Installing Python dependencies..."
pip install --quiet --no-warn-script-location -r requirements.txt

echo "[build 2/3] Seeding demo SQLite database (local-dev fallback)..."
python data/sample_tables/seed_database.py

echo "[build 3/3] Pre-downloading embedding model (multilingual-e5-large)..."
python - <<'PYEOF'
import os, sys
try:
    from sentence_transformers import SentenceTransformer
    model_name = os.environ.get("EMBEDDINGS_MODEL", "intfloat/multilingual-e5-large")
    print(f"  Downloading {model_name} (~500 MB, cached to ~/.cache/huggingface)...")
    SentenceTransformer(model_name)
    print("  Model ready.")
except Exception as exc:
    print(f"  Warning: model pre-download failed ({exc}). Will download on first use.")
PYEOF

echo "========================================================"
echo " CML Build complete. Application starts will be faster."
echo "========================================================"
