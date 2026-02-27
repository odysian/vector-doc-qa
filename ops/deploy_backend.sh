#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:-}"
if [[ -z "$IMAGE_TAG" ]]; then
  echo "Usage: $0 <image-tag>"
  exit 1
fi

CONTAINER_NAME="${CONTAINER_NAME:-quaero-backend}"
ENV_FILE="${ENV_FILE:-/opt/quaero/env/backend.env}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/quaero/deploy}"
LAST_GOOD_FILE="${LAST_GOOD_FILE:-$DEPLOY_DIR/last_successful_image}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_SLEEP_SECONDS="${HEALTH_SLEEP_SECONDS:-2}"
PORT_MAPPING="${PORT_MAPPING:-127.0.0.1:8000:8000}"

mkdir -p "$DEPLOY_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
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

previous_image=""
if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  previous_image="$(docker inspect --format '{{.Config.Image}}' "$CONTAINER_NAME")"
  echo "Current container image: $previous_image"
  docker stop "$CONTAINER_NAME" >/dev/null || true
  docker rm "$CONTAINER_NAME" >/dev/null || true
fi

start_container() {
  local image="$1"
  docker run -d \
    --name "$CONTAINER_NAME" \
    -p "$PORT_MAPPING" \
    --env-file "$ENV_FILE" \
    --restart unless-stopped \
    "$image" >/dev/null
}

echo "Starting container: $IMAGE_TAG"
if ! start_container "$IMAGE_TAG"; then
  echo "Failed to start new container"
  if [[ -n "$previous_image" ]]; then
    echo "Attempting rollback start: $previous_image"
    start_container "$previous_image"
  fi
  exit 1
fi

healthy=false
for ((attempt = 1; attempt <= HEALTH_RETRIES; attempt++)); do
  if curl -fsS "$HEALTH_URL" >/dev/null; then
    healthy=true
    break
  fi
  echo "Health check attempt ${attempt}/${HEALTH_RETRIES} failed"
  sleep "$HEALTH_SLEEP_SECONDS"
done

if [[ "$healthy" != "true" ]]; then
  echo "New container failed health checks"
  docker logs "$CONTAINER_NAME" --tail 200 || true
  docker stop "$CONTAINER_NAME" >/dev/null || true
  docker rm "$CONTAINER_NAME" >/dev/null || true

  if [[ -n "$previous_image" ]]; then
    echo "Rolling back to: $previous_image"
    start_container "$previous_image"
  fi
  exit 1
fi

echo "$IMAGE_TAG" > "$LAST_GOOD_FILE"
echo "Deployment successful. Recorded last good image in $LAST_GOOD_FILE"

docker image prune -f >/dev/null || true
