# /kerberos-status

Check the current Kerberos status of the CDP cluster.

## What this does
- Queries CM API for `kerberosInfo` (enabled, realm, KDC type)
- Lists all service principals registered in FreeIPA (`ipa service-find`)
- Shows which principals have keytabs vs missing them
- Checks if a valid admin TGT can be obtained

## Run these checks

```python
# Check CM Kerberos info
import requests, urllib3
urllib3.disable_warnings()
auth = ("admin", "Cl0ud3ra@Base732#SE")
base = "https://34.26.137.154:7183"

r = requests.get(f"{base}/api/version", auth=auth, verify=False)
v = r.text.strip().strip('"')

info = requests.get(f"{base}/api/{v}/cm/kerberosInfo", auth=auth, verify=False).json()
print("kerberosEnabled:", info.get("kerberosEnabled"))
print("realm:          ", info.get("realm"))
print("kdcType:        ", info.get("kdcType"))
print("managingKrb5:   ", info.get("managingKrb5Conf"))
```

And on the VM:
```bash
ssh root@34.26.137.154 '
  echo "=== FreeIPA services ==="
  echo "Cl0ud3ra@Base732#SE" | kinit admin@SE-INDO.LAB 2>/dev/null
  ipa service-find 2>/dev/null | grep "Principal name:" | wc -l
  echo "service principals registered"
  ipa service-find 2>/dev/null | grep "Keytab: False" | wc -l
  echo "missing keytabs"
  echo "=== kinit test ==="
  klist 2>/dev/null | head -3
'
```

Report:
1. Whether Kerberos is enabled in CM
2. Number of IPA service principals and how many are missing keytabs
3. Whether admin TGT can be obtained
