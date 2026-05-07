#!/usr/bin/env bash
# =============================================================================
# 01_freeipa_server.sh — Install FreeIPA server with integrated DNS on IPA_HOST
# Platform: RHEL 9 | Run ONLY on the IPA_HOST node
# Reference: https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/installing_identity_management/
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config.env"

log() { echo "[$(date '+%H:%M:%S')] [freeipa_server] $*"; }

# --- 1. Verify hostname resolves correctly before starting ---
log "Pre-flight: checking hostname and DNS resolution"
CURRENT_HOSTNAME="$(hostname -f)"
log "  FQDN: ${CURRENT_HOSTNAME}"
# Forward lookup must succeed; FreeIPA installer requires it
if ! host "${IPA_HOST}" &>/dev/null; then
    log "WARNING: ${IPA_HOST} does not resolve via DNS. IPA installer will use /etc/hosts."
fi

# --- 2. Install FreeIPA server packages ---
# On RHEL 9: ipa-server is in AppStream directly — no module enable needed
# (idm:DL1 module was a RHEL 8 construct; RHEL 9 ships packages directly)
log "Installing ipa-server and ipa-server-dns"
dnf install -y ipa-server ipa-server-dns

# --- 4. Firewall — GCP deployment: firewalld is disabled, VPC handles security ---
log "Firewall: skipping firewall-cmd (GCP VPC handles network security)"
# For non-GCP bare-metal, uncomment:
# systemctl enable --now firewalld
# firewall-cmd --permanent --add-service={freeipa-ldap,freeipa-ldaps,dns,kerberos,kpasswd,http,https,ntp}
# firewall-cmd --reload

# --- 5. Run ipa-server-install (unattended) ---
# --setup-dns: integrated DNS (required for FreeIPA to manage host A/PTR records)
# --no-reverse: skip auto-creating reverse zone (add manually if needed)
# udp_preference_limit is handled on client nodes (02_freeipa_client.sh)
log "Running ipa-server-install (this takes 5-10 minutes)"
ipa-server-install \
    --realm="${REALM}" \
    --domain="${DOMAIN}" \
    --ds-password="${IPA_DM_PASS}" \
    --admin-password="${IPA_ADMIN_PASS}" \
    --hostname="${IPA_HOST}" \
    --setup-dns \
    --forwarder="${DNS_SERVER}" \
    --no-reverse \
    --no-ntp \
    --unattended

log "FreeIPA server installation complete"

# --- 6. Authenticate as IPA admin for subsequent ipa commands ---
log "Obtaining Kerberos ticket for admin"
echo "${IPA_ADMIN_PASS}" | kinit admin

# --- 7. Add DNS A-records for all cluster hosts ---
# This is needed if FreeIPA is the authoritative DNS for the cluster domain
log "Adding DNS records for cluster nodes"
for host_entry in ${ALL_HOST_IPS:-}; do
    ip="${host_entry%%:*}"
    fqdn="${host_entry##*:}"
    short="${fqdn%%.*}"
    log "  Adding A record: ${short} → ${ip}"
    ipa dnsrecord-add "${DOMAIN}." "${short}" --a-rec="${ip}" 2>/dev/null || \
        log "  (record already exists for ${short})"
done

# --- 8. Create the Cloudera Manager Kerberos admin account ---
# CM Kerberos wizard creates its own cmadin-<id> service account; this admin
# account is used during the wizard to authorize that creation.
# If you pass 'admin' credentials to the wizard, step 8 is informational only.
log "Creating Cloudera-specific IPA user and role (optional — CM wizard can use admin)"
ipa user-add cmkrbadmin \
    --first="Cloudera" \
    --last="KrbAdmin" \
    --password <<< "${KRB5_ADMIN_PASS}
${KRB5_ADMIN_PASS}" 2>/dev/null || log "  cmkrbadmin already exists"

ipa role-add "Cloudera Manager Kerberos Admin" 2>/dev/null || true
ipa role-add-privilege "Cloudera Manager Kerberos Admin" \
    --privileges="Service Administrators" \
    --privileges="Host Administrators" 2>/dev/null || true
ipa role-add-member "Cloudera Manager Kerberos Admin" \
    --users=cmkrbadmin 2>/dev/null || true

# --- 9. Set default Kerberos ticket policy suitable for Cloudera services ---
log "Setting default Kerberos ticket policy"
ipa krbtpolicy-mod --maxlife=86400 --maxrenew=604800 2>/dev/null || true

# --- 10. Verify IPA is running ---
log "Verifying IPA services"
ipactl status

log "FreeIPA server setup complete on ${IPA_HOST}"
log "  Realm:  ${REALM}"
log "  Domain: ${DOMAIN}"
log "  Admin:  admin / (IPA_ADMIN_PASS)"
log "  WebUI:  https://${IPA_HOST}/ipa/ui"
