#!/usr/bin/env bash
set -euo pipefail

RUNNER_PATH="/usr/local/bin/quaero-reconcile-runner.sh"
SERVICE_PATH="/etc/systemd/system/quaero-reconcile.service"
TIMER_PATH="/etc/systemd/system/quaero-reconcile.timer"
RECONCILE_ROOT="/opt/quaero/reconcile"

install -d -m 755 "${RECONCILE_ROOT}/releases"

cat > "${RUNNER_PATH}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

METADATA_BASE_URL="http://metadata.google.internal/computeMetadata/v1/instance/attributes"
METADATA_HEADER="Metadata-Flavor: Google"
TOKEN_URL="http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"

get_metadata_or_fail() {
  local key="$1"
  local value=""

  if ! value="$(curl --silent --show-error --fail -H "${METADATA_HEADER}" "${METADATA_BASE_URL}/${key}")"; then
    echo "Missing required instance metadata key: ${key}" >&2
    exit 1
  fi

  if [[ -z "${value}" ]]; then
    echo "Instance metadata key is empty: ${key}" >&2
    exit 1
  fi

  printf '%s' "${value}"
}

RECONCILE_RELEASE_ID="$(get_metadata_or_fail "reconcile_release_id")"
RECONCILE_BUCKET="$(get_metadata_or_fail "reconcile_bucket")"
RECONCILE_OBJECT="$(get_metadata_or_fail "reconcile_object")"
RECONCILE_SHA256="$(get_metadata_or_fail "reconcile_sha256")"

RELEASE_DIR="/opt/quaero/reconcile/releases/${RECONCILE_RELEASE_ID}"
RECONCILE_SCRIPT_PATH="${RELEASE_DIR}/reconcile.sh"
RECONCILE_SCRIPT_TMP_PATH="${RECONCILE_SCRIPT_PATH}.tmp"

if [[ ! "${RECONCILE_SHA256}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "Invalid reconcile_sha256 metadata value." >&2
  exit 1
fi

install -d -m 755 "${RELEASE_DIR}"

TOKEN_JSON="$(curl --silent --show-error --fail -H "${METADATA_HEADER}" "${TOKEN_URL}")"
ACCESS_TOKEN="$(
  printf '%s' "${TOKEN_JSON}" \
    | tr -d '\n' \
    | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p'
)"

if [[ -z "${ACCESS_TOKEN}" ]]; then
  echo "Unable to read access token for reconcile artifact fetch." >&2
  exit 1
fi

ARTIFACT_URL="https://storage.googleapis.com/${RECONCILE_BUCKET}/${RECONCILE_OBJECT}"
if curl --silent --show-error --fail --location \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "${ARTIFACT_URL}" \
  -o "${RECONCILE_SCRIPT_TMP_PATH}"; then
  if [[ ! -s "${RECONCILE_SCRIPT_TMP_PATH}" ]]; then
    echo "Downloaded reconcile artifact is empty for release ${RECONCILE_RELEASE_ID}." >&2
    rm -f "${RECONCILE_SCRIPT_TMP_PATH}"
    exit 1
  fi

  DOWNLOADED_SHA256="$(sha256sum "${RECONCILE_SCRIPT_TMP_PATH}" | awk '{print $1}')"
  if [[ "${DOWNLOADED_SHA256}" != "${RECONCILE_SHA256}" ]]; then
    echo "Downloaded reconcile artifact hash mismatch for release ${RECONCILE_RELEASE_ID}." >&2
    rm -f "${RECONCILE_SCRIPT_TMP_PATH}"
    exit 1
  fi

  install -m 700 "${RECONCILE_SCRIPT_TMP_PATH}" "${RECONCILE_SCRIPT_PATH}"
  rm -f "${RECONCILE_SCRIPT_TMP_PATH}"
elif [[ -f "${RECONCILE_SCRIPT_PATH}" ]]; then
  rm -f "${RECONCILE_SCRIPT_TMP_PATH}" || true
  CACHED_SHA256="$(sha256sum "${RECONCILE_SCRIPT_PATH}" | awk '{print $1}')"
  if [[ "${CACHED_SHA256}" != "${RECONCILE_SHA256}" ]]; then
    echo "Cached reconcile artifact hash mismatch for release ${RECONCILE_RELEASE_ID}." >&2
    exit 1
  fi
  echo "Failed to download reconcile artifact; using cached artifact for release ${RECONCILE_RELEASE_ID}." >&2
else
  rm -f "${RECONCILE_SCRIPT_TMP_PATH}" || true
  echo "Failed to download reconcile artifact and no cached artifact is available." >&2
  exit 1
fi

"${RECONCILE_SCRIPT_PATH}"
EOF

chmod 700 "${RUNNER_PATH}"

cat > "${SERVICE_PATH}" <<'EOF'
[Unit]
Description=Quaero runtime reconcile
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/quaero-reconcile-runner.sh
EOF

cat > "${TIMER_PATH}" <<'EOF'
[Unit]
Description=Run Quaero runtime reconcile every 10 minutes

[Timer]
OnBootSec=2m
OnUnitActiveSec=10m
Unit=quaero-reconcile.service
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now quaero-reconcile.timer
systemctl start quaero-reconcile.service
