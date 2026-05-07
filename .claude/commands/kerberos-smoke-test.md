# /kerberos-smoke-test

Run smoke tests to verify Kerberos is working end-to-end on the CDP cluster.

## Tests to run (on the VM via SSH)

```bash
ssh root@34.26.137.154 'bash -s' << 'TESTS'
set -e
PASS="Cl0ud3ra@Base732#SE"
REALM="SE-INDO.LAB"

echo "=== TEST 1: kinit as admin ==="
kdestroy 2>/dev/null || true
echo "$PASS" | kinit admin@$REALM
klist | grep "Default principal"
echo "PASS: admin kinit"

echo ""
echo "=== TEST 2: HDFS access ==="
sudo -u hdfs kinit -k -t /var/run/cloudera-scm-server/process/*/hdfs.keytab hdfs/cdp.se-indo.lab@$REALM 2>/dev/null || \
  kinit -k -t /etc/security/keytabs/hdfs.keytab hdfs/cdp.se-indo.lab@$REALM 2>/dev/null || \
  echo "SKIP: hdfs keytab not at expected path"
hdfs dfs -ls / 2>&1 | head -5

echo ""
echo "=== TEST 3: IPA service principals ==="
echo "$PASS" | kinit admin@$REALM
COUNT=$(ipa service-find 2>/dev/null | grep -c "Principal name:" || echo 0)
echo "IPA services registered: $COUNT"
[ "$COUNT" -gt 5 ] && echo "PASS: services registered" || echo "WARN: fewer than expected"

echo ""
echo "=== TEST 4: Check CM health ==="
KDESTROY
echo "All tests complete"
TESTS
```

Report each test result clearly: PASS / FAIL / SKIP with the reason.
If any test fails, suggest the fix based on the error message.
