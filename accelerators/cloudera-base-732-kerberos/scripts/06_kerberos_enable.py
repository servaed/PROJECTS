#!/usr/bin/env python3.11
"""
06_kerberos_enable.py — Enable Kerberos authentication on the CDP cluster via CM API
Uses FreeIPA as the KDC (MIT-compatible interface)

Process (from Cloudera security guide):
  1. Set CM-level Kerberos config (KDC host, realm, type=MIT KDC)
  2. Call importAdminCredentials — CM creates cmadin-<id> service account in FreeIPA
  3. Call configureForKerberos on the cluster
  4. Deploy client configs and restart stale services

Reference: https://docs.cloudera.com/cdp-private-cloud-base/7.1.8/security-kerberos-authentication/
Requires: pip install requests
Run:      python3.11 06_kerberos_enable.py
"""
import os
import stat
import sys
import time
import requests
import urllib3
from urllib.parse import urljoin

# Suppress SSL warnings — expected with CM's self-signed Auto-TLS certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Load config from environment
# ---------------------------------------------------------------------------
CM_HOST = os.environ["CM_HOST"]
# CM_PORT: 7183 after Auto-TLS (HTTPS), 7180 before (HTTP)
CM_PORT = os.environ.get("CM_PORT", "7183")
CM_ADMIN_USER = os.environ.get("CM_ADMIN_USER", "admin")
CM_ADMIN_PASS = os.environ.get("CM_ADMIN_PASS", "admin")
# Use HTTPS if port is 7183, HTTP otherwise
CM_PROTOCOL = "https" if CM_PORT == "7183" else "http"
CM_VERIFY_SSL = False   # CM uses a self-signed CA — disable verification
CLUSTER_NAME = os.environ.get("CLUSTER_NAME", "CDP-Base-732")
REALM = os.environ["REALM"]
IPA_HOST = os.environ["IPA_HOST"]
IPA_ADMIN_PASS = os.environ["IPA_ADMIN_PASS"]
KRB5_ADMIN_USER = os.environ.get("KRB5_ADMIN_USER", "admin")
KRB5_ADMIN_PASS = os.environ.get("KRB5_ADMIN_PASS", IPA_ADMIN_PASS)


# ---------------------------------------------------------------------------
# CM API client (reuse pattern from 05_cluster_deploy.py)
# ---------------------------------------------------------------------------
class CmApi:
    def __init__(self, host, port, user, password):
        base = f"{CM_PROTOCOL}://{host}:{port}"
        r = requests.get(f"{base}/api/version", auth=(user, password),
                         timeout=30, verify=CM_VERIFY_SSL)
        r.raise_for_status()
        api_ver = r.text.strip().strip('"')
        self.base = f"{base}/api/{api_ver}"
        self.auth = (user, password)
        print(f"[CM API] Connected: {self.base}")

    def get(self, path, **kwargs):
        r = requests.get(urljoin(self.base + "/", path.lstrip("/")),
                         auth=self.auth, timeout=60, verify=CM_VERIFY_SSL, **kwargs)
        r.raise_for_status()
        return r.json()

    def post(self, path, data=None, params=None, **kwargs):
        r = requests.post(urljoin(self.base + "/", path.lstrip("/")),
                          auth=self.auth, json=data, params=params,
                          timeout=60, verify=CM_VERIFY_SSL, **kwargs)
        if not r.ok:
            print(f"  HTTP {r.status_code} error body: {r.text[:600]}")
        r.raise_for_status()
        return r.json()

    def put(self, path, data=None, **kwargs):
        r = requests.put(urljoin(self.base + "/", path.lstrip("/")),
                         auth=self.auth, json=data, timeout=60, verify=CM_VERIFY_SSL, **kwargs)
        r.raise_for_status()
        return r.json()

    def wait_for_command(self, cmd_id: int, poll_interval: int = 15,
                         timeout: int = 1800) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            cmd = self.get(f"/commands/{cmd_id}")
            if not cmd.get("active", True):
                if cmd.get("success", False):
                    print(f"  Command {cmd_id} succeeded: {cmd.get('resultMessage','')}")
                    return cmd
                else:
                    raise RuntimeError(
                        f"Command {cmd_id} FAILED: {cmd.get('resultMessage','')}")
            print(f"  Command {cmd_id} in progress... ({cmd.get('resultMessage','running')})")
            time.sleep(poll_interval)
        raise TimeoutError(f"Command {cmd_id} did not finish within {timeout}s")


