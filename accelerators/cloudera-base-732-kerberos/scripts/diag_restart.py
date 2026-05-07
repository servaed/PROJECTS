#!/usr/bin/env python3.11
"""Diagnose failed restart command — show failed child commands."""
import os, requests, urllib3
urllib3.disable_warnings()

host = os.environ["CM_HOST"]
port = os.environ.get("CM_PORT", "7183")
auth = (os.environ.get("CM_ADMIN_USER", "admin"), os.environ.get("CM_ADMIN_PASS", "admin"))
base = f"https://{host}:{port}"

r = requests.get(f"{base}/api/version", auth=auth, verify=False)
v = r.text.strip().strip('"')
api = f"{base}/api/{v}"

def get_cmd(cmd_id, depth=0):
    r = requests.get(f"{api}/commands/{cmd_id}", auth=auth, verify=False)
    d = r.json()
    indent = "  " * depth
    success = d.get("success", None)
    active = d.get("active", False)
    name = d.get("name", "?")
    msg = d.get("resultMessage", "")[:300]
    status = "OK" if success else ("RUNNING" if active else "FAIL")
    print(f"{indent}[{status}] {name}: {msg}")
    for child in d.get("children", {}).get("items", []):
        if not child.get("success", True):
            get_cmd(child["id"], depth + 1)

# Get the 5 most recent commands and show failures
r2 = requests.get(f"{api}/commands/active", auth=auth, verify=False)
for c in r2.json().get("items", []):
    print(f"ACTIVE: {c['name']} id={c['id']}")

# Show recent cluster commands
r3 = requests.get(
    f"{api}/clusters/{os.environ.get('CLUSTER_NAME', 'CDP-Base-732')}/commands",
    auth=auth, verify=False, params={"view": "full"}
)
for c in r3.json().get("items", [])[:5]:
    print(f"\n--- Command {c['id']}: {c['name']} success={c.get('success')} ---")
    print(f"    {c.get('resultMessage','')[:300]}")
    for child in c.get("children", {}).get("items", []):
        s = child.get("success")
        if s is False:
            print(f"  FAILED child {child['id']}: {child.get('name')} — {child.get('resultMessage','')[:200]}")
