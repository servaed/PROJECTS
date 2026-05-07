#!/usr/bin/env bash
# =============================================================================
# install.sh — Single-node Cloudera Base 7.3.2 + FreeIPA Kerberos orchestrator
# Platform: RHEL 9 | Run as root on the node itself
#
# Usage:
#   bash install.sh [--phase <n>] [--from <n>] [--dry-run]
#
# Phases:
#   0 — System prep (Java 17, Python 3.11, psycopg2, NTP, THP, data dirs)
#   1 — FreeIPA server (ipa-server-install, also enrolls this node as client)
#   2 — krb5.conf patch (udp_preference_limit=1)
#   3 — PostgreSQL 14 — all CM service databases
#   4 — Cloudera Manager 7.13.2 — install, scm_prepare_database, start
#   5 — Cloudera Management Service — Alert Publisher, Event Server,
#         Host Monitor, Reports Manager, Service Monitor
#   6 — Cluster deployment — 20 services via /cm/importClusterTemplate
#   7 — Auto-TLS — CM-managed CA, certificates for all hosts + services
#         (CM moves to HTTPS port 7183 after this phase)
#   8 — Kerberos enablement via CM API (requires TLS from phase 7)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.env"

START_PHASE=0
END_PHASE=8
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --phase)   START_PHASE="$2"; END_PHASE="$2"; shift 2 ;;
        --from)    START_PHASE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

