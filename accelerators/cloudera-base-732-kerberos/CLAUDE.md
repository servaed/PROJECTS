# CLAUDE.md — Cloudera Base 7.3.2 + FreeIPA Kerberos Automation

## Project Purpose
Automation scripts to install **CDP Private Cloud Base 7.3.2** (Cloudera Manager + CDH Runtime) on RHEL 9 with **Kerberos authentication enabled via FreeIPA** as the KDC.

Intended audience: Cloudera presales engineers and field SEs deploying secure lab/POC clusters.

## Stack
| Component | Version | Notes |
|---|---|---|
| OS | RHEL 9 | Certified: RHEL 9.6 (also Rocky 9.6) |
| Cloudera Manager | 7.13.2 | **Required** for Runtime 7.3.2 — confirmed in [release summary](https://docs.cloudera.com/cdp-private-cloud/latest/release-summaries/topics/announcement-202603-732.html) |
| CDP Runtime parcel | 7.3.2.0 | `el9` build required |
| FreeIPA | 4.10.x | Ships in RHEL 9 AppStream via `idm:DL1` module |
| PostgreSQL | 14 or 15 | PG 13 support removed in 7.3.2; use PGDG repo |
| Java | **OpenJDK 17 only** | JDK 8 and JDK 11 support **removed** in 7.3.2 |
| Python | **3.11 only** | Python 3.8/3.9/3.10 discontinued in CM 7.13.2 |

## Directory Layout
```
cloudera-base-732-kerberos/
├── CLAUDE.md                  ← this file
├── config.env                 ← ALL variables; edit this first
├── install.sh                 ← main orchestrator (source config.env, call phases)
└── scripts/
    ├── 00_system_prep.sh      ← run on ALL nodes: NTP, hostnames, firewalld, Java
    ├── 01_freeipa_server.sh   ← install FreeIPA server + DNS on IPA_HOST
    ├── 02_freeipa_client.sh   ← enroll all other nodes as FreeIPA clients
    ├── 03_postgres_setup.sh   ← install PG 14, create CM service databases
    ├── 04_cm_install.sh       ← install CM packages, run scm_prepare_database.sh
    ├── 05_cluster_deploy.py   ← CM REST API: add hosts, deploy parcels, create services
    └── 06_kerberos_enable.py  ← CM REST API: import KDC credentials, enable Kerberos
```

## Execution Order
1. Edit `config.env` — set all hostnames, passwords, parcel URLs
2. Run `install.sh` on the CM host (it SSHes out to other nodes as needed)
3. Each phase script is idempotent where possible; re-run a phase safely

## Key Design Decisions
- **PostgreSQL over MariaDB**: better RHEL 9 support; Ranger requires PG 12+
- **FreeIPA as KDC**: Cloudera's wizard accepts MIT-compatible KDC; FreeIPA exposes standard Kerberos interface — use `KDC type: MIT KDC` in the CM wizard
- **CM API v51**: used by 05_cluster_deploy.py and 06_kerberos_enable.py; compatible with CM 7.9+
- **No auto-TLS in initial install**: TLS can be enabled post-cluster via CM UI → Administration → Settings → TLS
- **SELinux**: set to `permissive` during install; re-enable with targeted policy after cluster is up

## Common Issues

### GCP-Specific (confirmed in live testing — May 2026)
- **`firewall-cmd` fails with `No module named 'gi'`**: firewalld is disabled on GCP (`systemctl disable firewalld`). VPC firewall handles security. All `firewall-cmd` calls in scripts are commented out for GCP.
- **`idm:DL1` module not found**: On RHEL 9.6 GCP, `ipa-server` installs directly from AppStream — no `dnf module enable` needed. The module was a RHEL 8 construct.
- **`python3` override breaks system tools**: Installing Python 3.11 with `alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1` overrides the system Python and breaks `firewall-cmd`, `ipa-server-install`, and any tool using `#!/usr/bin/python3`. Fix: install Python 3.11 as a side-by-side binary only (`/usr/bin/python3.11`); never override `python3`.
- **`ipa-server-install` hostname mismatch**: GCP writes `10.x.x.x <gcp-fqdn>` into `/etc/hosts` and GCP DNS reverse-resolves the internal IP to the GCP FQDN. This conflicts with custom hostnames. Fix: remove GCP's `/etc/hosts` entry for the internal IP and insert our FQDN first. Also remove `myhostname` from `/etc/nsswitch.conf` `hosts` line to prevent IPv6 link-local from winning forward lookups.
- **`getent hosts <fqdn>` returns IPv6**: `myhostname` in `nsswitch.conf` injects link-local IPv6 for the machine hostname. Fix: `sed -i 's/^hosts:.*/hosts:      files dns/' /etc/nsswitch.conf`

### General
- **Parcel download fails**: verify `CLOUDERA_REPO_USER`/`CLOUDERA_REPO_PASS` in config.env are correct
- **Clock skew error**: chrony must be synced before Kerberos; run `chronyc tracking` to verify
- **CM API 503 on first call**: CM takes ~2 min to fully start after `systemctl start cloudera-scm-server`

## GCP Compute Engine Deployment Notes

### Recommended Instance Configuration
| Node | Machine Type | Boot Disk | Data Disks | Notes |
|---|---|---|---|---|
| IPA | `e2-standard-2` | 50 GB RHEL 9 | — | Lightweight IdM server |
| CM | `e2-standard-4` | 100 GB RHEL 9 | — | Runs CM Server + Agent + PostgreSQL |
| Worker (×3) | `e2-standard-8` | 100 GB RHEL 9 | 2× 500 GB SSD (pd-ssd) | DataNode + NodeManager |

### Required Setup Before Running install.sh

1. **OS image**: Use `rhel-9` public image family (`--image-project=rhel-cloud`)
2. **Network**: All nodes in the same VPC subnet with internal DNS or update `/etc/hosts` via `ALL_HOST_IPS` in config.env
3. **Firewall rules**: GCP VPC firewall (not `firewall-cmd`) controls ingress — create rules to allow:
   - Internal: all traffic between nodes on the subnet (tag-based or subnet CIDR)
   - External: TCP 7180 (CM UI), 8443 (Knox), 8888 (Hue) from your IP
4. **SSH key**: Add your public key to GCP project metadata OR instance metadata; set `SSH_KEY_PATH` in config.env
5. **RHEL subscription**: GCP RHEL images are pay-as-you-go (no subscription needed); `dnf` works out of the box
6. **DNS**: Set `DNS_SERVER` to GCP's internal DNS `169.254.169.254` — but FreeIPA will override this. Alternatively use FreeIPA's integrated DNS (default in the scripts)
7. **Hostname**: GCP sets FQDN automatically based on the instance name; verify with `hostname -f` before running

### GCP Instance Creation Example (gcloud)
```bash
# Create all nodes — adjust project/zone/subnet as needed
PROJECT="your-gcp-project"
ZONE="asia-southeast2-a"    # Jakarta for Indonesia presales
SUBNET="default"
IMAGE_FAMILY="rhel-9"
IMAGE_PROJECT="rhel-cloud"

for node in ipa cm worker1 worker2 worker3; do
    TYPE="e2-standard-4"
    [[ "$node" == worker* ]] && TYPE="e2-standard-8"
    [[ "$node" == "ipa"   ]] && TYPE="e2-standard-2"

    gcloud compute instances create "${node}.example.com" \
        --project="${PROJECT}" \
        --zone="${ZONE}" \
        --machine-type="${TYPE}" \
        --subnet="${SUBNET}" \
        --image-family="${IMAGE_FAMILY}" \
        --image-project="${IMAGE_PROJECT}" \
        --boot-disk-size=100GB \
        --boot-disk-type=pd-balanced \
        --metadata="enable-oslogin=false" \
        --tags=cloudera-cluster
done

# Allow internal traffic between tagged instances
gcloud compute firewall-rules create allow-cloudera-internal \
    --network=default \
    --allow=all \
    --source-tags=cloudera-cluster \
    --target-tags=cloudera-cluster

# Allow CM UI and Hue from your workstation
gcloud compute firewall-rules create allow-cloudera-ui \
    --network=default \
    --allow=tcp:7180,tcp:7183,tcp:8888,tcp:8443,tcp:6080 \
    --source-ranges="YOUR_PUBLIC_IP/32" \
    --target-tags=cloudera-cluster
```

### config.env Adjustment for GCP
- Set `ALL_HOST_IPS` to `"<ip1>:ipa.example.com <ip2>:cm.example.com ..."` using internal IPs
- Use internal IP for `DNS_SERVER` if not using FreeIPA DNS
- `DEPLOY_USER` is typically your GCP OS Login username or `root`

## References
- [CM Installation Guide RHEL 9](https://docs.cloudera.com/cdp-private-cloud-base/7.1.9/installation/topics/cdpdc-install-cm-rhel.html)
- [Enable Kerberos with FreeIPA](https://docs.cloudera.com/cdp-private-cloud-base/latest/security-kerberos-authentication/topics/cm-security-kerberos-enable-existing-mit-freeipa.html)
- [CM API v51 Reference](https://cloudera.github.io/cm_api/apidocs/v51/index.html)
- [CDP PVC Base Supported OS Matrix](https://docs.cloudera.com/cdp-private-cloud-base/latest/installation/topics/cdpdc-os-requirements.html)
