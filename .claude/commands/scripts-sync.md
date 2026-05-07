# /scripts-sync

Sync all local scripts to the VM and deploy patched CM binaries. Run this after editing any script locally.

## Arguments
`$ARGUMENTS` — optional VM IP (default: `34.26.137.154`)

## Run

```bash
VM="${ARGUMENTS:-34.26.137.154}"
BASE="accelerators/cloudera-base-732-kerberos"

echo "=== Syncing scripts to $VM ==="
rsync -av --exclude='*.pyc' --exclude='__pycache__' \
  ${BASE}/scripts/ root@${VM}:/opt/cloudera-install/scripts/
scp ${BASE}/config.env ${BASE}/install.sh root@${VM}:/opt/cloudera-install/

echo "=== Deploying patched CM binaries ==="
scp ${BASE}/scripts/gen_credentials_patched.sh root@${VM}:/opt/cloudera/cm/bin/gen_credentials.sh
scp ${BASE}/scripts/import_credentials_patched.sh root@${VM}:/opt/cloudera/cm/bin/import_credentials.sh
ssh root@${VM} 'chmod +x /opt/cloudera/cm/bin/gen_credentials.sh /opt/cloudera/cm/bin/import_credentials.sh'

echo "=== Verify ==="
ssh root@${VM} 'ls /opt/cloudera-install/scripts/ | wc -l; echo "scripts on VM"'
ssh root@${VM} 'head -4 /opt/cloudera/cm/bin/gen_credentials.sh'
```

Confirm file counts and that the patched header shows in gen_credentials.sh.
