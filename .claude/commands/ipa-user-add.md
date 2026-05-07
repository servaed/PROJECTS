# /ipa-user-add

Create a new Kerberos user in FreeIPA and set up their HDFS home directory. Use to add cluster users after Kerberos is enabled.

## Arguments
`$ARGUMENTS` — username. Example: `/ipa-user-add edward`

## Run

```bash
USERNAME="$ARGUMENTS"
REALM="SE-INDO.LAB"
PASS="Cl0ud3ra@Base732#SE"

if [ -z "$USERNAME" ]; then
  echo "Usage: /ipa-user-add <username>"
  exit 1
fi

ssh root@34.26.137.154 "bash -s" << SCRIPT
# Authenticate as admin
echo "${PASS}" | kinit admin@${REALM}

# Create IPA user
ipa user-add ${USERNAME} \
  --first="${USERNAME}" \
  --last="User" \
  --password-expiration=20991231000000Z 2>&1

# Set password
echo -e "${PASS}\n${PASS}" | ipa passwd ${USERNAME} 2>&1

# kinit as the new user to initialize password
echo "${PASS}" | kinit ${USERNAME}@${REALM} 2>&1
kdestroy 2>/dev/null

# Create HDFS home directory
echo "${PASS}" | kinit admin@${REALM}
sudo -u hdfs hdfs dfs -mkdir -p /user/${USERNAME} 2>&1
sudo -u hdfs hdfs dfs -chown ${USERNAME} /user/${USERNAME} 2>&1
hdfs dfs -ls /user/ 2>&1 | grep ${USERNAME}

echo ""
echo "User ${USERNAME} created successfully."
echo "Password: ${PASS}"
echo "HDFS home: /user/${USERNAME}"
SCRIPT
```

Report success or any errors (user may already exist, HDFS service might need kinit).
