#!/usr/bin/env python3.11
"""
08_autotls.py — Enable Auto-TLS on CDP cluster using CM-managed CA

Process:
  1. POST /cm/commands/generateCmca  — CM generates its own CA + host certificates
  2. Restart CM server               — switches to HTTPS on port 7183
  3. POST /clusters/{name}/commands/configureAutoTlsServices
                                     — updates all service configs for TLS
  4. Restart stale services

After Auto-TLS:
  - CM UI: https://{host}:7183   (HTTP 7180 redirects)
  - All API calls must use HTTPS and verify=False (self-signed CM CA)
  - 06_kerberos_enable.py is already TLS-compatible (uses HTTPS port from env)

Reference:
  https://docs.cloudera.com/cdp-private-cloud-base/7.3.1/security-encrypting-data-in-transit/topics/cm-security-auto-tls.html

Run: python3.11 08_autotls.py
"""
import os, sys, time, subprocess, requests, urllib3

# Suppress self-signed cert warnings (expected after Auto-TLS)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CM_HOST       = os.environ["CM_HOST"]
CM_PORT_HTTP  = os.environ.get("CM_PORT", "7180")
CM_PORT_HTTPS = "7183"
CM_ADMIN_USER = os.environ.get("CM_ADMIN_USER", "admin")
CM_ADMIN_PASS = os.environ.get("CM_ADMIN_PASS", "admin")
CLUSTER_NAME  = os.environ.get("CLUSTER_NAME", "CDP-Base-732")
NODE_HOST     = os.environ["NODE_HOST"]

# SSH credentials for generateCmca (CM SSHes to each host to install certs)
SSH_USER = os.environ.get("DEPLOY_USER", "root")
SSH_PASS = os.environ.get("SSH_PASSWORD", "")   # set SSH_PASSWORD env var before running

CERT_LOCATION = "/opt/cloudera/security/pki"

def get_api(use_https=False):
    """Return (base_url, auth, verify) tuple for the appropriate protocol."""
    protocol = "https" if use_https else "http"
    port = CM_PORT_HTTPS if use_https else CM_PORT_HTTP
    base_url = f"{protocol}://{CM_HOST}:{port}"
    r = requests.get(f"{base_url}/api/version",
                     auth=(CM_ADMIN_USER, CM_ADMIN_PASS),
                     verify=False, timeout=20)
    r.raise_for_status()
    api_ver = r.text.strip().strip('"')
    return f"{base_url}/api/{api_ver}", (CM_ADMIN_USER, CM_ADMIN_PASS), False

def wait_cmd(base, auth, cmd_id, verify=False, interval=20, timeout=600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{base}/commands/{cmd_id}",
                         auth=auth, verify=verify, timeout=15)
        c = r.json()
        if not c.get("active", True):
            ok = c.get("success", False)
            print(f"  {'OK' if ok else 'FAIL'}: {c.get('resultMessage','')[:200]}")
            return ok
        print(f"  ... {c.get('resultMessage','running')[:80]}")
        time.sleep(interval)
    return False

def step(msg):
    print(f"\n{'='*60}\n[Auto-TLS] {msg}\n{'='*60}")


