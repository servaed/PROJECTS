#!/usr/bin/env python3.11
"""Add missing Ozone roles, configure Atlas dependencies, then run firstRun."""
import requests, json, time

CM      = "http://cdp.se-indo.lab:7180/api/v58"
AUTH    = ("admin", "Cl0ud3ra@Base732#SE")
CLUSTER = "CDP-Base-732"
HOST_ID = "2d7e6fc0-ec98-47d7-859e-13d293d61d11"

def add_role(svc, role_type, role_name):
    r = requests.post(f"{CM}/clusters/{CLUSTER}/services/{svc}/roles",
                      auth=AUTH, timeout=15,
                      json={"items": [{"name": role_name, "type": role_type,
                                       "hostRef": {"hostId": HOST_ID}}]})
    print(f"  {role_name} HTTP {r.status_code}: {r.text[:100] if r.status_code != 200 else 'OK'}")

def svc_config(svc, items):
    r = requests.put(f"{CM}/clusters/{CLUSTER}/services/{svc}/config",
                     auth=AUTH, json={"items": items}, timeout=15)
    print(f"  config HTTP {r.status_code}: {r.text[:100] if r.status_code != 200 else 'OK'}")

def wait_cmd(cmd_id, interval=20, timeout=5400):
    deadline = time.time() + timeout
    print(f"  Waiting for cmd {cmd_id}...")
    while time.time() < deadline:
        r = requests.get(f"{CM}/commands/{cmd_id}", auth=AUTH, timeout=15)
        c = r.json()
        if not c.get("active", True):
            ok = c.get("success", False)
            print(f"  {'SUCCESS' if ok else 'FAILED'}: {c.get('resultMessage','')[:150]}")
            return ok
        print(f"  ... {c.get('resultMessage','running')[:80]}")
        time.sleep(interval)
    return False

# ── 1. Add missing Ozone roles ────────────────────────────────────────────────
print("=== 1. Add remaining Ozone roles ===")
existing_ozone = {r["type"] for r in
                  requests.get(f"{CM}/clusters/{CLUSTER}/services/ozone/roles",
                               auth=AUTH, timeout=10).json().get("items", [])}
print(f"  Existing Ozone roles: {existing_ozone}")

ozone_roles = [
    ("OZONE_MANAGER",            "ozone-OZONE_MANAGER-1"),
    ("STORAGE_CONTAINER_MANAGER","ozone-STORAGE_CONTAINER_MANAGER-1"),
    ("OZONE_DATANODE",           "ozone-OZONE_DATANODE-1"),
    ("OZONE_RECON",              "ozone-OZONE_RECON-1"),
    ("S3_GATEWAY",               "ozone-S3_GATEWAY-1"),
]
for role_type, role_name in ozone_roles:
    if role_type not in existing_ozone:
        add_role("ozone", role_type, role_name)
    else:
        print(f"  {role_type} already exists")

# ── 2. Configure Atlas service dependencies ───────────────────────────────────
print("\n=== 2. Configure Atlas service dependencies ===")
svc_config("atlas", [
    {"name": "atlas_solr_service",  "value": "infra_solr"},
    {"name": "atlas_hbase_service", "value": "hbase"},
    {"name": "atlas_kafka_service", "value": "kafka"},
    {"name": "dfs_service",         "value": "hdfs"},
])

# ── 3. Configure HBase dependencies ──────────────────────────────────────────
print("\n=== 3. Configure HBase ZooKeeper dependency ===")
svc_config("hbase", [{"name": "zookeeper_service", "value": "zookeeper"}])

# ── 4. Configure YARN dependencies ───────────────────────────────────────────
print("\n=== 4. Configure YARN HDFS dependency ===")
svc_config("yarn", [{"name": "hdfs_service", "value": "hdfs"}])

# ── 5. Configure Hive dependencies ────────────────────────────────────────────
print("\n=== 5. Configure Hive dependencies ===")
svc_config("hive", [{"name": "zookeeper_service", "value": "zookeeper"}])

# ── 6. Configure Hive on Tez dependencies ─────────────────────────────────────
print("\n=== 6. Configure Hive on Tez dependencies ===")
svc_config("hive_on_tez", [
    {"name": "hive_service",        "value": "hive"},
    {"name": "yarn_service",        "value": "yarn"},
    {"name": "tez_service",         "value": "tez"},
    {"name": "zookeeper_service",   "value": "zookeeper"},
])

# ── 7. Configure Tez dependencies ─────────────────────────────────────────────
print("\n=== 7. Configure Tez dependencies ===")
svc_config("tez", [
    {"name": "yarn_service", "value": "yarn"},
    {"name": "hdfs_service", "value": "hdfs"},
])

# ── 8. Configure Spark3 dependencies ──────────────────────────────────────────
print("\n=== 8. Configure Spark3 dependencies ===")
svc_config("spark3", [
    {"name": "yarn_service", "value": "yarn"},
    {"name": "hdfs_service", "value": "hdfs"},
    {"name": "hive_service", "value": "hive"},
])

# ── 9. Configure Impala dependencies ──────────────────────────────────────────
print("\n=== 9. Configure Impala dependencies ===")
svc_config("impala", [
    {"name": "hive_service",      "value": "hive"},
    {"name": "hdfs_service",      "value": "hdfs"},
    {"name": "hbase_service",     "value": "hbase"},
    {"name": "zookeeper_service", "value": "zookeeper"},
])

# ── 10. Configure Hue dependencies ────────────────────────────────────────────
print("\n=== 10. Configure Hue dependencies ===")
svc_config("hue", [
    {"name": "hive_service",   "value": "hive_on_tez"},
    {"name": "impala_service", "value": "impala"},
    {"name": "oozie_service",  "value": ""},
])

# ── 11. Configure HDFS DataNode data dirs ─────────────────────────────────────
print("\n=== 11. Configure HDFS data dirs ===")
r = requests.put(
    f"{CM}/clusters/{CLUSTER}/services/hdfs/roleConfigGroups/hdfs-DATANODE-BASE/config",
    auth=AUTH, json={"items": [{"name": "dfs_data_dir_list", "value": "/data/dfs/dn"}]},
    timeout=15)
print(f"  HDFS DataNode data dir HTTP {r.status_code}")

# Create the data dir on the node
import subprocess
print("  Creating data dirs on node...")
for d in ["/data/dfs/dn", "/data/yarn/nm"]:
    r_mk = requests.post(f"{CM}/clusters/{CLUSTER}/commands/deployClientConfig",
                         auth=AUTH, timeout=10)

# ── 12. firstRun ──────────────────────────────────────────────────────────────
print("\n=== 12. firstRun ===")
r = requests.post(f"{CM}/clusters/{CLUSTER}/commands/firstRun", auth=AUTH, timeout=30)
print(f"firstRun HTTP {r.status_code}: {r.text[:300]}")
if r.status_code == 200:
    cmd_id = r.json().get("id")
    print(f"firstRun cmd_id={cmd_id}  (15-30 min expected)")
    wait_cmd(cmd_id, interval=30, timeout=5400)
    print("firstRun complete!")
