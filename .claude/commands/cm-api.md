# /cm-api

Make a raw Cloudera Manager API call. Useful for quick lookups or triggering commands.

## Arguments
`$ARGUMENTS` — HTTP method and path. Examples:
- `/cm-api GET /cm/kerberosInfo`
- `/cm-api GET /clusters/CDP-Base-732/services`
- `/cm-api POST /clusters/CDP-Base-732/commands/restart`
- `/cm-api GET /cm/config`
- `/cm-api GET /hosts`

## Run

```python
import requests, urllib3, json, sys
urllib3.disable_warnings()
auth = ("admin", "Cl0ud3ra@Base732#SE")
base = "https://34.26.137.154:7183"

r = requests.get(f"{base}/api/version", auth=auth, verify=False)
v = r.text.strip().strip('"')

args = "$ARGUMENTS".strip().split(None, 1)
method = args[0].upper() if args else "GET"
path = args[1].lstrip("/") if len(args) > 1 else "cm/kerberosInfo"

url = f"{base}/api/{v}/{path}"
print(f"{method} {url}")
print()

if method == "GET":
    resp = requests.get(url, auth=auth, verify=False, params={"view": "summary"})
elif method == "POST":
    resp = requests.post(url, auth=auth, verify=False)
elif method == "PUT":
    resp = requests.put(url, auth=auth, verify=False)
elif method == "DELETE":
    resp = requests.delete(url, auth=auth, verify=False)

print(f"HTTP {resp.status_code}")
try:
    print(json.dumps(resp.json(), indent=2)[:3000])
except Exception:
    print(resp.text[:1000])
```

Pretty-print the response. If it's a command object, note the `id` for tracking with `/cm-commands`.