def main():
    if not SSH_PASS:
        print("ERROR: Set SSH_PASSWORD environment variable before running.")
        print("  export SSH_PASSWORD='root-ssh-password'")
        sys.exit(1)

    # ── Step 1: Generate CM CA (CM-managed, no custom certs) ─────────────
    step("1. Generating CM CA and host certificates")
    base, auth, verify = get_api(use_https=False)
    print(f"  CM API: {base}")
    print(f"  Cert location on hosts: {CERT_LOCATION}")

    payload = {
        "location":            CERT_LOCATION,
        "customCA":            False,        # CM generates its own CA
        "interpretAsFilenames": False,
        "configureAllServices": True,        # auto-configure CM + services
        "sshPort":             22,
        "userName":            SSH_USER,
        "password":            SSH_PASS,
    }

    r = requests.post(f"{base}/cm/commands/generateCmca",
                      auth=auth, json=payload, verify=verify, timeout=60)
    print(f"  generateCmca HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"  Response: {r.text[:400]}")
        sys.exit(1)

    cmd_id = r.json().get("id")
    print(f"  Command ID: {cmd_id}  (certificate generation takes 2-5 min)")
    ok = wait_cmd(base, auth, cmd_id, verify=verify, interval=20, timeout=600)
    if not ok:
        print("  generateCmca FAILED. Check CM server log.")
        sys.exit(1)
    print("  CM CA generated and certificates installed on all hosts")

    # ── Step 2: Restart CM server (switches to HTTPS) ────────────────────
    step("2. Restarting Cloudera Manager server (switching to HTTPS)")
    print("  Restarting cloudera-scm-server...")
    subprocess.run(["systemctl", "restart", "cloudera-scm-server"], check=True)
    subprocess.run(["systemctl", "restart", "cloudera-scm-agent"],  check=True)

    # Wait for CM to come back on HTTPS
    print("  Waiting for CM to restart on HTTPS (port 7183, up to 3 min)...")
    for i in range(18):
        time.sleep(10)
        try:
            r2 = requests.get(f"https://{CM_HOST}:{CM_PORT_HTTPS}/api/version",
                              auth=(CM_ADMIN_USER, CM_ADMIN_PASS),
                              verify=False, timeout=10)
            if r2.status_code in (200, 401):
                print(f"  CM HTTPS is up (HTTP {r2.status_code})")
                break
        except Exception:
            pass
        print(f"  [{i*10}s] Waiting for HTTPS...")
    else:
        print("  WARNING: CM HTTPS did not come up in 3 min. Check logs.")

    # ── Step 3: Configure cluster services for TLS ────────────────────────
    step("3. Configuring cluster services for Auto-TLS")
    base_https, auth_https, verify_https = get_api(use_https=True)
    print(f"  CM HTTPS API: {base_https}")

    r3 = requests.post(
        f"{base_https}/clusters/{CLUSTER_NAME}/commands/configureAutoTlsServices",
        auth=auth_https, verify=verify_https, timeout=30
    )
    print(f"  configureAutoTlsServices HTTP {r3.status_code}")
    if r3.status_code == 200:
        cmd_id3 = r3.json().get("id")
        wait_cmd(base_https, auth_https, cmd_id3, verify=verify_https,
                 interval=15, timeout=600)
    else:
        print(f"  Response: {r3.text[:200]}")

    # ── Step 4: Deploy client configs and restart stale services ──────────
    step("4. Deploying client configs and restarting stale services")
    r4 = requests.post(
        f"{base_https}/clusters/{CLUSTER_NAME}/commands/deployClientConfig",
        auth=auth_https, verify=verify_https, timeout=30
    )
    if r4.status_code == 200:
        wait_cmd(base_https, auth_https, r4.json().get("id"), verify=verify_https)

    # v58: only 'restartOnlyStaleServices' is accepted — no reDeployClientConf field
    r5 = requests.post(
        f"{base_https}/clusters/{CLUSTER_NAME}/commands/restart",
        auth=auth_https, verify=verify_https, timeout=30,
        json={"restartOnlyStaleServices": True}
    )
    print(f"  Restart stale services HTTP {r5.status_code}")
    if r5.status_code == 200:
        cmd_id5 = r5.json().get("id")
        print(f"  Restart command ID: {cmd_id5}  (may take 10-20 min for 20 services)")
        wait_cmd(base_https, auth_https, cmd_id5, verify=verify_https,
                 interval=30, timeout=2400)

    # ── Verify ────────────────────────────────────────────────────────────
    step("5. Verification")
    r6 = requests.get(f"{base_https}/cm/config",
                      auth=auth_https, verify=verify_https, timeout=10)
    tls_items = {i["name"]: i.get("value") for i in r6.json().get("items", [])
                 if "TLS" in i.get("name", "").upper() or "HTTPS" in i.get("name", "").upper()}
    print("  CM TLS config:")
    for k, v in tls_items.items():
        print(f"    {k} = {v}")

    print()
    print("[DONE] Auto-TLS enabled.")
    print(f"  CM HTTPS UI: https://{CM_HOST}:{CM_PORT_HTTPS}")
    print(f"  CM HTTP UI:  http://{CM_HOST}:{CM_PORT_HTTP}  (redirects to HTTPS)")
    print()
    print("  IMPORTANT: All subsequent API calls must use HTTPS port 7183")
    print("  Update CM_PORT=7183 and use verify=False in 06_kerberos_enable.py")
    print()
    print("  CA certificate location:")
    print(f"    {CERT_LOCATION}/ca.crt  (on each host)")
    print("  To trust the CM CA on your laptop:")
    print(f"    scp root@{CM_HOST}:{CERT_LOCATION}/ca.crt ./cm-ca.crt")
    print(f"    # Then use --cacert cm-ca.crt in curl or add to browser trust store")


if __name__ == "__main__":
    main()
