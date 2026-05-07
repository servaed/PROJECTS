# /cm-logs

Tail and filter Cloudera Manager server logs. Shows errors, warnings, and credential-related entries.

## Arguments
`$ARGUMENTS` — optional filter keyword (e.g. `kerberos`, `keytab`, `hive`, `ERROR`). Default: last 100 error/warn lines.

## Run

```bash
FILTER="${ARGUMENTS:-ERROR\|WARN\|keytab\|kerberos\|credential}"
ssh root@34.26.137.154 "grep -i \"$FILTER\" /var/log/cloudera-scm-server/cloudera-scm-server.log | tail -80"
```

Also show the last 10 lines regardless of filter (for context):
```bash
ssh root@34.26.137.154 "tail -20 /var/log/cloudera-scm-server/cloudera-scm-server.log"
```

Summarize:
- Any recent failures and their root cause
- Time of last successful command
- Any recurring errors

If `$ARGUMENTS` is `agent`, check the agent log instead:
```bash
ssh root@34.26.137.154 "tail -100 /var/log/cloudera-scm-agent/cloudera-scm-agent.log | grep -i 'ERROR\|WARN\|keytab\|kerberos'"
```
