# /cm-restart-stale

Restart all stale services in the CDP cluster via CM API. Use after keytab generation, config changes, or partial failures.

## Run

```python
import requests, urllib3, time
urllib3.disable_warnings()
auth = ("admin", "Cl0ud3ra@Base732#SE")
base = "https://34.26.137.154:7183"
cluster = "CDP-Base-732"

r = requests.get(f"{base}/api/version", auth=auth, verify=False)
v = r.text.strip().strip('"')
api = f"{base}/api/{v}"

# Deploy client configs first
print("Deploying client configs...")
r1 = requests.post(f"{api}/clusters/{cluster}/commands/deployClientConfig",
                   auth=auth, verify=False)
if r1.status_code == 200:
    cid = r1.json().get("id")
    for _ in range(40):
        time.sleep(10)
        c = requests.get(f"{api}/commands/{cid}", auth=auth, verify=False).json()
        if not c.get("active", True):
            print(f"  Deploy client config: {'OK' if c.get('success') else 'FAIL'}")
            break
        print("  ...", c.get("resultMessage","")[:60])

# Restart stale services
print("\nRestarting stale services...")
resp = requests.post(
    f"{api}/clusters/{cluster}/commands/restart",
    auth=auth, verify=False,
    json={"restartOnlyStaleServices": True}
)
print(f"HTTP {resp.status_code}")
if resp.status_code != 200:
    print(resp.text[:300])
    exit(1)

cmd_id = resp.json().get("id")
print(f"Command ID: {cmd_id}  (may take 10-20 min for 20 services)")

for _ in range(80):
    time.sleep(30)
    c = requests.get(f"{api}/commands/{cmd_id}", auth=auth, verify=False).json()
    msg = c.get("resultMessage", "running")[:100]
    if not c.get("active", True):
        print(f"\nResult: {'SUCCESS' if c.get('success') else 'FAILED'}")
        print(f"Message: {msg}")
        break
    print(f"  [{_*30}s] {msg}")
```

If restart fails, check which service failed:
```python
# Get failed children
c = requests.get(f"{api}/commands/{cmd_id}", auth=auth, verify=False).json()
for child in c.get("children", {}).get("items", []):
    if child.get("success") is False:
        print(f"FAIL: {child.get('name')} (id={child.get('id')}): {child.get('resultMessage','')[:200]}")
```
