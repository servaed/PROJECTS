# /cluster-from-scratch

Run the complete end-to-end cluster deployment on a fresh RHEL 9 GCP VM (all 9 phases). Use for a brand-new provisioning.

## Arguments
`$ARGUMENTS` — optional starting phase (default: `0`). Example: `/cluster-from-scratch 3` to start from PostgreSQL.

## Pre-conditions
1. VM is provisioned and reachable: `ssh root@34.26.137.154`
2. `config.env` is updated with correct `NODE_HOST`, `NODE_IP`, `IPA_ADMIN_PASS`
3. Cloudera license credentials (`CLOUDERA_REPO_USER`, `CLOUDERA_REPO_PASS`) are set in config.env
4. For phase 7 (Auto-TLS): `SSH_PASSWORD` must match the root password

## Run

```bash
FROM="${ARGUMENTS:-0}"
BASE="accelerators/cloudera-base-732-kerberos"
VM="34.26.137.154"

echo "=== Syncing all scripts to VM ==="
rsync -av --exclude='*.pyc' --exclude='__pycache__' \
  ${BASE}/ root@${VM}:/opt/cloudera-install/ \
  --exclude='.git' --exclude='ref_cluster_export.json' --exclude='adapted_template.json'

echo "=== Deploying patched CM binaries ==="
# These are needed for phase 8 but deploy them now
ssh root@${VM} 'mkdir -p /opt/cloudera/cm/bin 2>/dev/null; exit 0'

echo "=== Starting from phase $FROM ==="
ssh root@${VM} "cd /opt/cloudera-install && source config.env && export SSH_PASSWORD='Cl0ud3ra@Base732#SE' && bash install.sh --from $FROM" 2>&1
```

**Expected timeline:**
- Phase 0-2: ~5 minutes
- Phase 1 (FreeIPA): ~10-15 minutes
- Phase 3 (PostgreSQL): ~3 minutes
- Phase 4 (CM): ~5 minutes
- Phase 5 (CMS): ~10 minutes
- Phase 6 (Cluster): ~30-45 minutes (parcel download + 20 services)
- Phase 7 (Auto-TLS): ~15 minutes
- Phase 8 (Kerberos): ~10 minutes

After phase 7 completes, CM_PORT switches from 7180 → 7183 automatically.

After all phases complete, run `/kerberos-smoke-test` to verify.
