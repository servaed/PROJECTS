# /autotls-enable

Enable Auto-TLS on the CDP cluster (phase 7). Generates a CM-managed CA, installs certs on all hosts, and restarts all services over TLS. CM moves to HTTPS port 7183 after this.

## Pre-conditions
- Cluster is deployed and all services are running (phase 6 complete)
- `SSH_PASSWORD` env var must be set to the root SSH password

## Run

```bash
BASE="accelerators/cloudera-base-732-kerberos"
VM="34.26.137.154"

scp ${BASE}/scripts/08_autotls.py root@${VM}:/opt/cloudera-install/scripts/
scp ${BASE}/config.env root@${VM}:/opt/cloudera-install/

ssh root@${VM} "cd /opt/cloudera-install && source config.env && export SSH_PASSWORD='Cl0ud3ra@Base732#SE' && python3.11 scripts/08_autotls.py"
```

This takes 15-30 minutes. After success:
- CM UI moves to `https://34.26.137.154:7183`
- All service configs update to use TLS
- All API calls must use HTTPS with `verify=False` (self-signed CM CA)

If it fails at `generateCmca`:
- Check CM has SSH access to itself: `ssh root@cdp.se-indo.lab hostname`
- Verify SSH_PASSWORD is correct

After completion, update `CM_PORT=7183` in config.env.
