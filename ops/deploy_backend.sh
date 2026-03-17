#!/usr/bin/env bash
# Runs as root (called via: sudo bash deploy_backend.sh <image-tag>).
# Handles Docker container swap, NGINX config, certbot, and health check.
# Self-heals NGINX and TLS on every deploy so boot-time failures don't persist.
set -euo pipefail

IMAGE_TAG="${1:-}"
[[ -z "$IMAGE_TAG" ]] && { echo "Usage: $0 <image-tag>"; exit 1; }

ENV_FILE="${ENV_FILE:-/opt/quaero/env/backend.env}"
INFRA_ENV="/opt/quaero/env/infra.env"
CONTAINER_NAME="quaero-backend"
NGINX_SITE="/etc/nginx/sites-available/quaero-backend"
ACME_WEBROOT="/var/www/acme-challenge"
CERTBOT_CMD="/opt/certbot-venv/bin/certbot"

[[ -f "$ENV_FILE" ]] || { echo "ERROR: Missing env file: $ENV_FILE"; exit 1; }

# Infra config (domain/email) written by startup script; not in backend.env.
[[ -f "$INFRA_ENV" ]] && source "$INFRA_ENV"
API_DOMAIN="${API_DOMAIN:-}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
LE_LIVE_DIR="/etc/letsencrypt/live/${API_DOMAIN}"

CONTAINER_PORT="$(grep -E '^PORT=[0-9]+$' "$ENV_FILE" | cut -d= -f2 | head -n1 || true)"
CONTAINER_PORT="${CONTAINER_PORT:-8000}"

# ZeroSSL EAB credentials — stored in backend.env so they travel with the deploy payload.
ZEROSSL_EAB_KID="$(grep -E '^ZEROSSL_EAB_KID=' "$ENV_FILE" | cut -d= -f2- | head -n1 || true)"
ZEROSSL_EAB_HMAC_KEY="$(grep -E '^ZEROSSL_EAB_HMAC_KEY=' "$ENV_FILE" | cut -d= -f2- | head -n1 || true)"

# ── Docker ────────────────────────────────────────────────────────────────────
if [[ -n "${GHCR_USERNAME:-}" && -n "${GHCR_TOKEN:-}" ]]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin >/dev/null
fi

echo "Pulling: $IMAGE_TAG"
docker pull "$IMAGE_TAG"

echo "Running migrations..."
docker run --rm --env-file "$ENV_FILE" "$IMAGE_TAG" alembic upgrade head

echo "Swapping container..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm   "$CONTAINER_NAME" 2>/dev/null || true

docker run -d \
  --name "$CONTAINER_NAME" \
  -p "127.0.0.1:8000:${CONTAINER_PORT}" \
  --env-file "$ENV_FILE" \
  --restart unless-stopped \
  "$IMAGE_TAG"

docker image prune -f >/dev/null || true

# ── NGINX ─────────────────────────────────────────────────────────────────────
install -d -m 755 /opt/quaero/nginx "$ACME_WEBROOT"

# Upstream block: written once, persists across deploys.
if [[ ! -f /opt/quaero/nginx/upstream.conf ]]; then
  cat > /opt/quaero/nginx/upstream.conf <<'UPSTREAM'
upstream quaero_backend {
    server 127.0.0.1:8000;
}
UPSTREAM
fi

write_http_nginx_config() {
  cat > "$NGINX_SITE" <<NGINX
include /opt/quaero/nginx/upstream.conf;

server {
    listen 80;
    server_name ${API_DOMAIN};

    location ^~ /.well-known/acme-challenge/ {
        alias ${ACME_WEBROOT}/.well-known/acme-challenge/;
    }

    location ~ ^/api/documents/[0-9]+/query/stream$ {
        proxy_pass http://quaero_backend;
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
    }

    location / {
        proxy_pass http://quaero_backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX
}

write_https_nginx_config() {
  cat > "$NGINX_SITE" <<NGINX
include /opt/quaero/nginx/upstream.conf;

server {
    listen 80;
    server_name ${API_DOMAIN};

    # Allow ACME HTTP-01 challenges through for cert renewal.
    location ^~ /.well-known/acme-challenge/ {
        alias ${ACME_WEBROOT}/.well-known/acme-challenge/;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name ${API_DOMAIN};
    ssl_certificate     ${LE_LIVE_DIR}/fullchain.pem;
    ssl_certificate_key ${LE_LIVE_DIR}/privkey.pem;

    location ~ ^/api/documents/[0-9]+/query/stream$ {
        proxy_pass http://quaero_backend;
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
        add_header X-Accel-Buffering "no" always;
    }

    location / {
        proxy_pass http://quaero_backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX
}

# If cert is present: HTTPS. If not: attempt certbot, then decide.
if [[ -f "${LE_LIVE_DIR}/fullchain.pem" && -f "${LE_LIVE_DIR}/privkey.pem" ]]; then
  echo "TLS cert found; writing HTTPS config."
  write_https_nginx_config
elif [[ -n "$API_DOMAIN" && -n "$CERTBOT_EMAIL" && -n "$ZEROSSL_EAB_KID" && -n "$ZEROSSL_EAB_HMAC_KEY" && -x "$CERTBOT_CMD" ]]; then
  echo "No TLS cert; attempting ZeroSSL certbot for ${API_DOMAIN}..."
  # Write HTTP config first so NGINX can serve the ACME challenge.
  write_http_nginx_config
  ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/quaero-backend
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && (systemctl reload nginx 2>/dev/null || systemctl start nginx)

  if "$CERTBOT_CMD" certonly --non-interactive --agree-tos \
       --email "$CERTBOT_EMAIL" --domains "$API_DOMAIN" \
       --webroot -w "$ACME_WEBROOT" \
       --server https://acme.zerossl.com/v2/DV90 \
       --eab-kid "$ZEROSSL_EAB_KID" \
       --eab-hmac-key "$ZEROSSL_EAB_HMAC_KEY"; then
    echo "Cert issued; writing HTTPS config."
    write_https_nginx_config
  else
    echo "WARNING: certbot failed; serving HTTP only."
  fi
else
  echo "No cert and certbot unavailable; writing HTTP config."
  write_http_nginx_config
fi

ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/quaero-backend
rm -f /etc/nginx/sites-enabled/default

if nginx -t 2>/dev/null; then
  systemctl reload nginx 2>/dev/null || systemctl start nginx
  echo "NGINX reloaded."
else
  echo "ERROR: NGINX config test failed:"
  nginx -t
  exit 1
fi

# ── Health check ──────────────────────────────────────────────────────────────
echo "Waiting for app to be healthy (up to 60s)..."
for i in $(seq 1 12); do
  if curl -sf "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    echo "App is healthy. Deploy complete: $IMAGE_TAG"
    exit 0
  fi
  echo "  attempt $i/12..."
  sleep 5
done

echo "ERROR: App did not become healthy after 60s."
docker logs "$CONTAINER_NAME" --tail=40
exit 1
