#!/usr/bin/env python3.11
"""
05_cluster_deploy.py — Deploy CDP Private Cloud Base 7.3.2 (single-node) via CM REST API

Approach: POST /cm/importClusterTemplate with hostTemplates + instantiator format.
This is the ONLY format that works with CM API v58 — inline hostRef in roles is rejected.

Verified fixes from live testing (May 2026):
  - Parcel repo:              cdh7 (not cdp-pvc-ds)
  - Parcel build:             7.3.2-1.cdh7.3.2.p0.77083870
  - Activate parcel command:  'activate' (not 'activateParcel' in v58)
  - Template endpoint:        /cm/importClusterTemplate (not /clusters/importClusterTemplate)
  - Template requires:        displayName field
  - ranger_database_type:     'postgresql' lowercase
  - hive_metastore_database_type + port: must be explicit (defaults to mysql/3306)
  - hue.database_port:        must be explicit 5432 (defaults to 3306)

YARN resources (32 vCPU / 128 GB single node — conservative for all services co-located):
  NM memory: 32 GB  (was 50 GB — reduced to prevent overcommit with 20 services)
  NM vCores: 16     (was 24 — leaves 16 for system services)

CM API reference: https://cloudera.github.io/cm_api/apidocs/v51/index.html
Requires: pip install requests
Run:      python3.11 05_cluster_deploy.py
"""
import os, sys, json, time, argparse, requests
from urllib.parse import urljoin

# ---------------------------------------------------------------------------
# Config from environment (source config.env before running)
# ---------------------------------------------------------------------------
CM_HOST       = os.environ["CM_HOST"]
CM_PORT       = os.environ.get("CM_PORT", "7180")
CM_ADMIN_USER = os.environ.get("CM_ADMIN_USER", "admin")
CM_ADMIN_PASS = os.environ.get("CM_ADMIN_PASS", "admin")
NODE_HOST     = os.environ["NODE_HOST"]
CLUSTER_NAME  = os.environ.get("CLUSTER_NAME", "CDP-Base-732")
PARCEL_BUILD  = os.environ.get("PARCEL_BUILD", "7.3.2-1.cdh7.3.2.p0.77083870")
PARCEL_REPO   = os.environ["PARCEL_REPO"]
PARCEL_PRODUCT = "CDH"

DB_HOST     = os.environ.get("DB_HOST", "localhost")
DB_PORT     = os.environ.get("DB_PORT", "5432")
MASTER_PASS = os.environ.get("MASTER_PASS", "")

DFS_DATA_DIRS   = os.environ.get("DFS_DATA_DIRS", "/data/dfs/dn")
YARN_LOCAL_DIRS = os.environ.get("YARN_LOCAL_DIRS", "/data/yarn/nm")
YARN_LOG_DIRS   = os.environ.get("YARN_LOG_DIRS", "/var/log/hadoop-yarn/nm")

# ---------------------------------------------------------------------------
# Resource allocation — conservative for single-node with 20 services
# 32 GB NM memory leaves headroom for Impala (20 GB), system, and all other services
# ---------------------------------------------------------------------------
YARN_NM_MEMORY_MB   = 32768   # 32 GB (reduced from 50 GB to prevent host overcommit)
YARN_NM_VCORES      = 16      # 16 vCores (leaves 16 for system/other services)
IMPALA_MEM_BYTES    = 21474836480  # 20 GB
HBASE_RS_HEAP_BYTES = 2147483648   # 2 GB  (Atlas prereq only)
KAFKA_HEAP_BYTES    = 1073741824   # 1 GB  (Atlas prereq only)
SOLR_HEAP_BYTES     = 1073741824   # 1 GB  (Atlas/Ranger prereq only)
ATLAS_HEAP_BYTES    = 4294967296   # 4 GB


