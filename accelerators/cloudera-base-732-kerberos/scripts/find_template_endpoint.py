#!/usr/bin/env python3.11
"""Find the correct importClusterTemplate endpoint in CM API v58."""
import requests, json

CM      = "http://cdp.se-indo.lab:7180/api/v58"
AUTH    = ("admin", "Cl0ud3ra@Base732#SE")
CLUSTER = "CDP-Base-732"

# Load the saved template
with open("/tmp/cdp_single_node_template.json") as f:
    template = json.load(f)

# Try both endpoint variants
endpoints = [
    f"/clusters/importClusterTemplate",
    f"/clusters/{CLUSTER}/importClusterTemplate",
    f"/cm/importClusterTemplate",
]

print("=== Probing importClusterTemplate endpoints ===")
for path in endpoints:
    r = requests.post(f"{CM}{path}?addRepositories=true",
                      auth=AUTH, json=template, timeout=30)
    print(f"  POST {path}: HTTP {r.status_code}")
    if r.status_code not in (404, 405):
        print(f"    -> {r.text[:300]}")
        if r.status_code == 200:
            print("FOUND WORKING ENDPOINT!")
            break

# Also check if there's an API spec endpoint
print("\n=== CM API root ===")
r = requests.get(f"http://cdp.se-indo.lab:7180/api/v58", auth=AUTH, timeout=10)
print(f"HTTP {r.status_code}: {r.text[:500]}")
