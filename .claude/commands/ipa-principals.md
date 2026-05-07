# /ipa-principals

List all Kerberos service principals registered in FreeIPA and their keytab status.

## Arguments
`$ARGUMENTS` — optional filter (e.g. `hdfs`, `yarn`, `missing`). Default: show all.

## Run

```bash
FILTER="${ARGUMENTS:-}"
ssh root@34.26.137.154 'bash -s' << SCRIPT
echo "Cl0ud3ra@Base732#SE" | kinit admin@SE-INDO.LAB 2>/dev/null

echo "=== Service Principals in FreeIPA ==="
ipa service-find 2>/dev/null | grep -E "Principal name:|Keytab:" | paste - - | \
  awk '{print $3, $6}' | sort

echo ""
echo "=== Users with Kerberos principals ==="
ipa user-find 2>/dev/null | grep -E "User login:|Principal name:" | paste - - | head -20

echo ""
TOTAL_SVC=\$(ipa service-find 2>/dev/null | grep -c "Principal name:" || echo 0)
HAS_KT=\$(ipa service-find 2>/dev/null | grep -c "Keytab: True" || echo 0)
echo "Services: \$TOTAL_SVC total, \$HAS_KT with keytabs, \$((\$TOTAL_SVC - \$HAS_KT)) missing"
SCRIPT
```

If `$ARGUMENTS` is `missing`, only show services with `Keytab: False`.
If `$ARGUMENTS` is a service name (e.g. `hdfs`), show just that service's details:
```bash
ssh root@34.26.137.154 "echo 'Cl0ud3ra@Base732#SE' | kinit admin@SE-INDO.LAB 2>/dev/null && ipa service-show '${ARGUMENTS}/cdp.se-indo.lab@SE-INDO.LAB' 2>&1"
```
