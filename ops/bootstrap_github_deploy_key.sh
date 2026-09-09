#!/usr/bin/env bash
# Bootstrap and verify one repository-scoped, read-only GitHub deploy key.
# The private key is generated on this host and is never printed or uploaded.
set -Eeuo pipefail
IFS=$'\n\t'
umask 077
export LC_ALL=C

EXPECTED_REPOSITORY="appolon1908-hue/N8N"
REPOSITORY="${REPOSITORY:-${EXPECTED_REPOSITORY}}"
HOST_ALIAS="${HOST_ALIAS:-github-n8n-readonly}"
SSH_DIRECTORY="${SSH_DIRECTORY:-${HOME}/.ssh}"
KEY_PATH="${KEY_PATH:-${SSH_DIRECTORY}/n8n_readonly_deploy_ed25519}"
PUBLIC_KEY_PATH="${KEY_PATH}.pub"
CONFIG_DIRECTORY="${SSH_DIRECTORY}/config.d"
CONFIG_PATH="${CONFIG_DIRECTORY}/n8n-readonly.conf"
MAIN_CONFIG_PATH="${SSH_DIRECTORY}/config"
KNOWN_HOSTS_PATH="${SSH_DIRECTORY}/known_hosts.github-n8n"
EVIDENCE_PATH="${EVIDENCE_PATH:-${SSH_DIRECTORY}/n8n-readonly-deploy-key.evidence.json}"
EXPECTED_GITHUB_ED25519_FINGERPRINT="SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU"
API_VERSION="2026-03-10"

