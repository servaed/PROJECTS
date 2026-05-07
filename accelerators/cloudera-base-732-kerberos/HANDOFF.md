# Kerberos Enablement — Handoff Document
_Last updated: 2026-05-07 ~12:30 UTC_

---

## Project Goal
Enable Kerberos (FreeIPA) on a single-node CDP Private Cloud Base 7.3.2 cluster running on GCP (RHEL 9).

- VM IP: `34.26.137.154`  
- VM hostname: `cdp.se-indo.lab`  
- Realm: `SE-INDO.LAB`  
- IPA admin password: `Cl0ud3ra@Base732#SE`  
- CM admin password: `Cl0ud3ra@Base732#SE`  
- CM URL: `https://cdp.se-indo.lab:7183` (Auto-TLS enabled)  
- SSH: `ssh root@34.26.137.154` (passwordless key already set up)

---

## Current Status

### What is DONE ✅
- CDP cluster deployed with 20 services, all healthy
- Auto-TLS enabled (CM on HTTPS port 7183)
- `importAdminCredentials` → **SUCCEEDS** (cmadin keytab created)
- `configureForKerberos` → **SUCCEEDS**
- `deployClientConfig` → **SUCCEEDS**

### What is FAILING ❌
`generateCredentials` (the step that creates Kerberos keytabs for all 23 service principals) fails every time. The restart of stale services then fails because services are missing their keytabs.

---

## Root Cause (fully diagnosed)

CM calls `/opt/cloudera/cm/bin/gen_credentials.sh` for each service principal (hdfs, yarn, hive, etc.).

