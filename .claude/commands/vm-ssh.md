# /vm-ssh

Run a command on the CDP VM over SSH and show the output.

## Arguments
`$ARGUMENTS` — shell command to run on the VM. If empty, shows system summary.

## Run

```bash
CMD="${ARGUMENTS}"

if [ -z "$CMD" ]; then
  # Default: system overview
  ssh root@34.26.137.154 '
    echo "=== System ==="
    hostname -f
    uptime
    free -h | grep Mem
    df -h / /data 2>/dev/null | tail -3

    echo ""
    echo "=== Cloudera Services ==="
    systemctl is-active cloudera-scm-server cloudera-scm-agent 2>/dev/null

    echo ""
    echo "=== Kerberos ==="
    klist 2>/dev/null || echo "No TGT"

    echo ""
    echo "=== IPA ==="
    systemctl is-active ipa 2>/dev/null || ipactl status 2>/dev/null | head -5
  '
else
  ssh root@34.26.137.154 "$CMD"
fi
```

Show output verbatim. If the command fails, explain the error.
