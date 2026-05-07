#!/usr/bin/env python3.11
"""Fix Ozone roles and run firstRun."""
import requests, json, time

CM      = "http://cdp.se-indo.lab:7180/api/v58"
AUTH    = ("admin", "Cl0ud3ra@Base732#SE")
CLUSTER = "CDP-Base-732"
HOST_ID = "2d7e6fc0-ec98-47d7-859e-13d293d61d11"

# 1. Check Ozone service type metadata to find correct DataNode role type
print("=== Ozone service type info ===")
r = requests.get(f"{CM}/clusters/{CLUSTER}/services/ozone", auth=AUTH, timeout=10)
print(f"Ozone service: {r.json().get('type')} state={r.json().get('serviceState')}")

# List existing Ozone roles
r2 = requests.get(f"{CM}/clusters/{CLUSTER}/services/ozone/roles", auth=AUTH, timeout=10)
existing = r2.json().get("items", [])
print(f"Existing Ozone roles: {[r['type'] for r in existing]}")

# Get role config groups to find the DataNode one
r3 = requests.get(f"{CM}/clusters/{CLUSTER}/services/ozone/roleConfigGroups", auth=AUTH, timeout=10)
for rcg in r3.json().get("items", []):
    print(f"  RCG: {rcg['name']}  type={rcg['roleType']}")

# 2. Try adding OZONE_DATANODE role (underscore variant)
print("\n=== Adding Ozone DataNode role ===")
for role_type in ["OZONE_DATANODE", "DATANODE", "OZONEDATANODE"]:
    # Check if this role type has a base RCG
    rcg_name = f"ozone-{role_type}-BASE"
    r_test = requests.get(f"{CM}/clusters/{CLUSTER}/services/ozone/roleConfigGroups/{rcg_name}",
                          auth=AUTH, timeout=10)
    if r_test.status_code == 200:
        print(f"  Found RCG for {role_type}")
        r_add = requests.post(f"{CM}/clusters/{CLUSTER}/services/ozone/roles",
                              auth=AUTH, timeout=15,
                              json={"items": [{"name": f"ozone-{role_type}-1",
                                               "type": role_type,
                                               "hostRef": {"hostId": HOST_ID}}]})
        print(f"  Add role HTTP {r_add.status_code}: {r_add.text[:150]}")
        break

# 3. Check firstRun error detail
print("\n=== firstRun error detail ===")
r_fr = requests.post(f"{CM}/clusters/{CLUSTER}/commands/firstRun", auth=AUTH, timeout=15)
print(f"HTTP {r_fr.status_code}: {r_fr.text[:500]}")

# 4. Try deployClientConfig first
print("\n=== deployClientConfig ===")
r_dcc = requests.post(f"{CM}/clusters/{CLUSTER}/commands/deployClientConfig", auth=AUTH, timeout=15)
print(f"HTTP {r_dcc.status_code}: {r_dcc.json().get('id')} active={r_dcc.json().get('active')}")

# 5. List all services and their health/state
print("\n=== All services state ===")
r_svcs = requests.get(f"{CM}/clusters/{CLUSTER}/services", auth=AUTH, timeout=10)
for s in r_svcs.json().get("items", []):
    r_roles = requests.get(f"{CM}/clusters/{CLUSTER}/services/{s['name']}/roles", auth=AUTH, timeout=10)
    role_count = len(r_roles.json().get("items", []))
    print(f"  {s['name']:20s} type={s['type']:25s} roles={role_count}")
