#!/usr/bin/env bash

# Copyright (c) 2011 Cloudera, Inc. All rights reserved.
# Patched for FreeIPA on RHEL 9:
#   FreeIPA does not grant KADMIN add/xst privileges to external clients via
#   the standard kadmin protocol.  Instead:
#     1. ipa service-add  — registers the service in FreeIPA (idempotent)
#     2. ipa-getkeytab    — generates new random keys and writes the keytab
#   This uses FreeIPA's native LDAP interface and works with admin@REALM.
#   IPA admin password is read from /etc/cloudera/.ipa_admin_pass (written
#   by 06_kerberos_enable.py before the Kerberos enable phase).

set -e
set -x

# Explicitly add RHEL5/6, SLES11/12 locations to path
export PATH=$PATH:/usr/kerberos/bin:/usr/kerberos/sbin:/usr/lib/mit/sbin:/usr/sbin:/usr/lib/mit/bin:/usr/bin

CMF_REALM=${CMF_PRINCIPAL##*\@}

KEYTAB_OUT=$1
PRINC=$2
MAX_RENEW_LIFE=$3

KADMIN="kadmin -k -t $CMF_KEYTAB_FILE -p $CMF_PRINCIPAL -r $CMF_REALM"

RENEW_ARG=""

gen_credentials () {
  if [ $MAX_RENEW_LIFE -gt 0 ]; then
    RENEW_ARG="-maxrenewlife \"$MAX_RENEW_LIFE sec\""
  fi

  if [ -z "$KRB5_CONFIG" ]; then
    echo "Using system default krb5.conf path."
  else
    echo "Using custom config path '$KRB5_CONFIG', contents below:"
    cat $KRB5_CONFIG
  fi

  if which ipa > /dev/null 2>&1 || [ -f /etc/ipa/default.conf ]; then
    # ── FreeIPA path ──────────────────────────────────────────────────────
    # KADMIN addprinc/xst are blocked for external clients in FreeIPA.
    # Use the IPA CLI and ipa-getkeytab instead.

    IPA_REALM=$(awk '/^\s*default_realm\s*=/ {print $3}' /etc/krb5.conf 2>/dev/null | head -1)
    [ -z "$IPA_REALM" ] && IPA_REALM="$CMF_REALM"

    IPA_SERVER=$(grep -i "^host" /etc/ipa/default.conf 2>/dev/null \
                 | awk -F= '{gsub(/ /,""); print $2}' | head -1)
    [ -z "$IPA_SERVER" ] && IPA_SERVER=$(hostname 2>/dev/null || echo "localhost")

    IPA_CACERT=/etc/ipa/ca.crt
    CACERT_ARG=""
    [ -f "$IPA_CACERT" ] && CACERT_ARG="--cacert=${IPA_CACERT}"

    # Get an admin TGT so ipa CLI and ipa-getkeytab can authenticate
    IPA_ADMIN_PASS_FILE=/etc/cloudera/.ipa_admin_pass
    if [ ! -f "$IPA_ADMIN_PASS_FILE" ]; then
      echo "ERROR: $IPA_ADMIN_PASS_FILE not found."
      echo "  Write the IPA admin password there before running Kerberos setup."
      exit 1
    fi
    IPA_ADMIN_PASS=$(cat "$IPA_ADMIN_PASS_FILE")
    echo "$IPA_ADMIN_PASS" | kinit admin@${IPA_REALM}

    # Register the service in IPA (idempotent — ignore "already exists")
    set +e
    ipa service-add "${PRINC}" 2>&1
    set -e

    # Generate new random keys and write the keytab
    ipa-getkeytab -s "${IPA_SERVER}" -p "${PRINC}" -k "${KEYTAB_OUT}" ${CACERT_ARG}

    kdestroy 2>/dev/null || true
  else
    # ── Original MIT KDC path ─────────────────────────────────────────────
    $KADMIN -q "addprinc $RENEW_ARG -randkey $PRINC"

    if [ $MAX_RENEW_LIFE -gt 0 ]; then
      RENEW_LIFETIME=`$KADMIN -q "getprinc -terse $PRINC" | tail -1 | cut -f 12`
      if [ $RENEW_LIFETIME -eq 0 ]; then
        echo "Unable to set maxrenewlife"
        exit 1
      fi
    fi

    $KADMIN -q "xst -k $KEYTAB_OUT $PRINC"
  fi

  chmod 600 $KEYTAB_OUT
}

# Prepends a timestamp to each line of the stdout
adddate() {
    while IFS= read -r line; do
        printf '%s %s\n' "$(date)" "$line";
    done
}

gen_credentials | adddate
exit ${PIPESTATUS[0]}