# ---------------------------------------------------------------------------
# CM API client — auto-discovers API version
# ---------------------------------------------------------------------------
class CmApi:
    def __init__(self, host, port, user, password):
        base = f"http://{host}:{port}"
        r = requests.get(f"{base}/api/version", auth=(user, password), timeout=30)
        r.raise_for_status()
        api_ver = r.text.strip().strip('"')
        self.base = f"{base}/api/{api_ver}"
        self.auth = (user, password)
        print(f"[CM API] {self.base} (version {api_ver})")

    def get(self, path, **kw):
        r = requests.get(urljoin(self.base + "/", path.lstrip("/")),
                         auth=self.auth, timeout=60, **kw)
        r.raise_for_status()
        return r.json()

    def post(self, path, data=None, params=None, **kw):
        r = requests.post(urljoin(self.base + "/", path.lstrip("/")),
                          auth=self.auth, json=data, params=params, timeout=120, **kw)
        r.raise_for_status()
        return r.json()

    def put(self, path, data=None, **kw):
        r = requests.put(urljoin(self.base + "/", path.lstrip("/")),
                         auth=self.auth, json=data, timeout=60, **kw)
        r.raise_for_status()
        return r.json()

    def wait_for_command(self, cmd_id: int, poll_interval=15, timeout=3600) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            cmd = self.get(f"/commands/{cmd_id}")
            if not cmd.get("active", True):
                if cmd.get("success", False):
                    print(f"  Command {cmd_id} succeeded: {cmd.get('resultMessage','')}")
                    return cmd
                raise RuntimeError(f"Command {cmd_id} FAILED: {cmd.get('resultMessage','')}")
            print(f"  Command {cmd_id}: {cmd.get('resultMessage','running')}...")
            time.sleep(poll_interval)
        raise TimeoutError(f"Command {cmd_id} timed out after {timeout}s")


def step(msg):
    print(f"\n{'='*65}\n[STEP] {msg}\n{'='*65}")


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------
def configure_parcel_repo(api: CmApi):
    step("Configure parcel repository")
    cfg = api.get("/cm/config")
    existing = next((i["value"] for i in cfg.get("items", [])
                     if i["name"] == "REMOTE_PARCEL_REPO_URLS"), "")
    if PARCEL_REPO not in existing:
        api.put("/cm/config", {"items": [
            {"name": "REMOTE_PARCEL_REPO_URLS",
             "value": f"{existing},{PARCEL_REPO}" if existing else PARCEL_REPO}
        ]})
    print(f"  Parcel repo configured: {PARCEL_REPO}")


def wait_for_host(api: CmApi) -> str:
    step(f"Wait for {NODE_HOST} to register with CM agent")
    for _ in range(30):
        match = next((h for h in api.get("/hosts").get("items", [])
                      if h["hostname"] == NODE_HOST), None)
        if match:
            print(f"  Host registered: {NODE_HOST} (id={match['hostId']})")
            return match["hostId"]
        print(f"  Waiting for {NODE_HOST}...")
        time.sleep(10)
    raise RuntimeError(f"{NODE_HOST} never appeared. Check cloudera-scm-agent is running.")


