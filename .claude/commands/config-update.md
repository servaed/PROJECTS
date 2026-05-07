# /config-update

Update a value in `config.env` and sync it to the VM.

## Arguments
`$ARGUMENTS` — `KEY VALUE`. Example: `/config-update NODE_IP 10.240.0.99`

## Run

Read and update the config file:

1. Read `accelerators/cloudera-base-732-kerberos/config.env`
2. Find the line matching `KEY=` and update its value to `VALUE`
3. Show the before/after diff
4. Ask for confirmation, then write the file
5. Sync to VM: `scp accelerators/cloudera-base-732-kerberos/config.env root@34.26.137.154:/opt/cloudera-install/config.env`

## Common keys to update

| Key | Purpose |
|-----|---------|
| `NODE_HOST` | Cluster FQDN (e.g. `cdp.se-indo.lab`) |
| `NODE_IP` | Internal IP (used in /etc/hosts) |
| `MASTER_PASS` | All service passwords |
| `CM_PORT` | `7180` (HTTP) or `7183` (after Auto-TLS) |
| `REALM` | Kerberos realm (e.g. `SE-INDO.LAB`) |
| `IPA_HOST` | FreeIPA server hostname |
| `IPA_ADMIN_PASS` | FreeIPA admin password |
| `PARCEL_REPO` | CDH parcel repository URL |
| `PARCEL_BUILD` | Full parcel build string |

Parse `$ARGUMENTS` as `KEY VALUE` (split on first space). If VALUE contains spaces, preserve them.
