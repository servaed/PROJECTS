#!/usr/bin/env python3.11
import requests, json

CM   = "http://cdp.se-indo.lab:7180/api/v58"
AUTH = ("admin", "Cl0ud3ra@Base732#SE")
VER  = "7.3.2-1.cdh7.3.2.p0.77083870"
CLUSTER = "CDP-Base-732"

# Full parcel object — shows available commands and links
r = requests.get(f"{CM}/clusters/{CLUSTER}/parcels/products/CDH/versions/{VER}", auth=AUTH, timeout=15)
print(f"GET parcel HTTP {r.status_code}")
print(json.dumps(r.json(), indent=2)[:2000])

# Try all known activation command names
print("\n=== Testing activation endpoints ===")
for endpoint in ["activate", "activateParcel", "startActivation"]:
    url = f"{CM}/clusters/{CLUSTER}/parcels/products/CDH/versions/{VER}/commands/{endpoint}"
    r2 = requests.post(url, auth=AUTH, timeout=10)
    print(f"  POST {endpoint}: HTTP {r2.status_code}  -> {r2.text[:150]}")

# Also check the CM API endpoints list for parcel
print("\n=== Parcel list ===")
r3 = requests.get(f"{CM}/clusters/{CLUSTER}/parcels", auth=AUTH, timeout=15)
for p in r3.json().get("items", []):
    if p["product"] == "CDH":
        print(json.dumps(p, indent=2)[:800])
