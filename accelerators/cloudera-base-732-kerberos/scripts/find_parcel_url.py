#!/usr/bin/env python3.11
import requests, re

USER = "71d807bd-8297-48ca-9f0a-d463e8e6851d"
PASS = "bad773ad937d"
AUTH = (USER, PASS)

BASE = "https://archive.cloudera.com/p/cdh7/7.3.2/parcels/"

print(f"=== Fetching {BASE} ===")
r = requests.get(BASE, auth=AUTH, timeout=20)
print(f"Status: {r.status_code}")
print(r.text[:3000])

# Also check manifest.json
print("\n=== manifest.json ===")
r2 = requests.get(BASE + "manifest.json", auth=AUTH, timeout=20)
print(f"Status: {r2.status_code}")
if r2.status_code == 200:
    import json
    m = r2.json()
    for p in m.get("parcels", []):
        print(f"  {p.get('parcelName')}  hash={p.get('hash','')[:10]}")
