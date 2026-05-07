#!/usr/bin/env bash
# =============================================================================
# 02_freeipa_client.sh — Enroll a node into the FreeIPA domain
# Platform: RHEL 9 | Run on CM_HOST and each WORKER_HOST (not on IPA_HOST)
# Reference: https://docs.cloudera.com/cdp-private-cloud-base/7.1.8/security-kerberos-authentication/
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config.env"

log() { echo "[$(date '+%H:%M:%S')] [freeipa_client] $*"; }

# --- 1. Install FreeIPA client and Kerberos packages ---
# On RHEL 9: packages available directly in AppStream — no module enable needed
log "Installing freeipa-client and Kerberos packages"
# krb5-workstation / krb5-libs / openldap-clients: required by Cloudera per security guide
dnf install -y freeipa-client krb5-workstation krb5-libs openldap-clients

# --- 3. Run ipa-client-install (unattended) ---
# --mkhomedir: creates home directories on first login (PAM integration)
# --enable-dns-updates: registers this host's A record in FreeIPA DNS
log "Enrolling this host into IPA domain: ${DOMAIN} / realm: ${REALM}"
ipa-client-install \
    --domain="${DOMAIN}" \
    --realm="${REALM}" \
    --server="${IPA_HOST}" \
    --principal="admin" \
    --password="${IPA_ADMIN_PASS}" \
    --hostname="$(hostname -f)" \
    --mkhomedir \
    --enable-dns-updates \
    --no-ntp \
    --unattended

log "IPA client enrollment complete"

# --- 4. Apply udp_preference_limit=1 to krb5.conf ---
# This is REQUIRED by Cloudera security guide to prevent Kerberos library
# issues that can prevent cluster startup (TCP fallback for large tickets)
log "Patching /etc/krb5.conf: setting udp_preference_limit = 1"
if grep -q 'udp_preference_limit' /etc/krb5.conf; then
    sed -i 's/^\s*udp_preference_limit.*/  udp_preference_limit = 1/' /etc/krb5.conf
else
    # Insert under the [libdefaults] section
    sed -i '/^\[libdefaults\]/a\  udp_preference_limit = 1' /etc/krb5.conf
fi

# Verify the setting is present
grep 'udp_preference_limit' /etc/krb5.conf

# --- 5. Verify ticket acquisition (smoke test) ---
log "Smoke test: kinit as admin"
echo "${IPA_ADMIN_PASS}" | kinit admin && klist && kdestroy
log "Kerberos ticket acquisition successful"

log "FreeIPA client setup complete on $(hostname -f)"
