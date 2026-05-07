#!/usr/bin/env python3.11
import requests, json, time, sys

CM   = "http://cdp.se-indo.lab:7180/api/v58"
AUTH = ("admin", "Cl0ud3ra@Base732#SE")

# Trigger parcel repo refresh
r = requests.post(f"{CM}/cm/commands/refreshParcelRepos", auth=AUTH, timeout=15)
cmd = r.json()
print(f"Refresh command: id={cmd.get('id')} active={cmd.get('active')}")

print("Waiting 20s for CM to scan repo...")
time.sleep(20)

# List all parcels
r = requests.get(f"{CM}/clusters/CDP-Base-732/parcels", auth=AUTH, timeout=15)
items = r.json().get("items", [])
print(f"\nFound {len(items)} parcels:")
for p in items:
    print(f"  {p['product']}  {p['version']}  {p['stage']}")

# Also check what the repo URL actually serves
print("\nChecking repo URL listing...")
REPO = "https://71d807bd-8297-48ca-9f0a-d463e8e6851d:bad773ad937d@archive.cloudera.com/p/cdp-pvc-ds/7.3.2.0/parcels/"
try:
    r2 = requests.get(REPO + "manifest.json", timeout=30)
    if r2.status_code == 200:
        manifest = r2.json()
        for p in manifest.get("parcels", [])[:10]:
            print(f"  Manifest parcel: {p.get('parcelName')}")
    else:
        print(f"  manifest.json status: {r2.status_code}")
        # Try index page
        r3 = requests.get(REPO, timeout=30)
        print(f"  Repo index status: {r3.status_code}")
        if r3.status_code == 200:
            import re
            parcels = re.findall(r'CDH-[\w\.\-]+\.el9\.parcel(?:\.sha256)?', r3.text)
            for p in sorted(set(parcels))[:10]:
                print(f"  Found: {p}")
except Exception as e:
    print(f"  Error accessing repo: {e}")
