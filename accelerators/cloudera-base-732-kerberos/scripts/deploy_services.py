#!/usr/bin/env python3.11
"""
deploy_services.py — Add all 16 services to existing cluster via CM API v58.
Uses individual POST /clusters/{name}/services calls (more reliable than importClusterTemplate).
Run: python3.11 deploy_services.py
"""
import requests, json, time, sys, os

CM      = "http://cdp.se-indo.lab:7180/api/v58"
AUTH    = ("admin", "Cl0ud3ra@Base732#SE")
CLUSTER = "CDP-Base-732"
HOST    = "cdp.se-indo.lab"

# Resource allocation
YARN_NM_MB   = 51200
YARN_NM_VCPU = 24
IMPALA_BYTES = 25769803776   # 24 GB
HBASE_BYTES  = 2147483648    # 2 GB
KAFKA_BYTES  = 1073741824    # 1 GB
SOLR_BYTES   = 1073741824    # 1 GB
ATLAS_BYTES  = 4294967296    # 4 GB

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
PASS    = os.environ.get("MASTER_PASS", "Cl0ud3ra@Base732#SE")

def wait_cmd(cmd_id, interval=15, timeout=1800):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{CM}/commands/{cmd_id}", auth=AUTH, timeout=15)
        c = r.json()
        if not c.get("active", True):
            ok = c.get("success", False)
            print(f"    {'OK' if ok else 'FAIL'}: {c.get('resultMessage','')[:100]}")
            return ok
        print(f"    ... {c.get('resultMessage','running')[:80]}")
        time.sleep(interval)
    return False

def svc_exists(svc_name):
    r = requests.get(f"{CM}/clusters/{CLUSTER}/services", auth=AUTH, timeout=10)
    return any(s["name"] == svc_name for s in r.json().get("items", []))