def deploy_parcel(api: CmApi, cluster_name: str):
    """Download, distribute, activate the CDH parcel for the cluster."""
    step(f"Parcel: {PARCEL_PRODUCT} {PARCEL_BUILD}")

    # Refresh parcel repos so CM discovers the new repo
    print("  Refreshing parcel repos...")
    try:
        resp = api.post("/cm/commands/refreshParcelRepos")
        cmd_id = resp.get("id")
        if cmd_id:
            api.wait_for_command(cmd_id, poll_interval=5, timeout=120)
    except Exception as e:
        print(f"  Refresh warning (non-fatal): {e}")
    time.sleep(10)

    base = f"/clusters/{cluster_name}/parcels/products/{PARCEL_PRODUCT}/versions/{PARCEL_BUILD}"

    # Wait for parcel to appear (CM may need extra time)
    print("  Waiting for CM to discover parcel...")
    for attempt in range(18):
        try:
            info = api.get(base)
            print(f"  Parcel found — stage: {info.get('stage')}")
            break
        except requests.HTTPError as e:
            if "404" in str(e):
                print(f"  [{attempt*10}s] Not visible yet, retrying...")
                time.sleep(10)
            else:
                raise
    else:
        raise RuntimeError(f"Parcel {PARCEL_BUILD} never appeared. Check PARCEL_REPO URL and credentials.")

    def stage():
        return api.get(base).get("stage", "UNKNOWN")

    # v58: activate command is 'activate' not 'activateParcel'
    transitions = [
        ("startDownload",    "DOWNLOADED",  180, 15),
        ("startDistribution","DISTRIBUTED", 180, 20),
        ("activate",         "ACTIVATED",    60, 10),   # 'activate' in CM API v58
    ]
    for cmd, target, polls, interval in transitions:
        s = stage()
        if s in (target, "ACTIVATED"):
            print(f"  Stage already: {s}")
            continue
        print(f"  Running {cmd}...")
        try:
            api.post(f"{base}/commands/{cmd}")
        except requests.HTTPError:
            pass
        for _ in range(polls):
            s = stage()
            print(f"  Stage: {s}")
            if s in (target, "ACTIVATED"):
                break
            if "FAILED" in s:
                raise RuntimeError(f"Parcel failed at stage: {s}")
            time.sleep(interval)
    print(f"  Final stage: {stage()}")


