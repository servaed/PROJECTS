#!/usr/bin/env bash
# =============================================================================
# 00_system_prep.sh — RHEL 9 system prerequisites (run on EVERY node)
# Usage: bash 00_system_prep.sh <this-node-fqdn>
#        Called by install.sh for each host via SSH
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config.env"

THIS_HOST="${1:?Usage: $0 <fqdn>}"
log() { echo "[$(date '+%H:%M:%S')] [system_prep] $*"; }

# --- 1. Hostname ---
log "Setting hostname to ${THIS_HOST}"
hostnamectl set-hostname "${THIS_HOST}"

# --- 2. /etc/hosts — add all cluster nodes ---
log "Configuring /etc/hosts"
# Remove any stale entries for cluster nodes then append fresh ones
for host in ${ALL_HOSTS}; do
    sed -i "/ ${host}/d" /etc/hosts
done
# Caller must export ALL_HOST_IPS as "ip1:host1 ip2:host2 ..." in config.env
# If not set, skip — DNS-only environments work with FreeIPA DNS
if [[ -n "${ALL_HOST_IPS:-}" ]]; then
    # Remove ANY existing lines for the same IP (handles GCP's auto-added entries)
    for entry in ${ALL_HOST_IPS}; do
        ip="${entry%%:*}"
        host="${entry##*:}"
        sed -i "/^${ip}/d" /etc/hosts
    done
    # Insert our mappings at the top so they win over GCP's entries
    HOSTS_BLOCK=""
    for entry in ${ALL_HOST_IPS}; do
        ip="${entry%%:*}"
        host="${entry##*:}"
        short="${host%%.*}"
        HOSTS_BLOCK="${ip}  ${host} ${short}\n${HOSTS_BLOCK}"
    done
    sed -i "1a ${HOSTS_BLOCK}" /etc/hosts
fi

# Remove myhostname from nsswitch.conf — prevents IPv6 link-local from
# winning over /etc/hosts entries, which breaks ipa-server-install hostname check
sed -i 's/^hosts:.*/hosts:      files dns/' /etc/nsswitch.conf

# --- 3. Chrony NTP (required before Kerberos) ---
log "Configuring chrony NTP → ${NTP_SERVER}"
dnf install -y chrony
cat > /etc/chrony.conf <<EOF
server ${NTP_SERVER} iburst
driftfile /var/lib/chrony/drift
makestep 1.0 3
rtcsync
logdir /var/log/chrony
EOF
systemctl enable --now chronyd
chronyc makestep
log "NTP sync: $(chronyc tracking | grep 'System time')"

# --- 4. SELinux — permissive (re-enable with targeted policy post-install) ---
log "Setting SELinux to permissive"
setenforce 0 || true
sed -i 's/^SELINUX=.*/SELINUX=permissive/' /etc/selinux/config

# --- 5. Disable swap (YARN and Impala require this) ---
log "Disabling swap"
swapoff -a
sed -i '/\bswap\b/d' /etc/fstab

# --- 6. Kernel tuning ---
log "Applying kernel parameters"
cat > /etc/sysctl.d/99-cloudera.conf <<EOF
vm.swappiness = 10
vm.dirty_ratio = 20
vm.dirty_background_ratio = 5
net.ipv4.tcp_max_syn_backlog = 65536
net.core.somaxconn = 65536
net.core.netdev_max_backlog = 65536
EOF
sysctl --system -q

# --- 7. Transparent Huge Pages — must be disabled for YARN/Impala ---
log "Disabling Transparent Huge Pages"
echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo never > /sys/kernel/mm/transparent_hugepage/defrag
cat > /etc/systemd/system/disable-thp.service <<'EOF'
[Unit]
Description=Disable Transparent Huge Pages
DefaultDependencies=no
After=sysinit.target local-fs.target
Before=basic.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/enabled && echo never > /sys/kernel/mm/transparent_hugepage/defrag'
RemainAfterExit=yes

[Install]
WantedBy=basic.target
EOF
systemctl daemon-reload
systemctl enable disable-thp

# --- 8. Open file limits ---
log "Configuring file descriptor limits"
cat > /etc/security/limits.d/99-cloudera.conf <<EOF
*    soft nofile 65536
*    hard nofile 65536
*    soft nproc  65536
*    hard nproc  65536
hdfs soft nofile 131072
hdfs hard nofile 131072
hbase soft nofile 131072
hbase hard nofile 131072
impala soft nofile 131072
impala hard nofile 131072
EOF

# --- 9. Java 17 (ONLY supported JDK for CM 7.13.2 + Runtime 7.3.2; JDK 11 removed) ---
log "Installing OpenJDK 17"
dnf install -y java-17-openjdk-headless java-17-openjdk-devel
alternatives --set java "$(alternatives --display java 2>/dev/null | grep java-17 | head -1 | awk '{print $1}')" || true
java -version

# --- 10. Python 3.11 (required by CM 7.13.2; Python 3.8/3.9/3.10 discontinued) ---
# Install as a side-by-side binary — do NOT override /usr/bin/python3 because
# firewall-cmd on RHEL 9 depends on python3-gi which is only for system Python 3.9
log "Installing Python 3.11 (side-by-side, not overriding system python3)"
dnf install -y python3.11 python3.11-pip
# Verify it's available as python3.11 (CM API scripts call python3.11 directly)
python3.11 --version
python3.11 -m pip install --quiet requests

# --- 10a. psycopg2-binary — required by Hue to connect to PostgreSQL ---
# Install in system python3.11 (Hue uses the system Python for its Django DB check)
log "Installing psycopg2-binary for Hue PostgreSQL support"
python3.11 -m pip install --quiet psycopg2-binary

# --- 11. Kerberos client packages (required on all nodes before cluster Kerberization) ---
log "Installing Kerberos client packages"
dnf install -y krb5-workstation krb5-libs openldap-clients

# --- 12. Common utilities ---
log "Installing common utilities"
dnf install -y wget curl vim net-tools bind-utils nss-tools nc telnet rsync

# --- 12. Firewall ---
# GCP: disable firewalld — VPC firewall rules handle security at the network level.
# For bare-metal/non-GCP: swap the two blocks below (comment disable, uncomment rules).
log "Firewall: disabling firewalld (GCP deployment — VPC handles network security)"
systemctl stop firewalld 2>/dev/null || true
systemctl disable firewalld 2>/dev/null || true

# --- Uncomment for non-GCP bare-metal deployment ---
# systemctl enable --now firewalld
# for port in 7180 7183 7182 8020 9870 9864 8088 8032 8042 \
#             21000 21050 25000 25010 25020 10000 9083 \
#             2181 2888 3888 16000 16020 8443 6080 8888 18088; do
#     firewall-cmd --permanent --add-port=${port}/tcp
# done
# firewall-cmd --reload

# --- 13. Create CDP data directories ---
log "Creating CDP data directories"
mkdir -p \
    /data/dfs/nn \
    /data/dfs/snn \
    /data/dfs/dn \
    /data/yarn/nm \
    /data/zookeeper \
    /data/impala/impalad \
    /data/hadoop-ozone/datanode/data
chmod 777 /data/dfs/dn /data/yarn/nm /data/impala/impalad /data/hadoop-ozone/datanode/data
log "Data directories created under /data/"

log "System preparation complete on ${THIS_HOST}"
