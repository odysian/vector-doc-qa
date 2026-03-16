#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:-}"
if [[ -z "$IMAGE_TAG" ]]; then
  echo "Usage: $0 <image-tag>"
  exit 1
fi

ENV_FILE="${ENV_FILE:-/opt/quaero/env/backend.env}"
CONTAINER_NAME="quaero-backend"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

# Derive container port from ENV_FILE so the port mapping stays in sync with
# what the app actually binds to. Explicit override wins.
CONTAINER_PORT="${CONTAINER_PORT:-}"
if [[ -z "$CONTAINER_PORT" ]]; then
  CONTAINER_PORT="$(grep -E '^PORT=[0-9]+$' "$ENV_FILE" | cut -d= -f2 | head -n1 || true)"
  CONTAINER_PORT="${CONTAINER_PORT:-8000}"
fi

if [[ -n "${GHCR_USERNAME:-}" && -n "${GHCR_TOKEN:-}" ]]; then
  echo "Logging into ghcr.io as $GHCR_USERNAME"
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin >/dev/null
fi

echo "Pulling image: $IMAGE_TAG"
docker pull "$IMAGE_TAG"

echo "Running migrations"
docker run --rm --env-file "$ENV_FILE" "$IMAGE_TAG" alembic upgrade head

echo "Replacing container: $CONTAINER_NAME"
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm   "$CONTAINER_NAME" 2>/dev/null || true

docker run -d \
  --name "$CONTAINER_NAME" \
  -p "127.0.0.1:8000:${CONTAINER_PORT}" \
  --env-file "$ENV_FILE" \
  --restart unless-stopped \
  "$IMAGE_TAG"

docker image prune -f >/dev/null || true
echo "Deploy complete: $IMAGE_TAG"
