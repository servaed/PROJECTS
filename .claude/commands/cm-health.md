# /cm-health

Show the health status of all services and roles in the CDP cluster.

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

# Overall cluster health
cl = requests.get(f"{api}/clusters/{cluster}", auth=auth, verify=False).json()
print(f"Cluster: {cl.get('displayName')} — {cl.get('entityStatus')}")
print()

# Per-service health
services = requests.get(f"{api}/clusters/{cluster}/services", auth=auth, verify=False).json()
good, bad = [], []
for s in services.get("items", []):
    name = s.get("displayName", s.get("name"))
    health = s.get("entityStatus", "?")
    if health not in ("GOOD_HEALTH", "DISABLED"):
        bad.append(f"  {health:25} {name}")
    else:
        good.append(f"  {health:25} {name}")

print(f"=== HEALTHY ({len(good)}) ===")
for x in sorted(good): print(x)
print(f"\n=== NEEDS ATTENTION ({len(bad)}) ===")
for x in sorted(bad): print(x)
```

If any service shows BAD_HEALTH or has errors, also fetch its health checks:
```python
for s in services.get("items", []):
    if s.get("entityStatus") not in ("GOOD_HEALTH", "DISABLED"):
        sname = s["name"]
        checks = requests.get(f"{api}/clusters/{cluster}/services/{sname}/healthChecks", auth=auth, verify=False).json()
        for c in checks.get("items", []):
            if c.get("summary") not in ("GOOD", "DISABLED", "NOT_AVAILABLE"):
                print(f"  [{sname}] {c.get('name')}: {c.get('summary')} — {c.get('explanation', '')[:150]}")
```

Summarize the overall cluster state and highlight any actionable issues.
