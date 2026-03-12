#!/usr/bin/env bash
set -euo pipefail

METADATA_BASE_URL="http://metadata.google.internal/computeMetadata/v1/instance/attributes"
METADATA_HEADER="Metadata-Flavor: Google"

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

get_metadata_or_empty() {
  local key="$1"
  curl --silent --show-error --fail -H "${METADATA_HEADER}" "${METADATA_BASE_URL}/${key}" 2>/dev/null || true
}

SSH_USER="$(get_metadata_or_fail "ssh_user")"
API_DOMAIN="$(get_metadata_or_fail "api_domain")"
FRONTEND_URL="$(get_metadata_or_fail "frontend_url")"
BACKEND_PORT="$(get_metadata_or_fail "backend_port")"
CERTBOT_EMAIL="$(get_metadata_or_empty "certbot_email")"
ENABLE_TLS_BOOTSTRAP="$(get_metadata_or_fail "enable_tls_bootstrap")"
BUCKET_NAME="$(get_metadata_or_fail "bucket_name")"
PROJECT_ID="$(get_metadata_or_fail "project_id")"
ENABLE_OPS_AGENT="$(get_metadata_or_fail "enable_ops_agent")"
OPS_AGENT_VERSION="$(get_metadata_or_fail "ops_agent_version")"
OPS_AGENT_CONFIG_B64="$(get_metadata_or_fail "ops_agent_config_b64")"

BOOTSTRAP_MARKER="/opt/quaero/.bootstrap_v2_done"
ENV_FILE="/opt/quaero/env/backend.env"
NGINX_SITE="/etc/nginx/sites-available/quaero-backend"
OPS_AGENT_CONFIG_DIR="/etc/google-cloud-ops-agent"
OPS_AGENT_CONFIG_PATH="${OPS_AGENT_CONFIG_DIR}/config.yaml"

export DEBIAN_FRONTEND=noninteractive

if ! id -u "${SSH_USER}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${SSH_USER}"
fi

install -d -m 755 /opt/quaero
install -d -m 755 /opt/quaero/deploy
install -d -m 755 /opt/quaero/env
install -d -m 755 /opt/quaero/logs

if [[ ! -f "${BOOTSTRAP_MARKER}" ]]; then
  apt-get update
  apt-get install -y ca-certificates curl nginx certbot python3-certbot-nginx

  if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
  fi

  systemctl enable --now docker
  systemctl enable --now certbot.timer || true
  touch "${BOOTSTRAP_MARKER}"
fi

