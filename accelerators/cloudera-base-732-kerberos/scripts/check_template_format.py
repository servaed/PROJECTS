#!/usr/bin/env python3.11
"""Export cluster template and probe the correct importClusterTemplate format for CM API v58."""
import requests, json

CM      = "http://cdp.se-indo.lab:7180/api/v58"
AUTH    = ("admin", "Cl0ud3ra@Base732#SE")
CLUSTER = "CDP-Base-732"

# 1. Export the cluster to see current format
print("=== GET /clusters/{cluster}/export ===")
r = requests.get(f"{CM}/clusters/{CLUSTER}/export", auth=AUTH, timeout=15)
print(f"HTTP {r.status_code}")
if r.status_code == 200:
    print(json.dumps(r.json(), indent=2)[:3000])

# 2. Check available API endpoints on v58
print("\n=== Check /cm/importClusterTemplate schema (OPTIONS) ===")
r2 = requests.options(f"{CM}/cm/importClusterTemplate", auth=AUTH, timeout=10)
print(f"OPTIONS HTTP {r2.status_code}: {r2.headers}")

# 3. Try minimal template with just ZooKeeper to probe the correct format
print("\n=== Test minimal template at /cm/importClusterTemplate ===")
host_id = requests.get(f"{CM}/hosts", auth=AUTH, timeout=10).json()["items"][0]["hostId"]
hostname = requests.get(f"{CM}/hosts", auth=AUTH, timeout=10).json()["items"][0]["hostname"]
print(f"Host: {hostname}  id={host_id}")

# Try with 'hostname' instead of 'hostId' in hostRef
minimal_new_format = {
    "clusterName": CLUSTER,
    "services": [{
        "refName": "zookeeper",
        "serviceType": "ZOOKEEPER",
        "roleConfigGroups": [
            {"refName": "zk-SERVER", "roleType": "SERVER", "base": True, "configs": []}
        ],
        "roles": [{"refName": "zk-1", "roleType": "SERVER",
                   "hostRef": {"hostname": hostname}}]
    }]
}
r3 = requests.post(f"{CM}/cm/importClusterTemplate?addRepositories=false",
                   auth=AUTH, json=minimal_new_format, timeout=15)
print(f"hostname-format HTTP {r3.status_code}: {r3.text[:300]}")

# Try with 'hostName' (camelCase)
minimal_camel = {
    "clusterName": CLUSTER,
    "services": [{
        "refName": "zookeeper",
        "serviceType": "ZOOKEEPER",
        "roleConfigGroups": [
            {"refName": "zk-SERVER", "roleType": "SERVER", "base": True, "configs": []}
        ],
        "roles": [{"refName": "zk-1", "roleType": "SERVER",
                   "hostRef": {"hostName": hostname}}]
    }]
}
r4 = requests.post(f"{CM}/cm/importClusterTemplate?addRepositories=false",
                   auth=AUTH, json=minimal_camel, timeout=15)
print(f"hostName-format HTTP {r4.status_code}: {r4.text[:300]}")
