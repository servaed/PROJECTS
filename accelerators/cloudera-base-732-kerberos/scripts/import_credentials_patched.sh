#!/usr/bin/env bash
# Copyright (c) 2014 Cloudera, Inc. All rights reserved.
# Patched for FreeIPA on RHEL 9:
#   ipa-getkeytab -P replaces ktutil addent -password because FreeIPA uses
#   random per-user salts that ktutil cannot replicate (causes kinit failure).
#   This script is only called for HUMAN users (admin, cmadin-*).
#   Service principal keytabs are handled by gen_credentials_patched.sh.

set -e
set -x

export PATH=$PATH:/usr/kerberos/bin:/usr/kerberos/sbin:/usr/lib/mit/sbin:/usr/sbin:/usr/lib/mit/bin:/usr/bin

KEYTAB_OUT=$1
USER=$2
PASSWD=$3
KVNO=$4

if [ -z "$KRB5_CONFIG" ]; then
  echo "Using system default krb5.conf path."
else
  echo "Using custom config path '$KRB5_CONFIG', contents below:"
  cat $KRB5_CONFIG
fi

# FreeIPA / Red Hat IdM detection
# Use ipa-getkeytab -P instead of ktutil addent -password.
# Reason: FreeIPA stores Kerberos keys with random per-user salts; ktutil uses
# the default REALM+username salt → key mismatch → kinit -k -t fails.
# ipa-getkeytab -P re-derives the keytab from the existing password using the
# correct IPA-stored salt without changing the KDC keys or KVNO.
if which ipa-getkeytab > /dev/null 2>&1 || [ -f /etc/ipa/default.conf ]; then
  echo "FreeIPA detected: using ipa-getkeytab -P (avoids salt mismatch)"
  # /etc/ipa/default.conf uses 'host = ' key (not 'server=')
  IPA_SERVER=$(grep -i "^host" /etc/ipa/default.conf 2>/dev/null \
               | awk -F= '{gsub(/ /,""); print $2}' \
               | head -1)
  # Fallback to system hostname if not found
  [ -z "$IPA_SERVER" ] && IPA_SERVER=$(hostname 2>/dev/null || echo "localhost")
  echo "IPA server: $IPA_SERVER"
  # Step 1: kinit with password to get a TGT (required by ipa-getkeytab -P)
  echo "$PASSWD" | kinit $USER
  # Step 2: ipa-getkeytab -P re-derives keytab using the TGT for auth
  # --cacert: required after Auto-TLS since IPA LDAP uses TLS
  IPA_CACERT=/etc/ipa/ca.crt
  CACERT_ARG=""
  [ -f "$IPA_CACERT" ] && CACERT_ARG="--cacert=${IPA_CACERT}"
  printf "%s\n%s\n" "$PASSWD" "$PASSWD" | \
    ipa-getkeytab -s "${IPA_SERVER}" -p "${USER}" -k "${KEYTAB_OUT}" -P ${CACERT_ARG}
  kdestroy 2>/dev/null || true
else
  # Original MIT KDC approach (ktutil addent -password)
  SLEEP=0
  RHEL_FILE=/etc/redhat-release
  if [ -f $RHEL_FILE ]; then
    set +e
    grep Tikanga $RHEL_FILE
    [ $? -eq 0 ] && SLEEP=1
    [ $SLEEP -eq 0 ] && grep 'CentOS release 5' $RHEL_FILE && [ $? -eq 0 ] && SLEEP=1
    set -e
  fi
  IFS=' ' read -a ENC_ARR <<< "$ENC_TYPES"
  {
    for ENC in "${ENC_ARR[@]}"; do
      echo "addent -password -p $USER -k $KVNO -e $ENC"
      [ $SLEEP -eq 1 ] && sleep 1
      echo "$PASSWD"
    done
    echo "wkt $KEYTAB_OUT"
  } | ktutil
fi

chmod 600 $KEYTAB_OUT

# Validate the keytab with kinit
kinit -k -t $KEYTAB_OUT $USER

# AD-specific LDAP validation (not used for FreeIPA)
if [ "$AD_ADMIN" != "true" ]; then
  exit 0
fi
LDAP_CONF=$(mktemp /tmp/cm_ldap.XXXXXXXX)
echo "TLS_REQCERT     never" >> $LDAP_CONF
echo "sasl_secprops   minssf=0,maxssf=0" >> $LDAP_CONF
LDAP_URL="ldap://${AD_SERVER}:${LDAP_PORT}"
set +e
ldapsearch -LLL -H "$LDAP_URL" -b "$DOMAIN" "userPrincipalName=$USER"
if [ $? -ne 0 ]; then
  echo "ldapsearch failed with SASL, trying simple auth"
  LDAP_URL="ldaps://${AD_SERVER}:${LDAPS_PORT}"
  export LDAPCONF=$LDAP_CONF
  ldapsearch -LLL -H "$LDAP_URL" -b "$DOMAIN" -x -D $USER -w $PASSWD "userPrincipalName=$USER"
  if [ $? -ne 0 ]; then
    echo "Failed ldapsearch."; exit 1
  fi
  echo -n $PASSWD > $KEYTAB_OUT
fi
set -e
rm -f $LDAP_CONF
