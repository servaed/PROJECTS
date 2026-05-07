# /kerberos-enable

Deploy the latest Kerberos enablement scripts to the VM and run the full enablement flow.

## What this does
1. Copies `scripts/06_kerberos_enable.py`, `scripts/gen_credentials_patched.sh`, and `scripts/import_credentials_patched.sh` from the local repo to the VM
2. Deploys the patched CM binaries to `/opt/cloudera/cm/bin/`
3. Runs `06_kerberos_enable.py` — covers all steps: write IPA admin pass, configure CM Kerberos settings, import admin credentials, configureForKerberos, deploy client configs, generateCredentials, restart stale services, and verify

## VM details
- IP: `34.26.137.154`
- Scripts on VM: `/opt/cloudera-install/scripts/`
- CM binaries: `/opt/cloudera/cm/bin/`
- Config: `/opt/cloudera-install/config.env`

## Steps to run

Run these shell commands:

```bash
# 1. Deploy patched CM binaries
scp accelerators/cloudera-base-732-kerberos/scripts/gen_credentials_patched.sh root@34.26.137.154:/opt/cloudera/cm/bin/gen_credentials.sh
scp accelerators/cloudera-base-732-kerberos/scripts/import_credentials_patched.sh root@34.26.137.154:/opt/cloudera/cm/bin/import_credentials.sh
ssh root@34.26.137.154 'chmod +x /opt/cloudera/cm/bin/gen_credentials.sh /opt/cloudera/cm/bin/import_credentials.sh'

# 2. Deploy enablement script
scp accelerators/cloudera-base-732-kerberos/scripts/06_kerberos_enable.py root@34.26.137.154:/opt/cloudera-install/scripts/06_kerberos_enable.py

# 3. Run it
ssh root@34.26.137.154 'cd /opt/cloudera-install && source config.env && export CM_PORT=7183 && python3.11 scripts/06_kerberos_enable.py'
```

Show all output. If it fails, read `/var/log/cloudera-scm-server/cloudera-scm-server.log` on the VM around the time of failure and diagnose.

Key things to watch for in errors:
- `Permission denied` on `/etc/cloudera/.ipa_admin_pass` → fix: `chown cloudera-scm /etc/cloudera/.ipa_admin_pass`
- `ipa service-add` failing → check if `kinit admin@SE-INDO.LAB` worked
- `merge_credentials.sh` empty input → means `gen_credentials.sh` failed for all principals
- HTTP 400 on `configureForKerberos` → body must be `{}` not `{"deleteCredentials": false}`
