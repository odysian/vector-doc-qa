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
CONTAINER_PORT="${CONTAINER_PORT:-}"

mkdir -p "$DEPLOY_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

# Derive container port from ENV_FILE's PORT setting so the docker port mapping and
# health check stay in sync with what the app actually binds to. Explicit override wins.
if [[ -z "${CONTAINER_PORT:-}" ]]; then
  CONTAINER_PORT="$(grep -E '^PORT=[0-9]+$' "$ENV_FILE" | cut -d= -f2 | head -n 1 || true)"
  CONTAINER_PORT="${CONTAINER_PORT:-8000}"
fi
if ! [[ "$CONTAINER_PORT" =~ ^[0-9]+$ ]] || ((CONTAINER_PORT < 1 || CONTAINER_PORT > 65535)); then
  echo "Invalid container port extracted from $ENV_FILE: $CONTAINER_PORT"
  exit 1
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
  _color_raw="$(cat "$ACTIVE_COLOR_FILE")"
  case "$_color_raw" in
    blue|green)
      active_color="$_color_raw"
      ;;
    *)
      echo "Invalid active color in $ACTIVE_COLOR_FILE; defaulting to blue"
      ;;
  esac
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

# Stop and remove any stale container with this name before starting fresh.
# No-op on clean systems; self-heals a prior crash after state was written but before old container cleanup.
docker stop "$new_container" 2>/dev/null || true
docker rm   "$new_container" 2>/dev/null || true

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

switched_upstream="false"
_tmp_upstream=""
write_state_file() {
  local target="$1"
  local value="$2"
  local tmp_file="${target}.tmp.$$"
  printf '%s\n' "$value" > "$tmp_file"
  mv "$tmp_file" "$target"
}

# Any failure from here to success recording must stop the new container so it doesn't
# run orphaned while the old container continues to serve live traffic.
_cleanup_on_failure() {
  local rc=$?
  # Clean up any upstream tmp file leaked by a failed write on the main path.
  rm -f "${_tmp_upstream:-}" 2>/dev/null || true
  if [[ $rc -ne 0 ]]; then
    if [[ "$switched_upstream" == "true" ]]; then
      _tmp_upstream="$(mktemp "${NGINX_UPSTREAM_FILE}.tmp.XXXXXX" 2>/dev/null)" || _tmp_upstream=""
      if [[ -n "$_tmp_upstream" ]]; then
        printf 'upstream quaero_backend {\n    server 127.0.0.1:%d;\n}\n' "$old_port" > "$_tmp_upstream" \
          && mv "$_tmp_upstream" "$NGINX_UPSTREAM_FILE" \
          || rm -f "$_tmp_upstream"
      fi
      sudo /usr/sbin/nginx -s reload || true
    fi

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
# Atomic write (tmp+mv) so a mid-write crash cannot leave upstream.conf empty/corrupt.
_tmp_upstream="$(mktemp "${NGINX_UPSTREAM_FILE}.tmp.XXXXXX")"
printf 'upstream quaero_backend {\n    server 127.0.0.1:%d;\n}\n' "$new_port" > "$_tmp_upstream"
mv "$_tmp_upstream" "$NGINX_UPSTREAM_FILE"
sudo /usr/sbin/nginx -s reload
switched_upstream="true"
echo "NGINX upstream switched to ${new_color} (port ${new_port})"

write_state_file "$ACTIVE_COLOR_FILE" "$new_color"
write_state_file "$LAST_GOOD_FILE" "$IMAGE_TAG"
echo "Deployment successful. Recorded last good image in $LAST_GOOD_FILE"

# State is now durable; remove cleanup trap.
trap - EXIT

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