# Ops Agent reconciliation intentionally runs outside the bootstrap marker
# so existing VMs can enable/version-pin the agent after initial provisioning.
if [[ "${ENABLE_OPS_AGENT}" == "true" ]]; then
  CURRENT_OPS_AGENT_VERSION="$(dpkg-query -W -f='${Version}' google-cloud-ops-agent 2>/dev/null || true)"
  OPS_AGENT_TARGET_VERSION="${OPS_AGENT_VERSION}"

  if [[ "${CURRENT_OPS_AGENT_VERSION}" != "${OPS_AGENT_TARGET_VERSION}" ]]; then
    apt-get update

    # Fresh images may not have the Ops Agent repo configured yet.
    OPS_AGENT_AVAILABLE_VERSIONS="$(apt-cache madison google-cloud-ops-agent 2>/dev/null | awk '{print $3}')"
    if [[ -z "${OPS_AGENT_AVAILABLE_VERSIONS}" ]]; then
      if ! command -v curl >/dev/null 2>&1; then
        apt-get install -y ca-certificates curl
      fi
      OPS_AGENT_REPO_SCRIPT="$(mktemp)"
      curl --retry 5 --retry-all-errors --connect-timeout 10 --max-time 120 -fsSL \
        "https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh" \
        -o "${OPS_AGENT_REPO_SCRIPT}"
      # Without --also-install this script only adds the apt repository.
      bash "${OPS_AGENT_REPO_SCRIPT}"
      rm -f "${OPS_AGENT_REPO_SCRIPT}"
      apt-get update
      OPS_AGENT_AVAILABLE_VERSIONS="$(apt-cache madison google-cloud-ops-agent 2>/dev/null | awk '{print $3}')"
    fi

    OPS_AGENT_RESOLVED_VERSION=""
    if printf '%s\n' "${OPS_AGENT_AVAILABLE_VERSIONS}" | grep -Fxq "${OPS_AGENT_TARGET_VERSION}"; then
      OPS_AGENT_RESOLVED_VERSION="${OPS_AGENT_TARGET_VERSION}"
    else
      REQUESTED_OPS_AGENT_BASE_VERSION="$(printf '%s\n' "${OPS_AGENT_TARGET_VERSION}" | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1 || true)"
      if [[ -n "${REQUESTED_OPS_AGENT_BASE_VERSION}" ]]; then
        REQUESTED_OPS_AGENT_BASE_VERSION_REGEX="$(printf '%s' "${REQUESTED_OPS_AGENT_BASE_VERSION}" | sed 's/\./\\./g')"
        OPS_AGENT_RESOLVED_VERSION="$(printf '%s\n' "${OPS_AGENT_AVAILABLE_VERSIONS}" | grep -E "^([0-9]+:)?${REQUESTED_OPS_AGENT_BASE_VERSION_REGEX}([~.+:_-].*)?$" | head -n 1 || true)"
      fi
    fi

    if [[ -z "${OPS_AGENT_RESOLVED_VERSION}" ]]; then
      echo "Requested Ops Agent version ${OPS_AGENT_TARGET_VERSION} not found in apt repositories." >&2
      echo "Available versions:" >&2
      printf '%s\n' "${OPS_AGENT_AVAILABLE_VERSIONS}" >&2
      exit 1
    fi

    if [[ "${CURRENT_OPS_AGENT_VERSION}" != "${OPS_AGENT_RESOLVED_VERSION}" ]]; then
      apt-get install -y --allow-downgrades "google-cloud-ops-agent=${OPS_AGENT_RESOLVED_VERSION}"
    fi
  fi

  RENDERED_OPS_AGENT_CONFIG="$(mktemp)"
  printf '%s' "${OPS_AGENT_CONFIG_B64}" | base64 --decode > "${RENDERED_OPS_AGENT_CONFIG}"

  if [[ ! -s "${RENDERED_OPS_AGENT_CONFIG}" ]]; then
    echo "Rendered Ops Agent config is empty." >&2
    exit 1
  fi

  NEW_OPS_AGENT_CONFIG_HASH="$(sha256sum "${RENDERED_OPS_AGENT_CONFIG}" | awk '{print $1}')"
  CURRENT_OPS_AGENT_CONFIG_HASH=""
  if [[ -f "${OPS_AGENT_CONFIG_PATH}" ]]; then
    CURRENT_OPS_AGENT_CONFIG_HASH="$(sha256sum "${OPS_AGENT_CONFIG_PATH}" | awk '{print $1}')"
  fi

  OPS_AGENT_CONFIG_CHANGED="false"
  if [[ ! -f "${OPS_AGENT_CONFIG_PATH}" ]] || [[ "${NEW_OPS_AGENT_CONFIG_HASH}" != "${CURRENT_OPS_AGENT_CONFIG_HASH}" ]]; then
    install -d -m 755 "${OPS_AGENT_CONFIG_DIR}"
    install -m 640 -o root -g root "${RENDERED_OPS_AGENT_CONFIG}" "${OPS_AGENT_CONFIG_PATH}.tmp"
    mv "${OPS_AGENT_CONFIG_PATH}.tmp" "${OPS_AGENT_CONFIG_PATH}"
    OPS_AGENT_CONFIG_CHANGED="true"
  fi
  rm -f "${RENDERED_OPS_AGENT_CONFIG}"

  systemctl enable --now google-cloud-ops-agent
  if [[ "${OPS_AGENT_CONFIG_CHANGED}" == "true" ]]; then
    systemctl restart google-cloud-ops-agent
  fi
else
  if systemctl list-unit-files google-cloud-ops-agent.service >/dev/null 2>&1; then
    systemctl disable --now google-cloud-ops-agent || true
  fi
fi

# Always render the NGINX site so proxy updates apply to existing VMs too.
cat > "${NGINX_SITE}" <<EOF
server {
    listen 80;
    server_name ${API_DOMAIN};

    # Keep SSE responses truly streaming for the query stream endpoint.
    location ~ ^/api/documents/[0-9]+/query/stream$ {
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_cache off;
        gzip off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        send_timeout 3600s;
        add_header X-Accel-Buffering "no" always;
    }

    location / {
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf "${NGINX_SITE}" /etc/nginx/sites-enabled/quaero-backend
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx
systemctl restart nginx

if [[ "${ENABLE_TLS_BOOTSTRAP}" == "true" ]] && [[ -n "${CERTBOT_EMAIL}" ]] && [[ ! -f "/etc/letsencrypt/live/${API_DOMAIN}/fullchain.pem" ]]; then
  certbot --nginx --non-interactive --agree-tos \
    --email "${CERTBOT_EMAIL}" \
    --domains "${API_DOMAIN}" \
    --redirect || true
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  cat > "${ENV_FILE}" <<EOF
# Fill in all placeholder values before first deploy.
DATABASE_URL=postgresql://postgres:<password>@<cloud-sql-ip>:5432/postgres?options=-c%20search_path=quaero,public
APP_ENV=production
SECRET_KEY=<strong-random-secret>
OPENAI_API_KEY=<openai-key>
ANTHROPIC_API_KEY=<anthropic-key>
REDIS_URL=<upstash-redis-url>
FRONTEND_URL=${FRONTEND_URL}
PORT=${BACKEND_PORT}
STORAGE_BACKEND=gcs
GCS_BUCKET_NAME=${BUCKET_NAME}
GCP_PROJECT_ID=${PROJECT_ID}
EOF
  chown "${SSH_USER}:${SSH_USER}" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
fi

if id -u "${SSH_USER}" >/dev/null 2>&1; then
  usermod -aG docker "${SSH_USER}" || true
  chown -R "${SSH_USER}:${SSH_USER}" /opt/quaero
fi
