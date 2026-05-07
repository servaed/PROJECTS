# /cluster-deploy

Run the full cluster deployment (phase 6) — deploys all 20 CDP services via `importClusterTemplate`. Use after CM and CMS are running.

## What this does
1. Syncs `05_cluster_deploy.py` to the VM
2. Runs it — downloads parcel, distributes, activates, then imports the cluster template with all 20 services
3. Polls until cluster is fully deployed and all first-run commands complete

## Pre-conditions
- CM is running: `https://34.26.137.154:7183`
- CMS is running (phase 5 complete)
- PostgreSQL databases exist (phase 3 complete)

## Run

```bash
BASE="accelerators/cloudera-base-732-kerberos"
VM="34.26.137.154"

scp ${BASE}/scripts/05_cluster_deploy.py root@${VM}:/opt/cloudera-install/scripts/
scp ${BASE}/config.env root@${VM}:/opt/cloudera-install/

ssh root@${VM} "cd /opt/cloudera-install && source config.env && export CM_PORT=7183 && python3.11 scripts/05_cluster_deploy.py"
```

This takes 20-40 minutes. Show all output.

If it fails, check:
- Parcel URL: `PARCEL_REPO` in config.env must be `archive.cloudera.com/p/cdh7/7.3.2/parcels/`
- Parcel build string: must match manifest.json (currently `7.3.2-1.cdh7.3.2.p0.77083870`)
- Database passwords: must match what was set in phase 3
- Service template variables: Hue must have `database_port=5432`, Ranger must have `ranger_database_type=postgresql` (lowercase)