**The fix is 95% done.** The script has been patched to use `ipa service-add` + `ipa-getkeytab` (FreeIPA's native approach) instead of `kadmin addprinc` (which FreeIPA blocks for external clients). The fix works correctly when tested manually.

**The one remaining bug**: The patched script reads the IPA admin password from `/etc/cloudera/.ipa_admin_pass`, but CM runs `gen_credentials.sh` as the `cloudera-scm` user, and the file was previously owned by `root`. This caused:

```
cat: /etc/cloudera/.ipa_admin_pass: Permission denied
```

**Fix applied manually on VM:**
```bash
chown cloudera-scm /etc/cloudera/.ipa_admin_pass
chmod 600 /etc/cloudera/.ipa_admin_pass
```

**This manual fix was applied** — the file now has `cloudera-scm` as owner. The script in the repo (`06_kerberos_enable.py`) has been updated to set `cloudera-scm` ownership automatically going forward.

---

## What Needs to Run Next

Just re-run the Kerberos enablement script on the VM. The fix is in place:

```bash
ssh root@34.26.137.154
cd /opt/cloudera-install
source config.env
export CM_PORT=7183
python3.11 scripts/06_kerberos_enable.py
```

Expected outcome: All 23 service keytabs generated → services restart → Kerberos enabled.

---

## Files Changed (in this repo)

All files are in `accelerators/cloudera-base-732-kerberos/`:

| File | Status | What changed |
|------|--------|-------------|
| `scripts/gen_credentials_patched.sh` | **NEW — KEY FIX** | Replaces CM's `gen_credentials.sh`; uses `ipa service-add` + `ipa-getkeytab` for FreeIPA instead of `kadmin addprinc` + `kadmin xst` |
| `scripts/import_credentials_patched.sh` | Updated | Human users only (admin, cmadin); FreeIPA `ipa-getkeytab -P` approach |
| `scripts/06_kerberos_enable.py` | Updated | Writes IPA admin password to `/etc/cloudera/.ipa_admin_pass` with `cloudera-scm` ownership; adds `generateCredentials` step before restart; fixes `configureForKerberos` empty body; fixes `reDeployClientConf` removed in v58 |
| `scripts/08_autotls.py` | Updated (earlier) | `restartOnlyStaleServices` only (no `reDeployClientConf`) |

---

## Files Deployed on VM

| VM Path | Source | Purpose |
|---------|--------|---------|
| `/opt/cloudera/cm/bin/gen_credentials.sh` | `scripts/gen_credentials_patched.sh` | **KEY** — creates service keytabs via FreeIPA |
| `/opt/cloudera/cm/bin/import_credentials.sh` | `scripts/import_credentials_patched.sh` | Creates admin user keytab via FreeIPA |
| `/etc/cloudera/.ipa_admin_pass` | written by `06_kerberos_enable.py` | IPA admin password for `gen_credentials.sh` (owner: `cloudera-scm`, mode: 600) |
| `/opt/cloudera-install/scripts/06_kerberos_enable.py` | `scripts/06_kerberos_enable.py` | Kerberos enablement orchestrator |

---

## Technical Details

### Why `kadmin addprinc` fails on FreeIPA
FreeIPA uses its own LDAP backend (`ipadb.so`) for Kerberos. Even though `admin@SE-INDO.LAB` is in the `admins` group, FreeIPA does NOT grant external KADMIN `add`/`change-password` privileges through the standard kadmin protocol. Attempts return:
```
add_principal: Operation requires ``add'' privilege
```

### Why `ipa service-add` + `ipa-getkeytab` works
FreeIPA's native CLI:
- `ipa service-add yarn/cdp.se-indo.lab@SE-INDO.LAB` — registers the service (idempotent)
- `ipa-getkeytab -s cdp.se-indo.lab -p yarn/cdp.se-indo.lab@SE-INDO.LAB -k output.keytab --cacert=/etc/ipa/ca.crt` — generates new random keys and writes keytab

Both require a valid Kerberos TGT as `admin@SE-INDO.LAB`, obtained via:
```bash
echo "Cl0ud3ra@Base732#SE" | kinit admin@SE-INDO.LAB
```

Manually tested and confirmed working for `yarn/`, `hdfs/` service principals.

### gen_credentials.sh flow (patched)
```bash
if which ipa > /dev/null || [ -f /etc/ipa/default.conf ]; then
  # FreeIPA path
  kinit admin@SE-INDO.LAB   # uses /etc/cloudera/.ipa_admin_pass
  ipa service-add "$PRINC"  # idempotent
  ipa-getkeytab -s "$IPA_SERVER" -p "$PRINC" -k "$KEYTAB_OUT" --cacert=/etc/ipa/ca.crt
else
  # Original MIT KDC path (kadmin)
  kadmin -q "addprinc -randkey $PRINC"
  kadmin -q "xst -k $KEYTAB_OUT $PRINC"
fi
chmod 600 $KEYTAB_OUT
```

---

## Verification After Success

Once `06_kerberos_enable.py` completes:

```bash
# On the VM:
echo "Cl0ud3ra@Base732#SE" | kinit admin@SE-INDO.LAB
klist                          # should show TGT
hdfs dfs -ls /                 # should work with Kerberos
ipa service-find | grep cdp    # should show all Hadoop services
```

CM UI: `https://34.26.137.154:7183` → Hosts → check Kerberos = enabled

---

## Sequence for a Full Re-run (phases 0–8)

If you need to re-run everything from scratch on a fresh VM:

```bash
scp -r accelerators/cloudera-base-732-kerberos/ root@<VM_IP>:/opt/cloudera-install/
ssh root@<VM_IP>
cd /opt/cloudera-install
# Edit config.env with correct NODE_IP, NODE_HOST
bash install.sh --from 0
```

Phase 8 (Kerberos) deploys the patched scripts automatically via `06_kerberos_enable.py` which also writes `/etc/cloudera/.ipa_admin_pass`.

---

## Known Issues / Gotchas

1. **`merge_credentials.sh` always runs after `gen_credentials.sh`** — if ALL `gen_credentials.sh` calls fail, `merge_credentials.sh` receives empty input and fails with `chmod: cannot access ... No such file or directory`. This is the symptom, not the cause.

2. **CM runs scripts as `cloudera-scm`** — any file that CM scripts need to read must be owned by `cloudera-scm` or world-readable.

3. **`configureForKerberos` body must be `{}`** — passing `{"deleteCredentials": false}` causes HTTP 400 in CM API v58.

4. **`restartOnlyStaleServices` only** — CM API v58 removed `reDeployClientConf` from the restart body.

5. **`importAdminCredentials` is idempotent in our script** — it skips re-import if `kerberosEnabled` or `kdcAdminHost` is already set.

6. **`ipa-getkeytab` without `-P` changes keys** — every time `generateCredentials` runs, service principal keys change. This is OK for initial setup.
