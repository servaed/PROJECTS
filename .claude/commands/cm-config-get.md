# /cm-config-get

Read Cloudera Manager or service configuration values. Useful for verifying Kerberos, TLS, and database settings.

## Arguments
`$ARGUMENTS` — config scope. Examples:
- `/cm-config-get cm` — show CM-level settings (Kerberos, TLS)
- `/cm-config-get hdfs` — show HDFS service config
- `/cm-config-get yarn nodemanager` — show YARN NodeManager role config
- `/cm-config-get cm kerberos` — filter CM config by keyword

## Run

```python
import requests, urllib3
urllib3.disable_warnings()
auth = ("admin", "Cl0ud3ra@Base732#SE")
base = "https://34.26.137.154:7183"
cluster = "CDP-Base-732"

r = requests.get(f"{base}/api/version", auth=auth, verify=False)
v = r.text.strip().strip('"')
api = f"{base}/api/{v}"

args = "$ARGUMENTS".strip().split()
scope = args[0].lower() if args else "cm"
keyword = args[1].lower() if len(args) > 1 else ""

if scope == "cm":
    resp = requests.get(f"{api}/cm/config", auth=auth, verify=False, params={"view": "full"})
    items = resp.json().get("items", [])
elif scope in ("kerberos",):
    resp = requests.get(f"{api}/cm/config", auth=auth, verify=False, params={"view": "full"})
    items = [i for i in resp.json().get("items", []) if "krb" in i.get("name","").lower() or "kerberos" in i.get("name","").lower() or "kdc" in i.get("name","").lower() or "realm" in i.get("name","").lower()]
else:
    # Service config
    services = requests.get(f"{api}/clusters/{cluster}/services", auth=auth, verify=False).json()
    svc = next((s for s in services.get("items", []) if scope in s["name"].lower()), None)
    if not svc:
        print(f"Service '{scope}' not found")
        exit(1)
    sname = svc["name"]
    resp = requests.get(f"{api}/clusters/{cluster}/services/{sname}/config",
                        auth=auth, verify=False, params={"view": "full"})
    items = resp.json().get("items", [])

# Filter and print
for item in sorted(items, key=lambda x: x.get("name","")):
    name = item.get("name","")
    value = item.get("value") or item.get("default","<default>")
    if not keyword or keyword in name.lower():
        print(f"  {name:50} = {str(value)[:80]}")
```
