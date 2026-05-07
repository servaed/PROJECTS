# /keytab-verify

Verify that a Kerberos keytab for a specific service works (`kinit -k -t`).

## Arguments
`$ARGUMENTS` — service name. Examples: `hdfs`, `yarn`, `hive`, `ranger`, `HTTP`. Required.

## Run

```bash
SVC="$ARGUMENTS"
HOST="cdp.se-indo.lab"
REALM="SE-INDO.LAB"
PRINC="${SVC}/${HOST}@${REALM}"

ssh root@34.26.137.154 "bash -s" << SCRIPT
echo "Testing keytab for: ${PRINC}"

# Find keytab files for this service
echo "=== Keytab files on disk ==="
find /var/run/cloudera-scm-server /etc/security/keytabs /run -name "*.keytab" 2>/dev/null | xargs -I{} sh -c 'klist -k {} 2>/dev/null | grep -q "${SVC}/" && echo "{}"' 2>/dev/null | head -5

# Try kinit with first keytab found
KT=\$(find /var/run/cloudera-scm-server /etc/security/keytabs /run -name "*.keytab" 2>/dev/null | xargs -I{} sh -c 'klist -k {} 2>/dev/null | grep -q "${SVC}/" && echo "{}"' 2>/dev/null | head -1)

if [ -n "\$KT" ]; then
  echo ""
  echo "=== kinit test with \$KT ==="
  kinit -k -t "\$KT" "${PRINC}" 2>&1 && echo "PASS: kinit succeeded" || echo "FAIL: kinit failed"
  klist 2>/dev/null
  kdestroy 2>/dev/null
else
  echo "WARN: No keytab found for ${SVC} on disk"
  echo "Service principal in IPA:"
  echo "Cl0ud3ra@Base732#SE" | kinit admin@${REALM} 2>/dev/null
  ipa service-show "${PRINC}" 2>&1 | grep -E "Principal|Keytab"
fi
SCRIPT
```

Report PASS/FAIL clearly. If fail, check if the service principal exists in IPA and if `generateCredentials` needs to be re-run.
