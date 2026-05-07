# /cm-commands

Show the most recent Cloudera Manager commands with pass/fail status. Useful for quickly seeing what ran, what failed, and why.

## Arguments
`$ARGUMENTS` — optional number of commands to show (default: 20), or a command ID to drill into.

## Run

```python
import requests, urllib3, sys
urllib3.disable_warnings()
auth = ("admin", "Cl0ud3ra@Base732#SE")
base = "https://34.26.137.154:7183"
cluster = "CDP-Base-732"

r = requests.get(f"{base}/api/version", auth=auth, verify=False)
v = r.text.strip().strip('"')
api = f"{base}/api/{v}"

args = "$ARGUMENTS".strip()

if args.isdigit() and int(args) > 1000:
    # Treat as a command ID to drill into
    cmd_id = int(args)
    def drill(cid, depth=0):
        c = requests.get(f"{api}/commands/{cid}", auth=auth, verify=False).json()
        pad = "  " * depth
        ok = c.get("success")
        status = "OK" if ok is True else ("RUNNING" if c.get("active") else "FAIL")
        print(f"{pad}[{status}] {c.get('name','?')} (id={cid}): {c.get('resultMessage','')[:200]}")
        for child in c.get("children", {}).get("items", []):
            if child.get("success") is False or child.get("active"):
                drill(child["id"], depth+1)
    drill(cmd_id)
else:
    limit = int(args) if args.isdigit() else 20
    # Recent cluster commands
    cmds = requests.get(f"{api}/clusters/{cluster}/commands",
                        auth=auth, verify=False,
                        params={"view": "summary"}).json()
    print(f"{'ID':>12}  {'Status':8}  {'Duration':>8}  {'Name'}")
    print("-" * 70)
    for c in cmds.get("items", [])[:limit]:
        ok = c.get("success")
        status = "OK" if ok is True else ("RUNNING" if c.get("active") else "FAIL")
        start = c.get("startTime", "")[:16].replace("T", " ")
        print(f"{c.get('id'):>12}  {status:8}  {start}  {c.get('name','?')}")
        if ok is False:
            print(f"             {'':8}  {'':>8}  └─ {c.get('resultMessage','')[:120]}")
```

Print results. If the argument is a command ID, recursively show failed children.