fail() {
  printf 'ERROR=%s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

for command_name in awk cut date gh git grep hostname id install jq mktemp sort ssh ssh-keygen ssh-keyscan stat tr; do
  require_command "$command_name"
done

[[ "$REPOSITORY" == "$EXPECTED_REPOSITORY" ]] \
  || fail "this bootstrap is repository-scoped to ${EXPECTED_REPOSITORY}"
[[ "$HOST_ALIAS" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]] \
  || fail "HOST_ALIAS contains unsupported characters"
for absolute_path in "$SSH_DIRECTORY" "$KEY_PATH" "$CONFIG_DIRECTORY" "$CONFIG_PATH" \
  "$MAIN_CONFIG_PATH" "$KNOWN_HOSTS_PATH" "$EVIDENCE_PATH"; do
  [[ "$absolute_path" = /* ]] || fail "all managed paths must be absolute: $absolute_path"
  [[ "$absolute_path" != *[[:space:]]* ]] || fail "managed paths may not contain whitespace: $absolute_path"
done

printf 'TARGET_REPOSITORY=%s\n' "$REPOSITORY"
printf 'TARGET_HOSTNAME=%s\n' "$(hostname -f 2>/dev/null || hostname)"
printf 'TARGET_USER=%s\n' "$(id -un)"
printf 'LIVE_APPLICATION_DEPLOYMENT=NO\n'
printf 'WORKFLOW_IMPORT=NO\n'
printf 'SERVICE_RESTART=NO\n'

for managed_directory in "$SSH_DIRECTORY" "$CONFIG_DIRECTORY"; do
  [[ ! -L "$managed_directory" ]] || fail "refusing to use symbolic-link directory: $managed_directory"
done
install -d -m 0700 "$SSH_DIRECTORY" "$CONFIG_DIRECTORY"
for protected_path in "$KEY_PATH" "$PUBLIC_KEY_PATH" "$CONFIG_PATH" "$MAIN_CONFIG_PATH" \
  "$KNOWN_HOSTS_PATH" "$EVIDENCE_PATH"; do
  [[ ! -L "$protected_path" ]] || fail "refusing to use symbolic link: $protected_path"
done

if [[ -e "$KEY_PATH" ]]; then
  [[ -f "$KEY_PATH" ]] || fail "existing private-key path is not a regular file"
  if [[ ! -e "$PUBLIC_KEY_PATH" ]]; then
    ssh-keygen -y -f "$KEY_PATH" >"$PUBLIC_KEY_PATH"
  fi
else
  [[ ! -e "$PUBLIC_KEY_PATH" ]] || fail "public key exists without its private key"
  ssh-keygen \
    -q \
    -t ed25519 \
    -N '' \
    -C "deploy:${REPOSITORY}@$(hostname -f 2>/dev/null || hostname)" \
    -f "$KEY_PATH"
fi

[[ -f "$PUBLIC_KEY_PATH" ]] || fail "public-key file is missing"
chmod 0600 "$KEY_PATH"
chmod 0644 "$PUBLIC_KEY_PATH"
PRIVATE_KEY_MODE="$(stat -c '%a' "$KEY_PATH")"
PUBLIC_KEY_MODE="$(stat -c '%a' "$PUBLIC_KEY_PATH")"
[[ "$PRIVATE_KEY_MODE" == "600" ]] || fail "private-key mode is ${PRIVATE_KEY_MODE}, expected 600"
[[ "$PUBLIC_KEY_MODE" == "644" ]] || fail "public-key mode is ${PUBLIC_KEY_MODE}, expected 644"

PRIVATE_PUBLIC_MATERIAL="$(ssh-keygen -y -f "$KEY_PATH" | awk 'NF >= 2 {print $1 " " $2; exit}')"
FILE_PUBLIC_MATERIAL="$(awk 'NF >= 2 {print $1 " " $2; exit}' "$PUBLIC_KEY_PATH")"
[[ -n "$PRIVATE_PUBLIC_MATERIAL" && "$PRIVATE_PUBLIC_MATERIAL" == "$FILE_PUBLIC_MATERIAL" ]] \
  || fail "private and public deploy-key files do not match"
[[ "$FILE_PUBLIC_MATERIAL" == ssh-ed25519\ * ]] || fail "deploy key must be ED25519"

PUBLIC_KEY="$(tr -d '\r\n' <"$PUBLIC_KEY_PATH")"
[[ "$PUBLIC_KEY" == ssh-ed25519\ * ]] || fail "public key is not a single-line ED25519 key"
KEY_FINGERPRINT="$(ssh-keygen -lf "$PUBLIC_KEY_PATH" -E sha256 | awk '{print $2}')"
[[ "$KEY_FINGERPRINT" == SHA256:* ]] || fail "unable to calculate deploy-key fingerprint"

SCAN_PATH="$(mktemp "${SSH_DIRECTORY}/github-host-key.XXXXXX")"
KEY_ROWS_PATH="$(mktemp "${SSH_DIRECTORY}/github-deploy-keys.ndjson.XXXXXX")"
KEY_LIST_PATH="$(mktemp "${SSH_DIRECTORY}/github-deploy-keys.json.XXXXXX")"
API_RESPONSE_PATH="$(mktemp "${SSH_DIRECTORY}/github-api-response.XXXXXX")"
EFFECTIVE_CONFIG_PATH="$(mktemp "${SSH_DIRECTORY}/effective-config.XXXXXX")"
EVIDENCE_TMP_PATH="$(mktemp "${SSH_DIRECTORY}/deploy-key-evidence.XXXXXX")"
cleanup() {
  rm -f "$SCAN_PATH" "$KEY_ROWS_PATH" "$KEY_LIST_PATH" "$API_RESPONSE_PATH" \
    "$EFFECTIVE_CONFIG_PATH" "$EVIDENCE_TMP_PATH"
}
trap cleanup EXIT

GITHUB_HOST="github.com"
GITHUB_PORT="22"
if ! ssh-keyscan -T 10 -t ed25519 github.com >"$SCAN_PATH" 2>/dev/null; then
  GITHUB_HOST="ssh.github.com"
  GITHUB_PORT="443"
  ssh-keyscan -T 10 -p 443 -t ed25519 ssh.github.com >"$SCAN_PATH" 2>/dev/null \
    || fail "unable to obtain GitHub's ED25519 host key on ports 22 or 443"
fi
[[ -s "$SCAN_PATH" ]] || fail "GitHub host-key scan returned no data"

SCANNED_FINGERPRINTS="$(ssh-keygen -lf "$SCAN_PATH" -E sha256 | awk '{print $2}' | sort -u)"
[[ "$SCANNED_FINGERPRINTS" == "$EXPECTED_GITHUB_ED25519_FINGERPRINT" ]] \
  || fail "GitHub host-key fingerprint mismatch"
install -m 0600 "$SCAN_PATH" "$KNOWN_HOSTS_PATH"
[[ "$(stat -c '%a' "$KNOWN_HOSTS_PATH")" == "600" ]] \
  || fail "dedicated known-hosts file mode is not 600"

cat >"$CONFIG_PATH" <<EOF_CONFIG
Host ${HOST_ALIAS}
  HostName ${GITHUB_HOST}
  Port ${GITHUB_PORT}
  User git
  IdentityFile ${KEY_PATH}
  IdentitiesOnly yes
  IdentityAgent none
  AddKeysToAgent no
  PreferredAuthentications publickey
  PasswordAuthentication no
  KbdInteractiveAuthentication no
  BatchMode yes
  StrictHostKeyChecking yes
  UserKnownHostsFile ${KNOWN_HOSTS_PATH}
  ForwardAgent no
EOF_CONFIG
chmod 0600 "$CONFIG_PATH"

INCLUDE_LINE="Include ${CONFIG_DIRECTORY}/*"
touch "$MAIN_CONFIG_PATH"
chmod 0600 "$MAIN_CONFIG_PATH"
UPDATED_CONFIG="$(mktemp "${SSH_DIRECTORY}/config.XXXXXX")"
{
  printf '%s\n\n' "$INCLUDE_LINE"
  grep -Fvx "$INCLUDE_LINE" "$MAIN_CONFIG_PATH" || true
} >"$UPDATED_CONFIG"
chmod 0600 "$UPDATED_CONFIG"
mv -f "$UPDATED_CONFIG" "$MAIN_CONFIG_PATH"

ssh -F "$MAIN_CONFIG_PATH" -G "$HOST_ALIAS" >"$EFFECTIVE_CONFIG_PATH" \
  || fail "generated SSH configuration is invalid"
grep -Eq '^identitiesonly yes$' "$EFFECTIVE_CONFIG_PATH" \
  || fail "effective SSH configuration does not enforce IdentitiesOnly yes"
grep -Eq '^stricthostkeychecking (yes|true)$' "$EFFECTIVE_CONFIG_PATH" \
  || fail "effective SSH configuration does not enforce strict host-key checking"
grep -Fqx "identityfile ${KEY_PATH}" "$EFFECTIVE_CONFIG_PATH" \
  || fail "effective SSH configuration does not select the repository key"
grep -Fqx "userknownhostsfile ${KNOWN_HOSTS_PATH}" "$EFFECTIVE_CONFIG_PATH" \
  || fail "effective SSH configuration does not select the dedicated known-hosts file"

gh auth status --hostname github.com >/dev/null 2>&1 \
  || fail "GitHub CLI is not authenticated; use a one-time GH_TOKEN with repository Administration write permission"

gh api \
  --paginate \
  -H 'Accept: application/vnd.github+json' \
  -H "X-GitHub-Api-Version: ${API_VERSION}" \
  "repos/${REPOSITORY}/keys?per_page=100" \
  --jq '.[]' >"$KEY_ROWS_PATH"
if [[ -s "$KEY_ROWS_PATH" ]]; then
  jq -s '.' "$KEY_ROWS_PATH" >"$KEY_LIST_PATH"
else
  printf '[]\n' >"$KEY_LIST_PATH"
fi

MATCHES="$(
  jq -c --arg material "$FILE_PUBLIC_MATERIAL" '
    [
      .[]
      | select(.key | type == "string")
      | select((.key | split(" ") | .[0:2] | join(" ")) == $material)
    ]
  ' "$KEY_LIST_PATH"
)"
MATCH_COUNT="$(jq 'length' <<<"$MATCHES")"
[[ "$MATCH_COUNT" -le 1 ]] || fail "the same public key is registered more than once"

if [[ "$MATCH_COUNT" -eq 1 ]]; then
  DEPLOY_KEY_ID="$(jq -r '.[0].id' <<<"$MATCHES")"
  [[ "$(jq -r '.[0].read_only' <<<"$MATCHES")" == "true" ]] \
    || fail "existing GitHub deploy key has write access"
  [[ "$(jq -r '.[0] | if has("enabled") then .enabled else true end' <<<"$MATCHES")" == "true" ]] \
    || fail "existing GitHub deploy key is disabled"
  printf 'GITHUB_DEPLOY_KEY=ALREADY_PRESENT_READ_ONLY\n'
else
  FINGERPRINT_SUFFIX="$(printf '%s' "${KEY_FINGERPRINT#SHA256:}" | tr '/+' '_-' | cut -c1-16)"
  KEY_TITLE="N8N read-only deploy key - $(hostname -s) - ${FINGERPRINT_SUFFIX}"
  gh api \
    --method POST \
    -H 'Accept: application/vnd.github+json' \
    -H "X-GitHub-Api-Version: ${API_VERSION}" \
    "repos/${REPOSITORY}/keys" \
    -f "title=${KEY_TITLE}" \
    -f "key=${PUBLIC_KEY}" \
    -F read_only=true >"$API_RESPONSE_PATH"
  [[ "$(jq -r '.read_only' "$API_RESPONSE_PATH")" == "true" ]] \
    || fail "GitHub did not record the deploy key as read-only"
  DEPLOY_KEY_ID="$(jq -r '.id' "$API_RESPONSE_PATH")"
  printf 'GITHUB_DEPLOY_KEY=CREATED_READ_ONLY\n'
fi
[[ "$DEPLOY_KEY_ID" =~ ^[0-9]+$ ]] || fail "GitHub deploy-key ID is invalid"

gh api \
  -H 'Accept: application/vnd.github+json' \
  -H "X-GitHub-Api-Version: ${API_VERSION}" \
  "repos/${REPOSITORY}/keys/${DEPLOY_KEY_ID}" >"$API_RESPONSE_PATH"
[[ "$(jq -r '.read_only' "$API_RESPONSE_PATH")" == "true" ]] \
  || fail "GitHub deploy-key read-only readback failed"
[[ "$(jq -r 'if has("enabled") then .enabled else true end' "$API_RESPONSE_PATH")" == "true" ]] \
  || fail "GitHub deploy key is disabled"
READBACK_MATERIAL="$(
  jq -r '.key' "$API_RESPONSE_PATH" | awk 'NF >= 2 {print $1 " " $2; exit}'
)"
[[ "$READBACK_MATERIAL" == "$FILE_PUBLIC_MATERIAL" ]] \
  || fail "GitHub deploy-key public-material readback differs"

set +e
SSH_RESULT="$(ssh -F "$MAIN_CONFIG_PATH" -o ConnectTimeout=15 -T "$HOST_ALIAS" 2>&1)"
SSH_STATUS=$?
set -e
[[ "$SSH_STATUS" -eq 1 ]] \
  || fail "GitHub SSH test returned unexpected status ${SSH_STATUS}"
grep -Fq "Hi ${REPOSITORY}!" <<<"$SSH_RESULT" \
  || fail "GitHub SSH authentication did not identify ${REPOSITORY}"
grep -Fq "successfully authenticated" <<<"$SSH_RESULT" \
  || fail "GitHub SSH authentication did not return the expected success message"

printf -v GIT_SSH_COMMAND_VALUE 'ssh -F %q -o BatchMode=yes -o ConnectTimeout=15' "$MAIN_CONFIG_PATH"
REMOTE_HEAD_LINE="$(
  GIT_SSH_COMMAND="$GIT_SSH_COMMAND_VALUE" \
    git ls-remote "git@${HOST_ALIAS}:${REPOSITORY}.git" HEAD
)"
REMOTE_HEAD_SHA="${REMOTE_HEAD_LINE%%[[:space:]]*}"
[[ "$REMOTE_HEAD_SHA" =~ ^[0-9a-f]{40}$ ]] \
  || fail "git ls-remote did not return a valid HEAD SHA"

AUTH_MODE="gh-cli-stored"
if [[ -n "${GH_TOKEN:-}" ]]; then
  AUTH_MODE="GH_TOKEN_environment"
fi
jq -n \
  --arg schema_version "1.0" \
  --arg status "PASS" \
  --arg repository "$REPOSITORY" \
  --arg host_alias "$HOST_ALIAS" \
  --arg github_host "$GITHUB_HOST" \
  --arg github_port "$GITHUB_PORT" \
  --arg key_fingerprint "$KEY_FINGERPRINT" \
  --arg private_key_mode "0600" \
  --arg public_key_mode "0644" \
  --arg deploy_key_id "$DEPLOY_KEY_ID" \
  --arg remote_head_sha "$REMOTE_HEAD_SHA" \
  --arg api_auth_mode "$AUTH_MODE" \
  --arg verified_at "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
  '{
    schema_version: $schema_version,
    status: $status,
    repository: $repository,
    host_alias: $host_alias,
    github_host: $github_host,
    github_port: ($github_port | tonumber),
    key_fingerprint: $key_fingerprint,
    private_key_mode: $private_key_mode,
    public_key_mode: $public_key_mode,
    deploy_key_id: ($deploy_key_id | tonumber),
    deploy_key_read_only: true,
    identities_only: true,
    strict_host_key_checking: true,
    ssh_authenticated_repository: $repository,
    git_ls_remote: "PASS",
    remote_head_sha: $remote_head_sha,
    api_auth_mode: $api_auth_mode,
    private_key_exported: false,
    application_deployed: false,
    service_restarted: false,
    workflow_imported: false,
    live_capability_activated: false,
    verified_at: $verified_at
  }' >"$EVIDENCE_TMP_PATH"
install -m 0600 "$EVIDENCE_TMP_PATH" "$EVIDENCE_PATH"

printf 'SSH_DEPLOY_KEY_BOOTSTRAP=PASS\n'
printf 'DEPLOY_KEY_MODE=READ_ONLY\n'
printf 'SSH_AUTH_IDENTITY=%s\n' "$REPOSITORY"
printf 'DEPLOY_KEY_FINGERPRINT=%s\n' "$KEY_FINGERPRINT"
printf 'PRIVATE_KEY_MODE=0600\n'
printf 'PUBLIC_KEY_MODE=0644\n'
printf 'IDENTITIES_ONLY=yes\n'
printf 'STRICT_HOST_KEY_CHECKING=yes\n'
printf 'SSH_HOST_ALIAS=%s\n' "$HOST_ALIAS"
printf 'GIT_REMOTE_URL=git@%s:%s.git\n' "$HOST_ALIAS" "$REPOSITORY"
printf 'REMOTE_HEAD_SHA=%s\n' "$REMOTE_HEAD_SHA"
printf 'EVIDENCE_PATH=%s\n' "$EVIDENCE_PATH"
printf 'PRIVATE_KEY_EXPORTED=NO\n'
printf 'LIVE_APPLICATION_DEPLOYMENT=NO\n'
printf 'WORKFLOW_IMPORT=NO\n'
printf 'SERVICE_RESTART=NO\n'
printf 'LIVE_CAPABILITY_ACTIVATION=NO\n'
