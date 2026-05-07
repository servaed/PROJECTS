#!/usr/bin/env python3.11
"""Set correct service dependencies using verified config key names, then run firstRun."""
import requests, json, time

CM      = "http://cdp.se-indo.lab:7180/api/v58"
AUTH    = ("admin", "Cl0ud3ra@Base732#SE")
CLUSTER = "CDP-Base-732"

def cfg(svc, items):
    r = requests.put(f"{CM}/clusters/{CLUSTER}/services/{svc}/config",
                     auth=AUTH, json={"items": items}, timeout=15)
    status = "OK" if r.status_code == 200 else f"HTTP {r.status_code}: {r.text[:100]}"
    print(f"  {svc}: {status}")

def wait_cmd(cmd_id, interval=30, timeout=5400):
    deadline = time.time() + timeout
    print(f"  Waiting for cmd {cmd_id}...")
    while time.time() < deadline:
        r = requests.get(f"{CM}/commands/{cmd_id}", auth=AUTH, timeout=15)
        c = r.json()
        if not c.get("active", True):
            ok = c.get("success", False)
            msg = c.get("resultMessage", "")[:200]
            print(f"  {'SUCCESS' if ok else 'FAILED'}: {msg}")
            return ok
        print(f"  ... {c.get('resultMessage','running')[:80]}")
        time.sleep(interval)
    return False

print("=== Setting service dependencies ===")

# Atlas (uses solr_service, hbase_service, hdfs_service, kafka_service)
cfg("atlas", [
    {"name": "solr_service",  "value": "infra_solr"},
    {"name": "hbase_service", "value": "hbase"},
    {"name": "kafka_service", "value": "kafka"},
    {"name": "hdfs_service",  "value": "hdfs"},
    {"name": "ranger_service","value": "ranger"},
])

# HIVE_ON_TEZ (uses mapreduce_yarn_service, tez_service, zookeeper_service, hdfs_service)
cfg("hive_on_tez", [
    {"name": "mapreduce_yarn_service", "value": "yarn"},
    {"name": "tez_service",            "value": "tez"},
    {"name": "zookeeper_service",      "value": "zookeeper"},
    {"name": "hdfs_service",           "value": "hdfs"},
    {"name": "hbase_service",          "value": "hbase"},
    {"name": "ranger_service",         "value": "ranger"},
    {"name": "atlas_service",          "value": "atlas"},
])

# TEZ (check what's available — might only need YARN via HIVE_ON_TEZ)
r_tez = requests.get(f"{CM}/clusters/{CLUSTER}/services/tez/config?view=full",
                     auth=AUTH, timeout=10)
tez_svc_keys = [i["name"] for i in r_tez.json().get("items",[]) if "service" in i["name"] and "suppression" not in i["name"]]
print(f"  TEZ service keys available: {tez_svc_keys}")
tez_cfg = []
if "yarn_service" in tez_svc_keys:
    tez_cfg.append({"name": "yarn_service", "value": "yarn"})
if "hive_service" in tez_svc_keys:
    tez_cfg.append({"name": "hive_service", "value": "hive"})
if tez_cfg:
    cfg("tez", tez_cfg)

# SPARK3 (uses yarn_service — NO hdfs_service key)
cfg("spark3", [
    {"name": "yarn_service",  "value": "yarn"},
    {"name": "atlas_service", "value": "atlas"},
    {"name": "hbase_service", "value": "hbase"},
])

# Hive Metastore (ZooKeeper)
cfg("hive", [{"name": "zookeeper_service", "value": "zookeeper"}])

# HBase
cfg("hbase", [
    {"name": "zookeeper_service", "value": "zookeeper"},
    {"name": "hdfs_service",      "value": "hdfs"},
])

# YARN
cfg("yarn", [
    {"name": "hdfs_service",      "value": "hdfs"},
    {"name": "zookeeper_service", "value": "zookeeper"},
])

# HDFS (ZooKeeper for HA — not needed for single node, but good practice)
cfg("hdfs", [{"name": "zookeeper_service", "value": "zookeeper"}])

# Impala
cfg("impala", [
    {"name": "hive_service",      "value": "hive"},
    {"name": "hdfs_service",      "value": "hdfs"},
    {"name": "hbase_service",     "value": "hbase"},
    {"name": "zookeeper_service", "value": "zookeeper"},
    {"name": "ranger_service",    "value": "ranger"},
])

# Hue
cfg("hue", [
    {"name": "hive_service",   "value": "hive_on_tez"},
    {"name": "impala_service", "value": "impala"},
])

# Ranger (needs Solr for audit)
r_rng = requests.get(f"{CM}/clusters/{CLUSTER}/services/ranger/config?view=full",
                     auth=AUTH, timeout=10)
rng_svc_keys = [i["name"] for i in r_rng.json().get("items",[]) if "service" in i["name"] and "suppression" not in i["name"]]
print(f"  Ranger service keys: {rng_svc_keys}")
rng_cfg = []
for k, v in [("solr_service","infra_solr"), ("hdfs_service","hdfs"), ("zookeeper_service","zookeeper")]:
    if k in rng_svc_keys:
        rng_cfg.append({"name": k, "value": v})
if rng_cfg:
    cfg("ranger", rng_cfg)

print("\n=== Attempting firstRun ===")
r = requests.post(f"{CM}/clusters/{CLUSTER}/commands/firstRun", auth=AUTH, timeout=30)
print(f"firstRun HTTP {r.status_code}: {r.text[:300]}")
if r.status_code == 200:
    cmd_id = r.json().get("id")
    print(f"firstRun cmd_id={cmd_id}")
    wait_cmd(cmd_id, interval=30, timeout=5400)
    print("firstRun complete!")
