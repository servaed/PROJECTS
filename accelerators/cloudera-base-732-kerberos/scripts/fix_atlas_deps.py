#!/usr/bin/env python3.11
"""Discover Atlas config key names and fix service dependencies."""
import requests, json

CM      = "http://cdp.se-indo.lab:7180/api/v58"
AUTH    = ("admin", "Cl0ud3ra@Base732#SE")
CLUSTER = "CDP-Base-732"

# Get Atlas service config — look for _service keys
print("=== Atlas config attributes (service-ref type) ===")
r = requests.get(f"{CM}/clusters/{CLUSTER}/services/atlas/config?view=full",
                 auth=AUTH, timeout=15)
for item in r.json().get("items", []):
    if "service" in item.get("name","").lower() or item.get("relatedName","") in ("","N/A"):
        if "service" in item.get("name","").lower():
            print(f"  {item['name']:45s} relatedName={item.get('relatedName','')} default={item.get('default','')}")

# Get HIVE_ON_TEZ service config
print("\n=== HIVE_ON_TEZ config attributes (service-ref type) ===")
r2 = requests.get(f"{CM}/clusters/{CLUSTER}/services/hive_on_tez/config?view=full",
                  auth=AUTH, timeout=15)
for item in r2.json().get("items", []):
    if "service" in item.get("name","").lower():
        print(f"  {item['name']:45s}")

# Get SPARK3 service config
print("\n=== SPARK3_ON_YARN config attributes (service-ref type) ===")
r3 = requests.get(f"{CM}/clusters/{CLUSTER}/services/spark3/config?view=full",
                  auth=AUTH, timeout=15)
for item in r3.json().get("items", []):
    if "service" in item.get("name","").lower():
        print(f"  {item['name']:45s}")
