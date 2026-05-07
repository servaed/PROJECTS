# /kerberos-generate-creds

Trigger the `generateCredentials` CM API command to create/refresh Kerberos keytabs for all service principals. Use this when services report "missing Kerberos keytab" without running the full re-enable flow.

## Pre-check
Before triggering, ensure `/etc/cloudera/.ipa_admin_pass` is readable by `cloudera-scm`:
```bash
ssh root@34.26.137.154 'ls -la /etc/cloudera/.ipa_admin_pass'
# Should show: -rw-------. 1 cloudera-scm ...
# Fix if needed: chown cloudera-scm /etc/cloudera/.ipa_admin_pass
```

## Trigger via CM API

```python
import requests, urllib3, time
urllib3.disable_warnings()
auth = ("admin", "Cl0ud3ra@Base732#SE")
base = "https://34.26.137.154:7183"

r = requests.get(f"{base}/api/version", auth=auth, verify=False)
v = r.text.strip().strip('"')
api = f"{base}/api/{v}"

# Trigger generateCredentials (CM-level command)
resp = requests.post(f"{api}/cm/commands/generateCredentials", auth=auth, verify=False)
print(f"HTTP {resp.status_code}")
cmd_id = resp.json().get("id")
print(f"Command ID: {cmd_id}")

# Poll until done
for _ in range(60):
    time.sleep(15)
    c = requests.get(f"{api}/commands/{cmd_id}", auth=auth, verify=False).json()
    if not c.get("active", True):
        print("Success:", c.get("success"))
        print("Message:", c.get("resultMessage", "")[:300])
        break
    print("  ...", c.get("resultMessage", "running")[:80])
```

If it fails, immediately check the CM log:
```bash
ssh root@34.26.137.154 'grep -A30 "GenerateCredentials.*ERROR\|gen_credentials.sh failed" /var/log/cloudera-scm-server/cloudera-scm-server.log | tail -60'
```

Common failure causes:
- `Permission denied` on `.ipa_admin_pass` → `chown cloudera-scm /etc/cloudera/.ipa_admin_pass`
- `kinit: Password incorrect` → wrong password in `.ipa_admin_pass`
- `ipa: ERROR: ...not found` → IPA service not registerable, check `ipa host-show cdp.se-indo.lab`
- `merge_credentials.sh failed with empty input` → ALL gen_credentials.sh calls failed, check log above
