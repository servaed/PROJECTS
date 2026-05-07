#!/usr/bin/env bash
# =============================================================================
# 03_postgres_setup.sh — Install PostgreSQL 14 and create all CM service databases
# Platform: RHEL 9 | Run on DB_HOST (default: co-located with CM_HOST)
# Note: PostgreSQL 13 support was REMOVED in Cloudera Base 7.3.2
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config.env"

log() { echo "[$(date '+%H:%M:%S')] [postgres_setup] $*"; }

PG_VERSION="14"
PG_DATA="/var/lib/pgsql/${PG_VERSION}/data"
PG_HBA="${PG_DATA}/pg_hba.conf"
PG_CONF="${PG_DATA}/postgresql.conf"

# --- 1. Install PGDG repo and PostgreSQL 14 ---
log "Installing PostgreSQL ${PG_VERSION} from PGDG"
dnf install -y "https://download.postgresql.org/pub/repos/yum/reporpms/EL-9-x86_64/pgdg-redhat-repo-latest.noarch.rpm" 2>/dev/null || true
# Disable the built-in PostgreSQL module to avoid conflicts with PGDG
dnf module disable -y postgresql 2>/dev/null || true
dnf install -y "postgresql${PG_VERSION}-server" "postgresql${PG_VERSION}"

# --- 2. Initialize the database cluster ---
log "Initializing PostgreSQL ${PG_VERSION} data directory"
PGSETUP_INITDB_OPTIONS="--encoding=UTF8 --locale=en_US.UTF-8" \
    "/usr/pgsql-${PG_VERSION}/bin/postgresql-${PG_VERSION}-setup" initdb

# --- 3. Configure postgresql.conf ---
log "Configuring postgresql.conf"
cat >> "${PG_CONF}" <<EOF

# Cloudera Manager tuning
listen_addresses = '*'
max_connections = 500
shared_buffers = 256MB
work_mem = 4MB
maintenance_work_mem = 64MB
wal_level = replica
log_line_prefix = '%m [%p] %u@%d '
log_min_duration_statement = 1000
EOF

# --- 4. Configure pg_hba.conf for md5 password auth ---
# Cloudera scm_prepare_database.sh requires md5 (not peer/ident) for local connections
log "Configuring pg_hba.conf for md5 auth"
cat > "${PG_HBA}" <<EOF
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             postgres                                peer
local   all             all                                     md5
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
host    all             all             0.0.0.0/0               md5
EOF

# --- 5. Enable and start PostgreSQL ---
log "Starting postgresql-${PG_VERSION} service"
systemctl enable --now "postgresql-${PG_VERSION}"

# Open PostgreSQL port — skip on GCP (firewalld disabled, VPC handles it)
# firewall-cmd --permanent --add-port=5432/tcp && firewall-cmd --reload

# --- 6. Set postgres OS user password for psql operations ---
log "Setting postgres OS user password"
echo "postgres:${PG_ADMIN_PASS}" | chpasswd

# Helper to run SQL as postgres
pg_exec() {
    sudo -u postgres "/usr/pgsql-${PG_VERSION}/bin/psql" -c "$1"
}
pg_exec_db() {
    sudo -u postgres "/usr/pgsql-${PG_VERSION}/bin/psql" -d "$1" -c "$2"
}

# Set postgres superuser password
pg_exec "ALTER USER postgres WITH PASSWORD '${PG_ADMIN_PASS}';"

# --- 7. Create all CM service databases and users ---
create_db_user() {
    local db="$1" user="$2" pass="$3"
    log "  Creating user=${user} db=${db}"
    pg_exec "CREATE USER ${user} WITH LOGIN PASSWORD '${pass}';" 2>/dev/null || \
        pg_exec "ALTER USER ${user} WITH PASSWORD '${pass}';"
    pg_exec "CREATE DATABASE ${db} OWNER ${user} ENCODING 'UTF8';" 2>/dev/null || \
        log "  (database ${db} already exists)"
    pg_exec "GRANT ALL PRIVILEGES ON DATABASE ${db} TO ${user};"
    pg_exec_db "${db}" "ALTER SCHEMA public OWNER TO ${user};"
}

log "Creating Cloudera service databases"
create_db_user "${DB_SCM}"   "${USER_SCM}"   "${PASS_SCM}"    # Cloudera Manager SCM
create_db_user "${DB_AMON}"  "${USER_AMON}"  "${PASS_AMON}"   # Activity Monitor
create_db_user "${DB_RMAN}"  "${USER_RMAN}"  "${PASS_RMAN}"   # Reports Manager
create_db_user "${DB_HUE}"   "${USER_HUE}"   "${PASS_HUE}"    # Hue
create_db_user "${DB_HIVE}"  "${USER_HIVE}"  "${PASS_HIVE}"   # Hive Metastore
create_db_user "${DB_OOZIE}" "${USER_OOZIE}" "${PASS_OOZIE}"  # Oozie
create_db_user "${DB_RANGER}" "${USER_RANGER}" "${PASS_RANGER}" # Ranger

# --- 8. Verify all databases exist ---
log "Verifying databases:"
pg_exec "\l" | grep -E "scm|amon|rman|hue|metastore|oozie|ranger"

log "PostgreSQL setup complete"
log "  Version: ${PG_VERSION}"
log "  Data:    ${PG_DATA}"
log "  Port:    5432"
