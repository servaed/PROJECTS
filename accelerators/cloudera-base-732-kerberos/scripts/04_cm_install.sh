#!/usr/bin/env bash
# =============================================================================
# 04_cm_install.sh — Install Cloudera Manager 7.13.2 on CM_HOST
# Platform: RHEL 9 | CM 7.13.2 is required for Runtime 7.3.2
# Java: OpenJDK 17 ONLY (JDK 8 and 11 removed in CM 7.13.2)
# Python: 3.11 ONLY (earlier versions discontinued in CM 7.13.2)
# Reference: https://docs.cloudera.com/cdp-private-cloud-base/7.1.9/installation/topics/cdpdc-configure-repository.html
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config.env"

log() { echo "[$(date '+%H:%M:%S')] [cm_install] $*"; }

# --- 1. Validate Java 17 is installed (required before CM install) ---
log "Checking Java 17"
if ! java -version 2>&1 | grep -q "17\."; then
    log "Installing OpenJDK 17 (required by CM 7.13.2)"
    dnf install -y java-17-openjdk-headless java-17-openjdk-devel
fi
JAVA_BIN="$(alternatives --list 2>/dev/null | awk '/^java\s/{print $3}' | grep 'java-17' | head -1)"
if [[ -n "${JAVA_BIN}" ]]; then
    alternatives --set java "${JAVA_BIN}"
fi
export JAVA_HOME="$(dirname $(dirname $(readlink -f $(which java))))"
java -version

# --- 2. Validate Python 3.11 is installed ---
log "Checking Python 3.11"
if ! python3.11 --version &>/dev/null; then
    log "Installing Python 3.11 (required by CM 7.13.2)"
    dnf install -y python3.11 python3.11-pip
fi
python3.11 --version

# --- 3. Configure Cloudera Manager repo for RHEL 9 ---
# Repo path pattern: /p/cm7/<version>/redhat9/yum — confirmed from official docs
log "Configuring Cloudera Manager ${CM_VERSION} repository"
cat > /etc/yum.repos.d/cloudera-manager.repo <<EOF
[cloudera-manager]
name=Cloudera Manager ${CM_VERSION}
baseurl=${CM_REPO_BASE}/
gpgkey=${CM_REPO_BASE}/RPM-GPG-KEY-cloudera
gpgcheck=1
enabled=1
autorefresh=0
type=rpm-md
EOF

# Import GPG key
log "Importing Cloudera GPG key"
rpm --import "${CM_REPO_BASE}/RPM-GPG-KEY-cloudera"

# --- 4. Install Cloudera Manager packages ---
log "Installing Cloudera Manager packages"
# cloudera-manager-daemons: CM Agent daemon
# cloudera-manager-agent:   CM Agent (installs on all managed nodes too)
# cloudera-manager-server:  CM Server (only on CM_HOST)
dnf install -y \
    cloudera-manager-daemons \
    cloudera-manager-agent \
    cloudera-manager-server

# --- 5. Configure CM Agent to point to CM server ---
log "Configuring CM Agent server address"
sed -i "s/^server_host=.*/server_host=${CM_HOST}/" \
    /etc/cloudera-scm-agent/config.ini

# --- 6. Initialize the CM database with scm_prepare_database.sh ---
# Syntax: scm_prepare_database.sh <dbType> <dbName> <dbUser> <dbPass>
# -h: remote DB host (use localhost if co-located)
# This script creates /etc/cloudera-scm-server/db.properties
log "Running scm_prepare_database.sh for PostgreSQL"
# Syntax: scm_prepare_database.sh [options] <type> <db> <user> <password>
# -h = host, NO port flag needed when using default PG port 5432
# Do NOT use -p (that is the admin password flag, not port — port flag is capital -P)
/opt/cloudera/cm/schema/scm_prepare_database.sh \
    -h "${DB_HOST}" \
    postgresql \
    "${DB_SCM}" \
    "${USER_SCM}" \
    "${PASS_SCM}"

log "db.properties written to /etc/cloudera-scm-server/db.properties"
cat /etc/cloudera-scm-server/db.properties

# --- 6a. Install psycopg2-binary for Hue PostgreSQL support ---
# Hue's Django ORM requires psycopg2 when using PostgreSQL as the Hue backend DB.
# Must be installed in the system python3.11 that Hue uses for its DB migration check.
log "Installing psycopg2-binary for Hue (PostgreSQL support)"
PARCEL_HUE_PIP="/opt/cloudera/parcels/CDH/lib/hue/build/env/bin/pip"
python3.11 -m pip install --quiet psycopg2-binary
# Also install in Hue's bundled virtualenv if the parcel is already present
if [[ -f "${PARCEL_HUE_PIP}" ]]; then
    "${PARCEL_HUE_PIP}" install psycopg2-binary --quiet || true
fi

# --- 7. Allow CM to accept requests from any IP / host header ---
# Required to access CM UI via external IP or any hostname (e.g. GCP external IP)
log "Enabling CMF_FF_PREVENT_HOST_HEADER_INJECTION=false"
sed -i 's/^# *export CMF_FF_PREVENT_HOST_HEADER_INJECTION.*/export CMF_FF_PREVENT_HOST_HEADER_INJECTION="false"/' \
    /etc/default/cloudera-scm-server

# --- 8. Start Cloudera Manager Server ---
log "Starting cloudera-scm-server"
systemctl enable --now cloudera-scm-server

# --- 8. Start Cloudera Manager Agent (on CM node itself) ---
log "Starting cloudera-scm-agent"
systemctl enable --now cloudera-scm-agent

# --- 9. Wait for CM API to become available ---
log "Waiting for CM API to be ready (may take 2-3 minutes)"
MAX_WAIT=300
INTERVAL=10
ELAPSED=0
while [[ "${ELAPSED}" -lt "${MAX_WAIT}" ]]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        "http://localhost:${CM_PORT}/api/version" \
        -u "${CM_ADMIN_USER}:${CM_ADMIN_PASS}" 2>/dev/null || echo "000")
    if [[ "${HTTP_CODE}" == "200" ]]; then
        log "CM API is ready (HTTP ${HTTP_CODE})"
        break
    fi
    log "  CM not ready yet (HTTP ${HTTP_CODE}), waiting ${INTERVAL}s... (${ELAPSED}/${MAX_WAIT}s)"
    sleep "${INTERVAL}"
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [[ "${ELAPSED}" -ge "${MAX_WAIT}" ]]; then
    log "ERROR: CM did not start within ${MAX_WAIT}s. Check logs:"
    log "  tail -100 /var/log/cloudera-scm-server/cloudera-scm-server.log"
    exit 1
fi

# --- 10. Retrieve and log the discovered CM API version ---
API_VER=$(curl -s "http://localhost:${CM_PORT}/api/version" \
    -u "${CM_ADMIN_USER}:${CM_ADMIN_PASS}" 2>/dev/null || echo "unknown")
log "CM API version: ${API_VER}"

log "Cloudera Manager ${CM_VERSION} installation complete"
log "  Admin UI:  http://${CM_HOST}:${CM_PORT}"
log "  API base:  http://${CM_HOST}:${CM_PORT}/api/${CM_API_VERSION}"
log "  Logs:      /var/log/cloudera-scm-server/cloudera-scm-server.log"
