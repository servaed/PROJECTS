# /cm-parcel

Check parcel download, distribution, and activation status for the CDP cluster.

## Arguments
`$ARGUMENTS` — optional action: `status` (default), `activate`, `distribute`

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

action = "$ARGUMENTS".strip() or "status"

# List all parcels
parcels = requests.get(f"{api}/clusters/{cluster}/parcels",
                       auth=auth, verify=False).json()

print(f"{'Product':20} {'Version':40} {'Stage':15}")
print("-" * 80)
for p in parcels.get("items", []):
    stage = p.get("stage","?")
    print(f"{p.get('product','?'):20} {p.get('version','?'):40} {stage:15}")
    if p.get("state",{}).get("progress"):
        pct = p["state"].get("progress", 0)
        total = p["state"].get("totalProgress", 100)
        print(f"  Progress: {pct}/{total} ({int(100*pct/max(total,1))}%)")

if action == "activate":
    # Find the CDH parcel and activate it
    cdh = next((p for p in parcels.get("items",[]) if p.get("product") == "CDH"), None)
    if cdh and cdh.get("stage") == "DISTRIBUTED":
        product = cdh["product"]
        version = cdh["version"]
        resp = requests.post(
            f"{api}/clusters/{cluster}/parcels/products/{product}/versions/{version}/commands/activate",
            auth=auth, verify=False
        )
        print(f"\nActivate HTTP {resp.status_code}: {resp.json().get('resultMessage','')[:200]}")
    else:
        print(f"\nCDH parcel is in stage {cdh.get('stage') if cdh else 'NOT FOUND'} — cannot activate")
```