log()       { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
phase_log() { echo; printf '=%.0s' {1..70}; echo; echo "[PHASE $1] $2"; printf '=%.0s' {1..70}; echo; }

run() {
    local script="$1"; shift
    if [[ "${DRY_RUN}" == "true" ]]; then
        log "[DRY-RUN] would run: bash ${script} $*"
    else
        bash "${script}" "$@"
    fi
}

run_py() {
    local script="$1"
    if [[ "${DRY_RUN}" == "true" ]]; then
        log "[DRY-RUN] would run: python3.11 ${script}"
    else
        python3.11 "${script}"
    fi
}

# =============================================================================
# PHASE 0: System preparation
# Installs: Java 17, Python 3.11, psycopg2-binary, Kerberos clients
# Creates: /data/dfs/*, /data/yarn/nm, /data/zookeeper, etc.
# Fixes:   /etc/hosts (GCP entry), nsswitch.conf (myhostname), firewalld disabled
# =============================================================================
if [[ "${START_PHASE}" -le 0 && "${END_PHASE}" -ge 0 ]]; then
    phase_log 0 "System preparation on ${NODE_HOST}"
    run "${SCRIPT_DIR}/scripts/00_system_prep.sh" "${NODE_HOST}"
    log "Phase 0 complete"
fi

# =============================================================================
# PHASE 1: FreeIPA server
# ipa-server-install enrolls this node as client automatically — no phase 2b
# =============================================================================
if [[ "${START_PHASE}" -le 1 && "${END_PHASE}" -ge 1 ]]; then
    phase_log 1 "FreeIPA server on ${NODE_HOST}"
    run "${SCRIPT_DIR}/scripts/01_freeipa_server.sh"
    log "Phase 1 complete"
fi

# =============================================================================
# PHASE 2: krb5.conf patch — udp_preference_limit=1
# Required by Cloudera security guide to prevent cluster startup failures
# =============================================================================
if [[ "${START_PHASE}" -le 2 && "${END_PHASE}" -ge 2 ]]; then
    phase_log 2 "Patching krb5.conf (udp_preference_limit=1)"
    if grep -q 'udp_preference_limit' /etc/krb5.conf; then
        sed -i 's/^\s*udp_preference_limit.*/  udp_preference_limit = 1/' /etc/krb5.conf
    else
        sed -i '/^\[libdefaults\]/a\  udp_preference_limit = 1' /etc/krb5.conf
    fi
    grep 'udp_preference_limit' /etc/krb5.conf
    log "Phase 2 complete"
fi

# =============================================================================
# PHASE 3: PostgreSQL 14
# =============================================================================
if [[ "${START_PHASE}" -le 3 && "${END_PHASE}" -ge 3 ]]; then
    phase_log 3 "PostgreSQL 14 setup"
    run "${SCRIPT_DIR}/scripts/03_postgres_setup.sh"
    log "Phase 3 complete"
fi

# =============================================================================
# PHASE 4: Cloudera Manager 7.13.2
# =============================================================================
if [[ "${START_PHASE}" -le 4 && "${END_PHASE}" -ge 4 ]]; then
    phase_log 4 "Cloudera Manager ${CM_VERSION} installation"
    run "${SCRIPT_DIR}/scripts/04_cm_install.sh"
    log "Phase 4 complete"
fi

# =============================================================================
# PHASE 5: Cloudera Management Service (CMS)
# Must run BEFORE cluster deployment — CMS provides Service Monitor and Host
# Monitor which CM uses during cluster setup and health checking.
# Roles: Alert Publisher, Event Server, Host Monitor, Reports Manager, Service Monitor
# =============================================================================
if [[ "${START_PHASE}" -le 5 && "${END_PHASE}" -ge 5 ]]; then
    phase_log 5 "Cloudera Management Service setup"
    run_py "${SCRIPT_DIR}/scripts/07_setup_cms.py"
    log "Phase 5 complete"
fi

# =============================================================================
# PHASE 6: Cluster deployment — 20 services via CM API
# Uses /cm/importClusterTemplate (hostTemplates + instantiator format for CM v58)
# =============================================================================
if [[ "${START_PHASE}" -le 6 && "${END_PHASE}" -ge 6 ]]; then
    phase_log 6 "Cluster deployment via CM API (20 services)"
    run_py "${SCRIPT_DIR}/scripts/05_cluster_deploy.py"
    log "Phase 6 complete"
fi

# =============================================================================
# PHASE 7: Auto-TLS — CM-managed CA
# CM generates its own CA, installs certs on all hosts via SSH, and restarts
# all services with TLS enabled. After this phase:
#   - CM UI is at https://{host}:7183  (port 7180 redirects)
#   - All API calls must use HTTPS
# Requires: SSH_PASSWORD env var set to root SSH password
# =============================================================================
if [[ "${START_PHASE}" -le 7 && "${END_PHASE}" -ge 7 ]]; then
    phase_log 7 "Auto-TLS (CM-managed CA)"
    if [[ -z "${SSH_PASSWORD:-}" ]]; then
        log "WARNING: SSH_PASSWORD not set — Auto-TLS requires it for certificate distribution"
        log "  Set it with: export SSH_PASSWORD='your-root-password'"
        log "  Skipping Auto-TLS (re-run with --phase 7 after setting SSH_PASSWORD)"
    else
        run_py "${SCRIPT_DIR}/scripts/08_autotls.py"
        log "Phase 7 complete — CM now at HTTPS port 7183"
        # Subsequent phases must use HTTPS
        export CM_PORT="7183"
        export CM_API="https://${CM_HOST}:${CM_PORT}/api/${CM_API_VERSION}"
    fi
fi

# =============================================================================
# PHASE 8: Kerberos enablement (requires Auto-TLS from phase 7)
# =============================================================================
if [[ "${START_PHASE}" -le 8 && "${END_PHASE}" -ge 8 ]]; then
    phase_log 8 "Kerberos enablement via CM API"
    run_py "${SCRIPT_DIR}/scripts/06_kerberos_enable.py"
    log "Phase 8 complete"
fi

# =============================================================================
# Summary
# =============================================================================
echo
printf '=%.0s' {1..70}; echo
echo " Cloudera Base 7.3.2 + FreeIPA Kerberos — Single Node Complete"
printf '=%.0s' {1..70}; echo
echo "  Node             : ${NODE_HOST}"
echo "  Cloudera Manager : http://${NODE_HOST}:${CM_PORT}"
echo "  Hue              : http://${NODE_HOST}:8888"
echo "  Ranger           : http://${NODE_HOST}:6080"
echo "  Atlas            : http://${NODE_HOST}:21000"
echo "  FreeIPA WebUI    : https://${NODE_HOST}/ipa/ui"
echo "  Realm            : ${REALM}"
echo ""
echo "  Smoke test:"
echo "    kinit admin && klist"
echo "    hdfs dfs -ls /"
printf '=%.0s' {1..70}; echo
