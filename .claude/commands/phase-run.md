# /phase-run

Run a specific install phase (0-8) on the VM. Syncs the script first then runs it.

## Arguments
`$ARGUMENTS` — phase number (required). Example: `/phase-run 8`

## Phase map
- `0` — System prep: Java 17, Python 3.11, data dirs, /etc/hosts, firewalld
- `1` — FreeIPA server install (`ipa-server-install`)
- `2` — krb5.conf patch: `udp_preference_limit=1`
- `3` — PostgreSQL 14 (PGDG repo, all CM service databases)
- `4` — Cloudera Manager 7.13.2 install + `scm_prepare_database`
- `5` — Cloudera Management Service (Alert Publisher, Event Server, Host Monitor, Reports Manager, Service Monitor)
- `6` — Cluster deployment: 20 services via `importClusterTemplate`
- `7` — Auto-TLS: CM-managed CA, switches CM to HTTPS port 7183
- `8` — Kerberos: `importAdminCredentials` → `configureForKerberos` → `generateCredentials` → restart

## Run

```bash
PHASE="$ARGUMENTS"
BASE="accelerators/cloudera-base-732-kerberos"
VM="34.26.137.154"

# For phase 8, deploy patched CM binaries first
if [ "$PHASE" = "8" ]; then
  scp ${BASE}/scripts/gen_credentials_patched.sh root@${VM}:/opt/cloudera/cm/bin/gen_credentials.sh
  scp ${BASE}/scripts/import_credentials_patched.sh root@${VM}:/opt/cloudera/cm/bin/import_credentials.sh
  scp ${BASE}/scripts/06_kerberos_enable.py root@${VM}:/opt/cloudera-install/scripts/
  ssh root@${VM} 'chmod +x /opt/cloudera/cm/bin/gen_credentials.sh /opt/cloudera/cm/bin/import_credentials.sh'
fi

# Sync config and run phase
rsync -av --exclude='*.pyc' ${BASE}/scripts/ root@${VM}:/opt/cloudera-install/scripts/ 2>/dev/null
scp ${BASE}/config.env ${BASE}/install.sh root@${VM}:/opt/cloudera-install/ 2>/dev/null

ssh root@${VM} "cd /opt/cloudera-install && source config.env && export CM_PORT=7183 && bash install.sh --phase $PHASE"
```

Show all output. If it fails, immediately fetch the relevant log (CM log for phases 5-8, bash trace for 0-4) and diagnose.