def import_cluster_template(api: CmApi, host_id: str) -> int:
    """
    Import cluster using /cm/importClusterTemplate with hostTemplates + instantiator format.
    This is the ONLY format that works with CM API v58.
    Returns the command ID so the caller can poll it.
    """
    step(f"Import cluster template (20 services, hostTemplates format)")

    # All role config groups that go on the single node
    all_role_config_groups = [
        "atlas-ATLAS_SERVER-BASE",
        "hbase-GATEWAY-BASE", "hbase-MASTER-BASE", "hbase-REGIONSERVER-BASE",
        "hdfs-BALANCER-BASE", "hdfs-DATANODE-BASE", "hdfs-GATEWAY-BASE",
        "hdfs-NAMENODE-BASE", "hdfs-SECONDARYNAMENODE-BASE",
        "hive-GATEWAY-BASE", "hive-HIVEMETASTORE-BASE",
        "hive_on_tez-GATEWAY-BASE", "hive_on_tez-HIVESERVER2-BASE",
        "hue-HUE_LOAD_BALANCER-BASE", "hue-HUE_SERVER-BASE",
        "iceberg_replication-ICEBERG_REPLICATION_ADMINSERVER-BASE",
        "impala-CATALOGSERVER-BASE", "impala-IMPALAD-BASE", "impala-STATESTORE-BASE",
        "kafka-KAFKA_BROKER-BASE",
        "lakehouse_optimizer-CLO_SERVER-BASE",
        "livy_for_spark3-LIVY_SERVER-BASE",
        "meteringv2-METERINGV2_SERVER-BASE",
        "ozone-GATEWAY-BASE", "ozone-HTTPFS_GATEWAY-BASE",
        "ozone-OZONE_DATANODE-BASE", "ozone-OZONE_MANAGER-BASE",
        "ozone-OZONE_RECON-BASE", "ozone-S3_GATEWAY-BASE",
        "ozone-STORAGE_CONTAINER_MANAGER-BASE",
        "ranger-RANGER_ADMIN-BASE", "ranger-RANGER_TAGSYNC-BASE", "ranger-RANGER_USERSYNC-BASE",
        "solr-SOLR_SERVER-BASE",
        "spark3_on_yarn-GATEWAY-BASE", "spark3_on_yarn-SPARK3_YARN_HISTORY_SERVER-BASE",
        "tez-GATEWAY-BASE",
        "yarn-GATEWAY-BASE", "yarn-JOBHISTORY-BASE",
        "yarn-NODEMANAGER-BASE", "yarn-RESOURCEMANAGER-BASE",
        "zookeeper-SERVER-BASE",
        "core_settings-GATEWAY-BASE",
    ]

    template = {
        "cdhVersion": PARCEL_BUILD,
        "displayName": CLUSTER_NAME,          # required — CM rejects without it
        "repositories": [PARCEL_REPO],
        "products": [{"product": PARCEL_PRODUCT, "version": PARCEL_BUILD}],

        # ── Services (roleConfigGroups only, no inline roles) ──────────────
        "services": [
            {"refName": "zookeeper",   "serviceType": "ZOOKEEPER",
             "serviceConfigs": [{"name": "service_config_suppression_server_count_validator", "value": "true"}],
             "roleConfigGroups": [
                 {"refName": "zookeeper-SERVER-BASE", "roleType": "SERVER", "base": True, "configs": []}]},

            {"refName": "hdfs", "serviceType": "HDFS",
             "serviceConfigs": [{"name": "dfs_replication", "value": "1"}],
             "roleConfigGroups": [
                 {"refName": "hdfs-NAMENODE-BASE",          "roleType": "NAMENODE",          "base": True, "configs": []},
                 {"refName": "hdfs-SECONDARYNAMENODE-BASE", "roleType": "SECONDARYNAMENODE", "base": True, "configs": []},
                 {"refName": "hdfs-DATANODE-BASE",          "roleType": "DATANODE",          "base": True, "configs": []},
                 {"refName": "hdfs-BALANCER-BASE",          "roleType": "BALANCER",          "base": True, "configs": []},
                 {"refName": "hdfs-GATEWAY-BASE",           "roleType": "GATEWAY",           "base": True, "configs": []},
             ]},

            {"refName": "yarn", "serviceType": "YARN",
             "roleConfigGroups": [
                 {"refName": "yarn-RESOURCEMANAGER-BASE", "roleType": "RESOURCEMANAGER", "base": True, "configs": []},
                 {"refName": "yarn-NODEMANAGER-BASE",     "roleType": "NODEMANAGER",     "base": True, "configs": []},
                 {"refName": "yarn-JOBHISTORY-BASE",      "roleType": "JOBHISTORY",      "base": True, "configs": []},
                 {"refName": "yarn-GATEWAY-BASE",         "roleType": "GATEWAY",         "base": True, "configs": []},
             ]},

            {"refName": "hive", "serviceType": "HIVE",
             "roleConfigGroups": [
                 {"refName": "hive-HIVEMETASTORE-BASE", "roleType": "HIVEMETASTORE", "base": True, "configs": []},
                 {"refName": "hive-GATEWAY-BASE",       "roleType": "GATEWAY",       "base": True, "configs": []},
             ]},

            {"refName": "hive_on_tez", "serviceType": "HIVE_ON_TEZ",
             "roleConfigGroups": [
                 {"refName": "hive_on_tez-HIVESERVER2-BASE", "roleType": "HIVESERVER2", "base": True, "configs": []},
                 {"refName": "hive_on_tez-GATEWAY-BASE",     "roleType": "GATEWAY",     "base": True, "configs": []},
             ]},

            {"refName": "tez", "serviceType": "TEZ",
             "roleConfigGroups": [
                 {"refName": "tez-GATEWAY-BASE", "roleType": "GATEWAY", "base": True, "configs": []}]},

            {"refName": "hbase", "serviceType": "HBASE",
             "roleConfigGroups": [
                 {"refName": "hbase-MASTER-BASE",       "roleType": "MASTER",       "base": True,
                  "configs": [{"name": "hbase_master_java_heapsize", "value": str(HBASE_RS_HEAP_BYTES)}]},
                 {"refName": "hbase-REGIONSERVER-BASE", "roleType": "REGIONSERVER", "base": True,
                  "configs": [{"name": "hbase_regionserver_java_heapsize", "value": str(HBASE_RS_HEAP_BYTES)}]},
                 {"refName": "hbase-GATEWAY-BASE",      "roleType": "GATEWAY",      "base": True, "configs": []},
             ]},

            {"refName": "impala", "serviceType": "IMPALA",
             "roleConfigGroups": [
                 {"refName": "impala-CATALOGSERVER-BASE", "roleType": "CATALOGSERVER", "base": True, "configs": []},
                 {"refName": "impala-STATESTORE-BASE",    "roleType": "STATESTORE",    "base": True, "configs": []},
                 {"refName": "impala-IMPALAD-BASE",       "roleType": "IMPALAD",       "base": True,
                  "configs": [{"name": "impalad_memory_limit", "value": str(IMPALA_MEM_BYTES)}]},
             ]},

            {"refName": "kafka", "serviceType": "KAFKA",
             "roleConfigGroups": [
                 {"refName": "kafka-KAFKA_BROKER-BASE", "roleType": "KAFKA_BROKER", "base": True,
                  "configs": [{"name": "kafka_broker_java_heapsize", "value": str(KAFKA_HEAP_BYTES)}]}]},

            {"refName": "solr", "serviceType": "SOLR",
             "roleConfigGroups": [
                 {"refName": "solr-SOLR_SERVER-BASE", "roleType": "SOLR_SERVER", "base": True,
                  "configs": [{"name": "solr_java_heapsize", "value": str(SOLR_HEAP_BYTES)}]}]},

            {"refName": "atlas", "serviceType": "ATLAS",
             "roleConfigGroups": [
                 {"refName": "atlas-ATLAS_SERVER-BASE", "roleType": "ATLAS_SERVER", "base": True,
                  "configs": [{"name": "atlas_server_heap_size", "value": str(ATLAS_HEAP_BYTES)}]}]},

            {"refName": "spark3_on_yarn", "serviceType": "SPARK3_ON_YARN",
             "roleConfigGroups": [
                 {"refName": "spark3_on_yarn-SPARK3_YARN_HISTORY_SERVER-BASE",
                  "roleType": "SPARK3_YARN_HISTORY_SERVER", "base": True, "configs": []},
                 {"refName": "spark3_on_yarn-GATEWAY-BASE", "roleType": "GATEWAY", "base": True, "configs": []},
             ]},

            {"refName": "livy_for_spark3", "serviceType": "LIVY_FOR_SPARK3",
             "roleConfigGroups": [
                 {"refName": "livy_for_spark3-LIVY_SERVER-BASE", "roleType": "LIVY_SERVER",
                  "base": True, "configs": []}]},

            {"refName": "ozone", "serviceType": "OZONE",
             "roleConfigGroups": [
                 {"refName": "ozone-OZONE_MANAGER-BASE",            "roleType": "OZONE_MANAGER",            "base": True, "configs": []},
                 {"refName": "ozone-STORAGE_CONTAINER_MANAGER-BASE","roleType": "STORAGE_CONTAINER_MANAGER","base": True, "configs": []},
                 {"refName": "ozone-OZONE_DATANODE-BASE",            "roleType": "OZONE_DATANODE",           "base": True, "configs": []},
                 {"refName": "ozone-OZONE_RECON-BASE",               "roleType": "OZONE_RECON",              "base": True, "configs": []},
                 {"refName": "ozone-S3_GATEWAY-BASE",                "roleType": "S3_GATEWAY",               "base": True, "configs": []},
                 {"refName": "ozone-HTTPFS_GATEWAY-BASE",            "roleType": "HTTPFS_GATEWAY",           "base": True, "configs": []},
                 {"refName": "ozone-GATEWAY-BASE",                   "roleType": "GATEWAY",                  "base": True, "configs": []},
             ]},

            {"refName": "hue", "serviceType": "HUE",
             "roleConfigGroups": [
                 {"refName": "hue-HUE_SERVER-BASE",        "roleType": "HUE_SERVER",        "base": True, "configs": []},
                 {"refName": "hue-HUE_LOAD_BALANCER-BASE", "roleType": "HUE_LOAD_BALANCER", "base": True, "configs": []},
             ]},

            {"refName": "ranger", "serviceType": "RANGER",
             "roleConfigGroups": [
                 {"refName": "ranger-RANGER_ADMIN-BASE",    "roleType": "RANGER_ADMIN",    "base": True, "configs": []},
                 {"refName": "ranger-RANGER_TAGSYNC-BASE",  "roleType": "RANGER_TAGSYNC",  "base": True, "configs": []},
                 {"refName": "ranger-RANGER_USERSYNC-BASE", "roleType": "RANGER_USERSYNC", "base": True, "configs": []},
             ]},

            {"refName": "meteringv2", "serviceType": "METERINGV2",
             "roleConfigGroups": [
                 {"refName": "meteringv2-METERINGV2_SERVER-BASE", "roleType": "METERINGV2_SERVER",
                  "base": True, "configs": []}]},

            {"refName": "lakehouse_optimizer", "serviceType": "LAKEHOUSE_OPTIMIZER",
             "roleConfigGroups": [
                 {"refName": "lakehouse_optimizer-CLO_SERVER-BASE", "roleType": "CLO_SERVER",
                  "base": True, "configs": []}]},

            {"refName": "iceberg_replication", "serviceType": "ICEBERG_REPLICATION",
             "roleConfigGroups": [
                 {"refName": "iceberg_replication-ICEBERG_REPLICATION_ADMINSERVER-BASE",
                  "roleType": "ICEBERG_REPLICATION_ADMINSERVER", "base": True, "configs": []}]},

            {"refName": "core_settings", "serviceType": "CORE_SETTINGS",
             "roleConfigGroups": [
                 {"refName": "core_settings-GATEWAY-BASE", "roleType": "GATEWAY", "base": True, "configs": []}]},
        ],

        # ── Single hostTemplate — ALL roles on one node ────────────────────
        "hostTemplates": [
            {
                "refName": "single-node-template",
                "cardinality": 1,
                "roleConfigGroupsRefNames": all_role_config_groups,
            }
        ],

        # ── Instantiator — maps host + fills all required variables ─────────
        "instantiator": {
            "clusterName": CLUSTER_NAME,
            "hosts": [
                {"hostName": NODE_HOST, "hostTemplateRefName": "single-node-template"}
            ],
            "variables": [
                # HDFS paths
                {"name": "hdfs-NAMENODE-BASE-dfs_name_dir_list",               "value": "/data/dfs/nn"},
                {"name": "hdfs-SECONDARYNAMENODE-BASE-fs_checkpoint_dir_list", "value": "/data/dfs/snn"},
                {"name": "hdfs-DATANODE-BASE-dfs_data_dir_list",               "value": DFS_DATA_DIRS},
                # YARN — conservative NM resources (32 GB / 16 vCores for single-node with 20 services)
                {"name": "yarn-NODEMANAGER-BASE-yarn_nodemanager_local_dirs",          "value": YARN_LOCAL_DIRS},
                {"name": "yarn-NODEMANAGER-BASE-yarn_nodemanager_resource_memory_mb",  "value": str(YARN_NM_MEMORY_MB)},
                {"name": "yarn-NODEMANAGER-BASE-yarn_nodemanager_resource_cpu_vcores", "value": str(YARN_NM_VCORES)},
                # ZooKeeper
                {"name": "zookeeper-SERVER-BASE-dataDir",    "value": "/data/zookeeper"},
                {"name": "zookeeper-SERVER-BASE-dataLogDir", "value": "/data/zookeeper"},
                # Impala
                {"name": "impala-IMPALAD-BASE-scratch_dirs", "value": "/data/impala/impalad"},
                # Ozone
                {"name": "ozone-OZONE_DATANODE-BASE-hdds.datanode.dir", "value": "/data/hadoop-ozone/datanode/data"},
                # Hive Metastore — MUST specify type+port explicitly; defaults to mysql/3306
                {"name": "hive-hive_metastore_database_type",     "value": "postgresql"},
                {"name": "hive-hive_metastore_database_host",     "value": DB_HOST},
                {"name": "hive-hive_metastore_database_port",     "value": DB_PORT},
                {"name": "hive-hive_metastore_database_name",     "value": "metastore"},
                {"name": "hive-hive_metastore_database_user",     "value": "hive"},
                {"name": "hive-hive_metastore_database_password", "value": MASTER_PASS},
                # Hue — MUST include database_port; omitting defaults to 3306 (MySQL)
                {"name": "hue-database_type",     "value": "postgresql"},
                {"name": "hue-database_host",     "value": DB_HOST},
                {"name": "hue-database_port",     "value": DB_PORT},     # CRITICAL
                {"name": "hue-database_name",     "value": "hue"},
                {"name": "hue-database_user",     "value": "hue"},
                {"name": "hue-database_password", "value": MASTER_PASS},
                # Ranger — lowercase 'postgresql' required; 'PostgreSQL' causes parse error
                {"name": "ranger-ranger_database_type",     "value": "postgresql"},
                {"name": "ranger-ranger_database_host",     "value": DB_HOST},
                {"name": "ranger-ranger_database_port",     "value": DB_PORT},
                {"name": "ranger-ranger_database_name",     "value": "ranger"},
                {"name": "ranger-ranger_database_user",     "value": "rangeradmin"},
                {"name": "ranger-ranger_database_password", "value": MASTER_PASS},
                {"name": "ranger-rangeradmin_user_password",    "value": MASTER_PASS},
                {"name": "ranger-keyadmin_user_password",       "value": MASTER_PASS},
                {"name": "ranger-rangertagsync_user_password",  "value": MASTER_PASS},
                {"name": "ranger-rangerusersync_user_password", "value": MASTER_PASS},
                # Atlas admin password
                {"name": "atlas-ATLAS_SERVER-BASE-atlas_admin_password", "value": MASTER_PASS},
            ]
        }
    }

    tpl_file = "/tmp/cdp_template.json"
    with open(tpl_file, "w") as f:
        json.dump(template, f, indent=2)
    print(f"  Template saved to {tpl_file}  ({len(template['services'])} services)")

    # POST to /cm/importClusterTemplate (not /clusters/importClusterTemplate)
    resp = api.post("/cm/importClusterTemplate?addRepositories=true", data=template)
    cmd_id = resp.get("id")
    print(f"  importClusterTemplate command ID: {cmd_id}")
    return cmd_id


