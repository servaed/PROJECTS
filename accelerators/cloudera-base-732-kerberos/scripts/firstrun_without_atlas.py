#!/usr/bin/env python3.11
"""Remove Atlas to unblock firstRun, run firstRun, then restore Atlas."""
import requests, json, time

CM      = "http://cdp.se-indo.lab:7180/api/v58"
AUTH    = ("admin", "Cl0ud3ra@Base732#SE")
CLUSTER = "CDP-Base-732"

def wait_cmd(cmd_id, interval=30, timeout=5400):
    deadline = time.time() + timeout
    print(f"  Waiting for cmd {cmd_id}...")
    while time.time() < deadline:
        r = requests.get(f"{CM}/commands/{cmd_id}", auth=AUTH, timeout=15)
        c = r.json()
        if not c.get("active", True):
            ok = c.get("success", False)
            print(f"  {'SUCCESS' if ok else 'FAILED'}: {c.get('resultMessage','')[:200]}")
            return ok
        print(f"  ... {c.get('resultMessage','running')[:80]}")
        time.sleep(interval)
    return False

# 1. Stop Atlas if running
print("=== 1. Stop Atlas service ===")
r = requests.post(f"{CM}/clusters/{CLUSTER}/services/atlas/commands/stop",
                  auth=AUTH, timeout=15)
print(f"  HTTP {r.status_code}")
time.sleep(5)

# 2. Delete Atlas roles first
print("=== 2. Delete Atlas roles ===")
r = requests.get(f"{CM}/clusters/{CLUSTER}/services/atlas/roles", auth=AUTH, timeout=10)
for role in r.json().get("items", []):
    rd = requests.delete(f"{CM}/clusters/{CLUSTER}/services/atlas/roles/{role['name']}",
                         auth=AUTH, timeout=10)
    print(f"  Delete role {role['name']}: HTTP {rd.status_code}")

# 3. Delete Atlas service
print("\n=== 3. Delete Atlas service ===")
r = requests.delete(f"{CM}/clusters/{CLUSTER}/services/atlas", auth=AUTH, timeout=15)
print(f"  HTTP {r.status_code}: {r.text[:100]}")

# 4. List remaining services
print("\n=== 4. Services after Atlas removal ===")
r = requests.get(f"{CM}/clusters/{CLUSTER}/services", auth=AUTH, timeout=10)
svcs = r.json().get("items", [])
print(f"  {len(svcs)} services: {[s['name'] for s in svcs]}")

# 5. Run firstRun
print("\n=== 5. firstRun (15 services, 15-30 min expected) ===")
r = requests.post(f"{CM}/clusters/{CLUSTER}/commands/firstRun", auth=AUTH, timeout=30)
print(f"  firstRun HTTP {r.status_code}: {r.text[:300]}")
if r.status_code == 200:
    cmd_id = r.json().get("id")
    print(f"  cmd_id={cmd_id}")
    ok = wait_cmd(cmd_id, interval=30, timeout=5400)
    if ok:
        print("\n[SUCCESS] Cluster is UP with 15 services!")
        print("Next: Add Atlas via CM UI (Administration > Add Service > ATLAS)")
    else:
        print("\n[WARNING] firstRun had issues. Check CM UI for details.")
else:
    print(f"  firstRun still blocked: {r.text[:400]}")
