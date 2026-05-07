#!/usr/bin/env python3.11
"""
07_setup_cms.py — Create and start the Cloudera Management Service (CMS)

CMS roles (from reference cluster):
  Alert Publisher, Event Server, Host Monitor, Reports Manager, Service Monitor

Database requirements:
  Activity Monitor  → amon DB (PostgreSQL)
  Reports Manager   → rman DB (PostgreSQL)

Note: headlamp_database_host for Reports Manager uses "host:port" format
      (there is no separate headlamp_database_port config key)

Run: python3.11 07_setup_cms.py
"""
import os, requests, time

CM_HOST       = os.environ["CM_HOST"]
CM_PORT       = os.environ.get("CM_PORT", "7180")
CM_ADMIN_USER = os.environ.get("CM_ADMIN_USER", "admin")
CM_ADMIN_PASS = os.environ.get("CM_ADMIN_PASS", "admin")
DB_HOST       = os.environ.get("DB_HOST", "localhost")
DB_PORT       = os.environ.get("DB_PORT", "5432")
MASTER_PASS   = os.environ.get("MASTER_PASS", "")

# Discover API version
CM_BASE_URL = f"http://{CM_HOST}:{CM_PORT}"
r = requests.get(f"{CM_BASE_URL}/api/version", auth=(CM_ADMIN_USER, CM_ADMIN_PASS), timeout=30)
r.raise_for_status()
API_VER = r.text.strip().strip('"')
CM      = f"{CM_BASE_URL}/api/{API_VER}"
AUTH    = (CM_ADMIN_USER, CM_ADMIN_PASS)

def step(msg):
    print(f"\n{'='*60}\n[CMS] {msg}\n{'='*60}")

def wait_cmd(cmd_id, interval=15, timeout=600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{CM}/commands/{cmd_id}", auth=AUTH, timeout=15)
        c = r.json()
        if not c.get("active", True):
            ok = c.get("success", False)
            print(f"  {'OK' if ok else 'FAIL'}: {c.get('resultMessage','')[:150]}")
            return ok
        print(f"  ... {c.get('resultMessage','running')[:80]}")
        time.sleep(interval)
    return False

def main():
    # Check if CMS already exists
    r = requests.get(f"{CM}/cm/service", auth=AUTH, timeout=10)
    if r.status_code == 200 and r.json().get("serviceState") == "STARTED":
        print("CMS is already running — skipping setup")
        return

    # --- 1. Get host ID ---
    step("Looking up host")
    host_id = requests.get(f"{CM}/hosts", auth=AUTH, timeout=10).json()["items"][0]["hostId"]
    hostname = requests.get(f"{CM}/hosts", auth=AUTH, timeout=10).json()["items"][0]["hostname"]
    print(f"  Host: {hostname} (id={host_id})")

    # --- 2. Create CMS with all 5 roles ---
    step("Creating Cloudera Management Service")
    r2 = requests.put(f"{CM}/cm/service", auth=AUTH, timeout=30,
        json={
            "type": "MGMT",
            "roles": [
                {"type": "ALERTPUBLISHER", "hostRef": {"hostId": host_id}},
                {"type": "EVENTSERVER",    "hostRef": {"hostId": host_id}},
                {"type": "HOSTMONITOR",    "hostRef": {"hostId": host_id}},
                {"type": "REPORTSMANAGER", "hostRef": {"hostId": host_id}},
                {"type": "SERVICEMONITOR", "hostRef": {"hostId": host_id}},
            ]
        })
    if r2.status_code not in (200, 201):
        if "already exists" in r2.text.lower():
            print("  CMS already exists — reconfiguring")
        else:
            print(f"  Create CMS HTTP {r2.status_code}: {r2.text[:200]}")
            return
    else:
        print("  CMS created")

    # --- 3. Configure database-backed roles ---
    step("Configuring CMS databases")
    r3 = requests.get(f"{CM}/cm/service/roleConfigGroups", auth=AUTH, timeout=10)
    for rcg in r3.json().get("items", []):
        role_type = rcg["roleType"]
        rcg_name  = rcg["name"]

        if role_type == "ACTIVITYMONITOR":
            requests.put(f"{CM}/cm/service/roleConfigGroups/{rcg_name}/config",
                auth=AUTH, timeout=10,
                json={"items": [
                    {"name": "firehose_database_type",     "value": "postgresql"},
                    {"name": "firehose_database_host",     "value": f"{DB_HOST}:{DB_PORT}"},
                    {"name": "firehose_database_name",     "value": "amon"},
                    {"name": "firehose_database_user",     "value": "amon"},
                    {"name": "firehose_database_password", "value": MASTER_PASS},
                ]})
            print(f"  Configured ACTIVITYMONITOR DB (amon @ {DB_HOST}:{DB_PORT})")

        elif role_type == "REPORTSMANAGER":
            # headlamp uses "host:port" in database_host — no separate port config
            requests.put(f"{CM}/cm/service/roleConfigGroups/{rcg_name}/config",
                auth=AUTH, timeout=10,
                json={"items": [
                    {"name": "headlamp_database_type",     "value": "postgresql"},
                    {"name": "headlamp_database_host",     "value": f"{DB_HOST}:{DB_PORT}"},
                    {"name": "headlamp_database_name",     "value": "rman"},
                    {"name": "headlamp_database_user",     "value": "rman"},
                    {"name": "headlamp_database_password", "value": MASTER_PASS},
                ]})
            print(f"  Configured REPORTSMANAGER DB (rman @ {DB_HOST}:{DB_PORT})")

    # --- 4. Start CMS ---
    step("Starting Cloudera Management Service")
    r4 = requests.post(f"{CM}/cm/service/commands/start", auth=AUTH, timeout=30)
    print(f"  Start CMS: HTTP {r4.status_code}")
    if r4.status_code == 200:
        cmd_id = r4.json().get("id")
        wait_cmd(cmd_id, interval=15, timeout=300)

    # --- 5. Verify ---
    time.sleep(10)
    r5 = requests.get(f"{CM}/cm/service/roles", auth=AUTH, timeout=10)
    print("\nCMS roles:")
    for role in r5.json().get("items", []):
        state = role.get("roleState", "?")
        icon  = "OK" if state == "STARTED" else "!!"
        print(f"  [{icon}] {role['type']:20s} {state}")

    print("\n[DONE] CMS setup complete")


if __name__ == "__main__":
    main()