def start_remaining_services(api: CmApi):
    """Start any services that are STOPPED after firstRun (firstRun may only run a subset)."""
    step("Start any remaining STOPPED services")
    r = requests.post(
        urljoin(api.base + "/", f"clusters/{CLUSTER_NAME}/commands/start"),
        auth=api.auth, timeout=30
    )
    if r.status_code == 200:
        cmd_id = r.json().get("id")
        print(f"  Start command ID: {cmd_id}")
        api.wait_for_command(cmd_id, poll_interval=30, timeout=3600)
    else:
        print(f"  Start HTTP {r.status_code} (may already be started): {r.text[:100]}")


def print_service_status(api: CmApi):
    svcs = api.get(f"/clusters/{CLUSTER_NAME}/services").get("items", [])
    started = [s["name"] for s in svcs if s.get("serviceState") == "STARTED"]
    stopped = [s["name"] for s in svcs if s.get("serviceState") not in ("STARTED", "NA")]
    print(f"  STARTED ({len(started)}): {started}")
    if stopped:
        print(f"  STOPPED: {stopped}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-to",
                        choices=["parcel", "template", "start"],
                        help="Resume from a specific step")
    args = parser.parse_args()

    api = CmApi(CM_HOST, CM_PORT, CM_ADMIN_USER, CM_ADMIN_PASS)
    skip = args.skip_to

    if not skip:
        configure_parcel_repo(api)

    host_id = wait_for_host(api)

    if not skip:
        # Create minimal cluster so we have a target for parcel operations
        try:
            api.get(f"/clusters/{CLUSTER_NAME}")
            print(f"  Cluster '{CLUSTER_NAME}' already exists")
        except requests.HTTPError:
            api.post("/clusters", {"items": [{
                "name": CLUSTER_NAME, "displayName": CLUSTER_NAME,
                "fullVersion": PARCEL_BUILD,
            }]})
            print(f"  Cluster '{CLUSTER_NAME}' created")
        # Add host to cluster
        try:
            api.post(f"/clusters/{CLUSTER_NAME}/hosts",
                     {"items": [{"hostId": host_id}]})
        except requests.HTTPError:
            pass
        deploy_parcel(api, CLUSTER_NAME)

    elif skip == "parcel":
        try:
            api.get(f"/clusters/{CLUSTER_NAME}")
        except requests.HTTPError:
            api.post("/clusters", {"items": [{
                "name": CLUSTER_NAME, "displayName": CLUSTER_NAME,
                "fullVersion": PARCEL_BUILD,
            }]})
            try:
                api.post(f"/clusters/{CLUSTER_NAME}/hosts",
                         {"items": [{"hostId": host_id}]})
            except requests.HTTPError:
                pass
        configure_parcel_repo(api)
        deploy_parcel(api, CLUSTER_NAME)

    if not skip or skip in ("parcel", "template"):
        # Delete the minimal cluster (if it exists) so importClusterTemplate creates it fresh
        try:
            # Remove all services and cluster before re-importing
            svcs = api.get(f"/clusters/{CLUSTER_NAME}/services").get("items", [])
            if svcs:
                print(f"  Cleaning up {len(svcs)} existing services...")
                for s in svcs:
                    for role in api.get(f"/clusters/{CLUSTER_NAME}/services/{s['name']}/roles").get("items", []):
                        try:
                            requests.delete(
                                urljoin(api.base + "/",
                                        f"clusters/{CLUSTER_NAME}/services/{s['name']}/roles/{role['name']}"),
                                auth=api.auth, timeout=10)
                        except Exception:
                            pass
                    try:
                        requests.delete(
                            urljoin(api.base + "/", f"clusters/{CLUSTER_NAME}/services/{s['name']}"),
                            auth=api.auth, timeout=10)
                    except Exception:
                        pass
            # Delete cluster
            requests.delete(urljoin(api.base + "/", f"clusters/{CLUSTER_NAME}"),
                            auth=api.auth, timeout=15)
            print("  Old cluster removed")
        except Exception as e:
            print(f"  Cleanup note: {e}")
        time.sleep(3)

        cmd_id = import_cluster_template(api, host_id)
        # Poll the import command
        deadline = time.time() + 3600
        while time.time() < deadline:
            cmd = api.get(f"/commands/{cmd_id}")
            if not cmd.get("active", True):
                print(f"  Import {'succeeded' if cmd.get('success') else 'completed (partial)'}: "
                      f"{cmd.get('resultMessage','')[:150]}")
                break
            print(f"  Import running: {cmd.get('resultMessage','...')[:80]}")
            time.sleep(30)

    # Start any remaining stopped services
    if not skip or skip in ("parcel", "template", "start"):
        print_service_status(api)
        start_remaining_services(api)
        print_service_status(api)

    print(f"\n[DONE] Cluster deployment complete.")
    print(f"  Cloudera Manager: http://{CM_HOST}:{CM_PORT}")
    print(f"  Hue:              http://{CM_HOST}:8888")
    print(f"  Ranger:           http://{CM_HOST}:6080")
    print(f"  Atlas:            http://{CM_HOST}:21000")


if __name__ == "__main__":
    main()
