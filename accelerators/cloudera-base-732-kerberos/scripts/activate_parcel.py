#!/usr/bin/env python3.11
"""Activate the CDH parcel and run importClusterTemplate + firstRun."""
import requests, json, time, sys

CM   = "http://cdp.se-indo.lab:7180/api/v58"
AUTH = ("admin", "Cl0ud3ra@Base732#SE")
CLUSTER = "CDP-Base-732"
VER  = "7.3.2-1.cdh7.3.2.p0.77083870"
BASE = f"{CM}/clusters/{CLUSTER}/parcels/products/CDH/versions/{VER}"

def wait_cmd(cmd_id, interval=10, timeout=600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{CM}/commands/{cmd_id}", auth=AUTH, timeout=15)
        c = r.json()
        if not c.get("active", True):
            if c.get("success"):
                print(f"  Command {cmd_id} SUCCESS: {c.get('resultMessage','')}")
                return True
            else:
                print(f"  Command {cmd_id} FAILED: {c.get('resultMessage','')}")
                return False
        print(f"  Command {cmd_id} running: {c.get('resultMessage','...')}")
        time.sleep(interval)
    print(f"  TIMEOUT waiting for command {cmd_id}")
    return False

# 1. Check current stage
r = requests.get(BASE, auth=AUTH, timeout=15)
stage = r.json().get("stage", "UNKNOWN")
print(f"Current parcel stage: {stage}")

# 2. Activate if needed
if stage != "ACTIVATED":
    print("Activating parcel...")
    r = requests.post(f"{BASE}/commands/activate", auth=AUTH, timeout=15)  # v58: 'activate' not 'activateParcel'
    print(f"  HTTP {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        cmd_id = r.json().get("id")
        if cmd_id:
            wait_cmd(cmd_id, interval=5, timeout=60)

    # Poll until ACTIVATED
    for i in range(20):
        time.sleep(5)
        r = requests.get(BASE, auth=AUTH, timeout=15)
        stage = r.json().get("stage", "?")
        print(f"  [{i*5}s] stage={stage}")
        if stage == "ACTIVATED":
            break
    else:
        print("ERROR: Parcel did not activate in 100s")
        sys.exit(1)

print(f"Parcel stage: {stage}")

# 3. Import cluster template
print("\n=== Import cluster template ===")
# Read template from file written by deploy script if available
# Otherwise, just check services
r = requests.get(f"{CM}/clusters/{CLUSTER}/services", auth=AUTH, timeout=15)
svcs = r.json().get("items", [])
print(f"Services currently in cluster: {len(svcs)}")
for s in svcs:
    print(f"  {s['type']}: {s.get('serviceState','?')}")

if len(svcs) <= 1:
    print("\nTemplate not imported yet. Loading from saved file...")
    try:
        with open("/tmp/cdp_single_node_template.json") as f:
            template = json.load(f)
        r = requests.post(
            f"{CM}/clusters/importClusterTemplate?addRepositories=true",
            auth=AUTH, json=template, timeout=120
        )
        print(f"  HTTP {r.status_code}")
        if r.status_code == 200:
            cmd_id = r.json().get("id")
            print(f"  Import cmd ID: {cmd_id}")
            wait_cmd(cmd_id, interval=20, timeout=2400)
    except FileNotFoundError:
        print("  Template file not found at /tmp/cdp_single_node_template.json")
        print("  Re-run 05_cluster_deploy.py --skip-to template")
        sys.exit(1)
else:
    print("Services already deployed — skipping template import")

# 4. firstRun
print("\n=== firstRun ===")
r = requests.post(f"{CM}/clusters/{CLUSTER}/commands/firstRun", auth=AUTH, timeout=30)
print(f"  HTTP {r.status_code}")
if r.status_code == 200:
    cmd_id = r.json().get("id")
    print(f"  firstRun cmd ID: {cmd_id}")
    wait_cmd(cmd_id, interval=30, timeout=5400)

print("\nDone.")
