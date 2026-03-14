#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:-}"
if [[ -z "$IMAGE_TAG" ]]; then
  echo "Usage: $0 <image-tag>"
  exit 1
fi

ENV_FILE="${ENV_FILE:-/opt/quaero/env/backend.env}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/quaero/deploy}"
NGINX_UPSTREAM_FILE="${NGINX_UPSTREAM_FILE:-/opt/quaero/nginx/upstream.conf}"
LAST_GOOD_FILE="${LAST_GOOD_FILE:-$DEPLOY_DIR/last_successful_image}"
ACTIVE_COLOR_FILE="${ACTIVE_COLOR_FILE:-$DEPLOY_DIR/active_color}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_SLEEP_SECONDS="${HEALTH_SLEEP_SECONDS:-2}"

mkdir -p "$DEPLOY_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

# Derive container port from ENV_FILE's PORT setting so the docker port mapping and
# health check stay in sync with what the app actually binds to. Explicit override wins.
if [[ -z "${CONTAINER_PORT:-}" ]]; then
  CONTAINER_PORT="$(grep -E '^PORT=[0-9]+$' "$ENV_FILE" | cut -d= -f2 | head -1 || true)"
  CONTAINER_PORT="${CONTAINER_PORT:-8000}"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found on host"
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl not found on host"
  exit 1
fi

if [[ -n "${GHCR_USERNAME:-}" && -n "${GHCR_TOKEN:-}" ]]; then
  echo "Logging into ghcr.io as $GHCR_USERNAME"
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin >/dev/null
fi

echo "Pulling image: $IMAGE_TAG"
docker pull "$IMAGE_TAG"

echo "Running migrations"
docker run --rm --env-file "$ENV_FILE" "$IMAGE_TAG" alembic upgrade head

# Determine active color; default to blue when state file is absent (first deploy or legacy single-container).
active_color="blue"
if [[ -f "$ACTIVE_COLOR_FILE" ]]; then
  active_color="$(cat "$ACTIVE_COLOR_FILE")"
fi

# Derive new color and host ports. The container process binds to CONTAINER_PORT internally;
# host ports 8000 (blue) and 8001 (green) are mapped to it for NGINX upstream switching.
if [[ "$active_color" == "blue" ]]; then
  new_color="green"
  new_port=8001
  old_port=8000
else
  new_color="blue"
  new_port=8000
  old_port=8001
fi

old_container="quaero-backend-${active_color}"
new_container="quaero-backend-${new_color}"
new_health_url="http://127.0.0.1:${new_port}/health"

echo "Active: ${active_color} (port ${old_port}). Deploying ${new_color} on port ${new_port}."

echo "Starting container: $new_container ($IMAGE_TAG)"
if ! docker run -d \
    --name "$new_container" \
    -p "127.0.0.1:${new_port}:${CONTAINER_PORT}" \
    --env-file "$ENV_FILE" \
    --restart unless-stopped \
    "$IMAGE_TAG" >/dev/null; then
  echo "Failed to start new container $new_container"
  exit 1
fi

# Any failure from here to success recording must stop the new container so it doesn't
# run orphaned while the old container continues to serve live traffic.
_cleanup_on_failure() {
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "Deploy failed (exit $rc); removing $new_container. Old container $old_container is untouched."
    docker stop "$new_container" >/dev/null 2>&1 || true
    docker rm   "$new_container" >/dev/null 2>&1 || true
  fi
}
trap _cleanup_on_failure EXIT

# Health-check the new container before touching the live NGINX upstream.
healthy=false
for ((attempt = 1; attempt <= HEALTH_RETRIES; attempt++)); do
  if curl -fsS "$new_health_url" >/dev/null; then
    healthy=true
    break
  fi
  echo "Health check attempt ${attempt}/${HEALTH_RETRIES} failed"
  sleep "$HEALTH_SLEEP_SECONDS"
done

if [[ "$healthy" != "true" ]]; then
  echo "New container $new_container failed health checks"
  docker logs "$new_container" --tail 200 || true
  echo "Old container $old_container is untouched. Deploy aborted."
  exit 1
fi

# Switch NGINX upstream to new container then record state.
# Order matters: reload before writing state so a reload failure leaves state unchanged.
printf 'upstream quaero_backend {\n    server 127.0.0.1:%d;\n}\n' "$new_port" > "$NGINX_UPSTREAM_FILE"
sudo /usr/sbin/nginx -s reload
# NGINX is now serving the new container — disarm the cleanup trap here.
# Removing the new container after this point would cause 502s; state file writes below
# are best-effort observability records, not service-critical.
trap - EXIT
echo "NGINX upstream switched to ${new_color} (port ${new_port})"

echo "$new_color" > "$ACTIVE_COLOR_FILE"
echo "$IMAGE_TAG" > "$LAST_GOOD_FILE"
echo "Deployment successful. Recorded last good image in $LAST_GOOD_FILE"

# Stop old blue-green container (safe no-op if it doesn't exist yet).
docker stop "$old_container" >/dev/null 2>&1 || true
docker rm   "$old_container" >/dev/null 2>&1 || true

# On first cutover from legacy single-container, stop it too (idempotent: no-op afterwards).
if docker container inspect "quaero-backend" >/dev/null 2>&1; then
  echo "Stopping legacy container: quaero-backend"
  docker stop "quaero-backend" >/dev/null || true
  docker rm   "quaero-backend" >/dev/null || true
fi

docker image prune -f >/dev/null || true
