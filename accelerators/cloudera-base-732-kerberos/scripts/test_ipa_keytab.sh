#!/usr/bin/env bash
set -x
PASS="Cl0ud3ra@Base732#SE"
IPA_SERVER=$(grep -i "^host" /etc/ipa/default.conf 2>/dev/null | awk -F= '{gsub(/ /,""); print $2}' | head -1)
echo "IPA_SERVER=${IPA_SERVER}"
echo "$PASS" | kinit admin@SE-INDO.LAB
printf "%s\n%s\n" "$PASS" "$PASS" | \
  ipa-getkeytab -s "${IPA_SERVER}" -p admin@SE-INDO.LAB -k /tmp/pre_test.keytab -P --cacert=/etc/ipa/ca.crt 2>&1
ls -la /tmp/pre_test.keytab 2>/dev/null
kinit -k -t /tmp/pre_test.keytab admin@SE-INDO.LAB 2>&1 && echo "PRE-TEST PASSED" || echo "PRE-TEST FAILED"
rm -f /tmp/pre_test.keytab
kdestroy 2>/dev/null