def add_service(body):
    name = body[0]["name"]
    if svc_exists(name):
        print(f"  [{name}] already exists — skipping")
        return
    r = requests.post(f"{CM}/clusters/{CLUSTER}/services",
                      auth=AUTH, json={"items": body}, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  [{name}] FAILED HTTP {r.status_code}: {r.text[:200]}")
    else:
        print(f"  [{name}] created")

def add_roles(svc_name, roles):
    r = requests.post(f"{CM}/clusters/{CLUSTER}/services/{svc_name}/roles",
                      auth=AUTH, json={"items": roles}, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  [{svc_name}] roles FAILED: {r.text[:150]}")
    else:
        print(f"  [{svc_name}] {len(roles)} role(s) added")

def cfg(svc_name, items):
    r = requests.put(f"{CM}/clusters/{CLUSTER}/services/{svc_name}/config",
                     auth=AUTH, json={"items": items}, timeout=15)

def role_cfg(svc_name, rcg_name, items):
    r = requests.put(f"{CM}/clusters/{CLUSTER}/services/{svc_name}/roleConfigGroups/{rcg_name}/config",
                     auth=AUTH, json={"items": items}, timeout=15)

# ── Helper to make a role dict ───────────────────────────────────────────────
def role(role_type, name, svc_name):
    return {"name": name, "type": role_type,
            "hostRef": {"hostname": HOST},
            "roleConfigGroupRef": {"roleConfigGroupName": f"{svc_name}-{role_type}-BASE"}}

# ────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("Deploying services to CDP-Base-732")
print("=" * 60)

# Look up host ID (roles API requires hostId, not hostname)
r = requests.get(f"{CM}/hosts", auth=AUTH, timeout=10)
host_item = next((h for h in r.json().get("items", []) if h["hostname"] == HOST), None)
if not host_item:
    print(f"ERROR: Host {HOST} not found in CM")
    sys.exit(1)
HOST_ID = host_item["hostId"]
print(f"Host: {HOST}  id={HOST_ID}")

SERVICES = [
    # (service_name, service_type, [(role_type, role_name), ...], [(config_name, value)])
    ("zookeeper", "ZOOKEEPER",
     [("SERVER", "zookeeper-SERVER-1")], []),

    ("hdfs", "HDFS",
     [("NAMENODE",         "hdfs-NAMENODE-1"),
      ("SECONDARYNAMENODE","hdfs-SECONDARYNAMENODE-1"),
      ("DATANODE",         "hdfs-DATANODE-1"),
      ("BALANCER",         "hdfs-BALANCER-1"),
      ("GATEWAY",          "hdfs-GATEWAY-1")],
     [("dfs_replication", "1")]),

    ("yarn", "YARN",
     [("RESOURCEMANAGER","yarn-RESOURCEMANAGER-1"),
      ("NODEMANAGER",    "yarn-NODEMANAGER-1"),
      ("JOBHISTORY",     "yarn-JOBHISTORY-1"),
      ("GATEWAY",        "yarn-GATEWAY-1")], []),

    ("hive", "HIVE",
     [("HIVEMETASTORE","hive-HIVEMETASTORE-1"),
      ("GATEWAY",      "hive-GATEWAY-1")],
     [("hive_metastore_database_type",     "postgresql"),
      ("hive_metastore_database_host",     DB_HOST),
      ("hive_metastore_database_port",     DB_PORT),
      ("hive_metastore_database_name",     "metastore"),
      ("hive_metastore_database_user",     "hive"),
      ("hive_metastore_database_password", PASS)]),

    ("hive_on_tez", "HIVE_ON_TEZ",
     [("HIVESERVER2","hive_on_tez-HIVESERVER2-1"),
      ("GATEWAY",    "hive_on_tez-GATEWAY-1")], []),

    ("tez", "TEZ",
     [("GATEWAY","tez-GATEWAY-1")], []),

    ("hbase", "HBASE",
     [("MASTER",       "hbase-MASTER-1"),
      ("REGIONSERVER", "hbase-REGIONSERVER-1"),
      ("GATEWAY",      "hbase-GATEWAY-1")], []),

    ("impala", "IMPALA",
     [("CATALOGSERVER","impala-CATALOGSERVER-1"),
      ("STATESTORE",   "impala-STATESTORE-1"),
      ("IMPALAD",      "impala-IMPALAD-1")], []),

    ("kafka", "KAFKA",
     [("KAFKA_BROKER","kafka-KAFKA_BROKER-1")], []),

    ("infra_solr", "SOLR",
     [("SOLR_SERVER","infra_solr-SOLR_SERVER-1")], []),

    ("atlas", "ATLAS",
     [("ATLAS_SERVER","atlas-ATLAS_SERVER-1")], []),

    ("spark3", "SPARK3_ON_YARN",
     [("SPARK3_YARN_HISTORY_SERVER","spark3-SPARK3_YARN_HISTORY_SERVER-1"),
      ("GATEWAY",                   "spark3-GATEWAY-1")], []),

    # LIVY removed — not available as standalone service in CDH 7.3.2

    ("ozone", "OZONE",
     [("OZONE_MANAGER",            "ozone-OZONE_MANAGER-1"),
      ("STORAGE_CONTAINER_MANAGER","ozone-STORAGE_CONTAINER_MANAGER-1"),
      ("OZONEDATANODE",             "ozone-OZONEDATANODE-1"),
      ("RECON",                     "ozone-RECON-1"),
      ("S3_GATEWAY",                "ozone-S3_GATEWAY-1")], []),

    ("hue", "HUE",
     [("HUE_SERVER",        "hue-HUE_SERVER-1"),
      ("HUE_LOAD_BALANCER", "hue-HUE_LOAD_BALANCER-1")],
     [("database_type",     "postgresql"),
      ("database_host",     DB_HOST),
      ("database_port",     DB_PORT),
      ("database_name",     "hue"),
      ("database_user",     "hue"),
      ("database_password", PASS)]),

    ("ranger", "RANGER",
     [("RANGER_ADMIN",    "ranger-RANGER_ADMIN-1"),
      ("RANGER_TAGSYNC",  "ranger-RANGER_TAGSYNC-1"),
      ("RANGER_USERSYNC", "ranger-RANGER_USERSYNC-1")],
     [("ranger_database_type",     "PostgreSQL"),
      ("ranger_database_host",     DB_HOST),
      ("ranger_database_port",     DB_PORT),
      ("ranger_database_name",     "ranger"),
      ("ranger_database_user",     "rangeradmin"),
      ("ranger_database_password", PASS)]),
]

for svc_name, svc_type, role_defs, svc_configs in SERVICES:
    print(f"\n[{svc_name}] ({svc_type})")
    # Add service
    svc_body = [{"name": svc_name, "type": svc_type}]
    add_service(svc_body)
    # Apply service-level configs
    if svc_configs:
        cfg(svc_name, [{"name": k, "value": v} for k, v in svc_configs])
        print(f"  config applied ({len(svc_configs)} items)")
    # Add roles
    roles = []
    for role_type, role_name in role_defs:
        roles.append({
            "name": role_name,
            "type": role_type,
            "hostRef": {"hostId": HOST_ID}   # v58: must use hostId not hostname
        })
    if roles:
        add_roles(svc_name, roles)

# Apply YARN NM resource config
print("\nApplying YARN NodeManager resources...")
role_cfg("yarn", "yarn-NODEMANAGER-BASE",
         [{"name": "yarn_nodemanager_resource_memory_mb", "value": str(YARN_NM_MB)},
          {"name": "yarn_nodemanager_resource_cpu_vcores",  "value": str(YARN_NM_VCPU)},
          {"name": "yarn_nodemanager_local_dirs",           "value": "/data/yarn/nm"},
          {"name": "yarn_nodemanager_log_dirs",             "value": "/var/log/hadoop-yarn/nm"}])

# Apply Impala daemon memory
print("Applying Impala daemon memory...")
role_cfg("impala", "impala-IMPALAD-BASE",
         [{"name": "impalad_memory_limit", "value": str(IMPALA_BYTES)}])

print("\nAll services created. Running firstRun...")
r = requests.post(f"{CM}/clusters/{CLUSTER}/commands/firstRun", auth=AUTH, timeout=30)
print(f"firstRun HTTP {r.status_code}")
if r.status_code == 200:
    cmd_id = r.json().get("id")
    print(f"firstRun cmd={cmd_id}  (this takes 15-30 min)")
    wait_cmd(cmd_id, interval=30, timeout=5400)

print("\nDone.")