def step(msg: str):
    print(f"\n{'='*60}\n[STEP] {msg}\n{'='*60}")


# ---------------------------------------------------------------------------
# Step 1: Configure CM-level Kerberos settings
# ---------------------------------------------------------------------------
def configure_cm_kerberos(api: CmApi):
    step("Configure CM Kerberos settings (KDC host, realm, KDC type)")
    # KDC_TYPE must be "MIT KDC" for FreeIPA (it exposes a standard MIT interface)
    # Confirmed in Cloudera security guide: use "MIT KDC" not "Red Hat IPA"
    # Valid CM Kerberos config parameter names (from CM API docs):
    # KRB_RENEWABLE / KRB_FORWARDABLE are NOT valid CM config names —
    # those are set by CM in the managed krb5.conf automatically when
    # KRB_MANAGE_KRB5_CONF=true; passing them here would cause a 400 error.
    configs = [
        {"name": "KDC_HOST",             "value": IPA_HOST},
        {"name": "SECURITY_REALM",       "value": REALM},
        {"name": "KDC_TYPE",             "value": "MIT KDC"},
        {"name": "KRB_MANAGE_KRB5_CONF", "value": "true"},
        # AES256 + AES128 only; DES/RC4 are insecure and disabled by default in RHEL 9
        {"name": "KRB_ENC_TYPES",        "value": "aes256-cts aes128-cts"},
    ]
    api.put("/cm/config", {"items": configs})
    print(f"  KDC host:  {IPA_HOST}")
    print(f"  Realm:     {REALM}")
    print(f"  KDC type:  MIT KDC (FreeIPA)")


# ---------------------------------------------------------------------------
# Step 2: Import admin credentials
# CM uses these to create the cmadin-<id> account + keytab in FreeIPA
# After this, CM never stores the admin password — only the cmadin keytab
# ---------------------------------------------------------------------------
def import_admin_credentials(api: CmApi):
    step("Import Kerberos admin credentials into CM")
    # Check if cmadin keytab already exists — re-importing would create a second
    # cmadin principal and is usually unnecessary
    try:
        info = api.get("/cm/kerberosInfo")
        if info.get("kerberosEnabled") or info.get("kdcAdminHost"):
            print("  KDC admin credentials already imported — skipping")
            return
    except Exception:
        pass

    resp = api.post(
        "/cm/commands/importAdminCredentials",
        params={
            "username": f"{KRB5_ADMIN_USER}@{REALM}",
            "password": KRB5_ADMIN_PASS,
        }
    )
    cmd_id = resp.get("id")
    print(f"  importAdminCredentials command ID: {cmd_id}")
    api.wait_for_command(cmd_id, poll_interval=10, timeout=300)
    print("  Admin credentials imported — cmadin keytab created in FreeIPA")


# ---------------------------------------------------------------------------
# Step 3: Enable Kerberos on the cluster (configureForKerberos)
# This generates keytabs for all service principals and deploys them
# ---------------------------------------------------------------------------
def configure_for_kerberos(api: CmApi):
    step(f"Enable Kerberos on cluster '{CLUSTER_NAME}'")
    # Check current Kerberos state first — avoid 400 if already configured
    try:
        info = api.get("/cm/kerberosInfo")
        if info.get("kerberosEnabled"):
            print(f"  Kerberos already enabled (realm={info.get('realm')}) — skipping configureForKerberos")
            return
    except Exception as e:
        print(f"  Could not read kerberosInfo: {e}")

    # CM API v58: body must be empty or omitted — "deleteCredentials" field was
    # removed; passing it causes HTTP 400.
    resp = api.post(
        f"/clusters/{CLUSTER_NAME}/commands/configureForKerberos",
        data={}
    )
    cmd_id = resp.get("id")
    print(f"  configureForKerberos command ID: {cmd_id}")
    # This command can take 5-15 minutes — it iterates over every service
    api.wait_for_command(cmd_id, poll_interval=20, timeout=1800)
    print("  configureForKerberos complete")


