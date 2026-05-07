# /debug-kerberos

Deep-dive diagnostic for Kerberos issues. Collects all relevant state in one pass.

## Run

```bash
ssh root@34.26.137.154 'bash -s' << 'DIAG'
PASS="Cl0ud3ra@Base732#SE"
REALM="SE-INDO.LAB"
HOST="cdp.se-indo.lab"
CM_API="https://${HOST}:7183/api/v58"
AUTH_HEADER=$(echo -n "admin:${PASS}" | base64)

echo "════════════════════════════════════════"
echo " FreeIPA DIAGNOSIS"
echo "════════════════════════════════════════"

echo "[1] IPA service status"
ipactl status 2>&1 | head -10

echo ""
echo "[2] Admin kinit"
kdestroy 2>/dev/null
echo "$PASS" | kinit admin@$REALM 2>&1 && klist | grep "Default principal" || echo "FAIL"

echo ""
echo "[3] IPA service principals count"
ipa service-find 2>/dev/null | grep -c "Principal name:" | xargs echo "Total services:"
ipa service-find 2>/dev/null | grep "Keytab: False" | wc -l | xargs echo "Missing keytabs:"

echo ""
echo "[4] /etc/cloudera/.ipa_admin_pass"
ls -la /etc/cloudera/.ipa_admin_pass 2>/dev/null || echo "FILE MISSING"
stat -c "%U %G %a" /etc/cloudera/.ipa_admin_pass 2>/dev/null

echo ""
echo "[5] gen_credentials.sh header (FreeIPA patch check)"
head -6 /opt/cloudera/cm/bin/gen_credentials.sh

echo ""
echo "[6] import_credentials.sh header"
head -6 /opt/cloudera/cm/bin/import_credentials.sh

echo ""
echo "[7] CM kerberosInfo"
curl -sk -u "admin:${PASS}" "${CM_API}/cm/kerberosInfo" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'  {k}: {v}') for k,v in d.items() if k not in ('displayName','serviceUrl')]"

echo ""
echo "[8] Last 5 CM commands (cluster)"
curl -sk -u "admin:${PASS}" "${CM_API}/clusters/CDP-Base-732/commands?view=summary" | \
  python3 -c "
import sys, json
d = json.load(sys.stdin)
for c in d.get('items',[])[:5]:
    ok = 'OK' if c.get('success') else ('RUNNING' if c.get('active') else 'FAIL')
    print(f\"  [{ok}] {c.get('id')} {c.get('name','')} — {c.get('resultMessage','')[:100]}\")
"

echo ""
echo "[9] Recent gen_credentials errors in CM log"
grep "gen_credentials.sh failed\|GenerateCredentials.*ERROR\|Permission denied.*ipa_admin" \
  /var/log/cloudera-scm-server/cloudera-scm-server.log 2>/dev/null | tail -10
DIAG
```

Summarize:
1. Whether Kerberos is enabled in CM
2. Whether IPA admin password file is readable by `cloudera-scm`
3. Whether patched scripts are deployed
4. Which principals are missing keytabs
5. Root cause of any recent failures
6. Recommended next action