# ---------------------------------------------------------------------------
# Step 4: Deploy client configs (krb5.conf, HDFS configs, etc.)
# ---------------------------------------------------------------------------
def deploy_client_configs(api: CmApi):
    step("Deploy client configurations to all hosts")
    resp = api.post(f"/clusters/{CLUSTER_NAME}/commands/deployClientConfig")
    cmd_id = resp.get("id")
    api.wait_for_command(cmd_id, poll_interval=15, timeout=600)
    print("  Client configs deployed")


# ---------------------------------------------------------------------------
# Step 5a: Generate missing credentials (service keytabs)
# Must succeed before restarting — services won't start without keytabs
# ---------------------------------------------------------------------------
def generate_credentials(api: CmApi):
    step("Generate Kerberos credentials for all service principals")
    resp = api.post("/cm/commands/generateCredentials")
    cmd_id = resp.get("id")
    print(f"  generateCredentials command ID: {cmd_id}")
    api.wait_for_command(cmd_id, poll_interval=15, timeout=900)
    print("  All service keytabs generated")


# ---------------------------------------------------------------------------
# Step 5b: Restart stale services
# ---------------------------------------------------------------------------
def restart_stale_services(api: CmApi):
    step("Restart all stale services")
    # v58: reDeployClientConf removed — only restartOnlyStaleServices is accepted
    resp = api.post(
        f"/clusters/{CLUSTER_NAME}/commands/restart",
        data={"restartOnlyStaleServices": True}
    )
    cmd_id = resp.get("id")
    print(f"  Restart command ID: {cmd_id}")
    api.wait_for_command(cmd_id, poll_interval=30, timeout=2400)
    print("  All services restarted")


# ---------------------------------------------------------------------------
# Step 6: Verify Kerberos is enabled
# ---------------------------------------------------------------------------
def verify_kerberos(api: CmApi):
    step("Verify Kerberos status")
    info = api.get("/cm/kerberosInfo")
    print(f"  kerberosEnabled:    {info.get('kerberosEnabled')}")
    print(f"  kdcType:            {info.get('kdcType')}")
    print(f"  realm:              {info.get('realm')}")
    print(f"  managingKrb5Conf:   {info.get('managingKrb5Conf')}")

    if not info.get("kerberosEnabled"):
        print("  WARNING: Kerberos does not appear to be enabled yet. Check CM logs.")
    else:
        print("  Kerberos is ENABLED on the cluster")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def write_ipa_admin_pass():
    """Store IPA admin password for gen_credentials.sh (runs as cloudera-scm)."""
    import pwd, subprocess
    pass_file = "/etc/cloudera/.ipa_admin_pass"
    os.makedirs("/etc/cloudera", exist_ok=True)
    with open(pass_file, "w") as f:
        f.write(IPA_ADMIN_PASS)
    os.chmod(pass_file, 0o600)
    # CM scripts run as cloudera-scm — must be able to read this file
    try:
        cm_uid = pwd.getpwnam("cloudera-scm").pw_uid
        os.chown(pass_file, cm_uid, -1)
        print(f"  Wrote IPA admin password to {pass_file} (owner=cloudera-scm mode=600)")
    except KeyError:
        print(f"  Wrote IPA admin password to {pass_file} (cloudera-scm user not found — chown manually if needed)")


def main():
    step("0. Writing IPA admin password for service principal keytab generation")
    write_ipa_admin_pass()

    api = CmApi(CM_HOST, CM_PORT, CM_ADMIN_USER, CM_ADMIN_PASS)

    configure_cm_kerberos(api)
    import_admin_credentials(api)
    configure_for_kerberos(api)
    deploy_client_configs(api)
    generate_credentials(api)
    restart_stale_services(api)
    verify_kerberos(api)

    print("\n" + "="*60)
    print("[DONE] Kerberos authentication is enabled on the cluster.")
    print(f"  Realm:       {REALM}")
    print(f"  KDC:         {IPA_HOST}")
    print(f"  FreeIPA UI:  https://{IPA_HOST}/ipa/ui")
    print(f"  CM UI:       http://{CM_HOST}:{CM_PORT}")
    print()
    print("Next steps:")
    print("  1. Create user principals: ipa user-add <user> && ipa passwd <user>")
    print("  2. Create HDFS home dirs: sudo -u hdfs hadoop fs -mkdir /user/<user>")
    print("  3. kinit <user> to test Kerberos authentication")
    print("  4. Configure Ranger policies for authorization")


if __name__ == "__main__":
    main()
