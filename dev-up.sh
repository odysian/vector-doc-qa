#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PY="$BACKEND_DIR/.venv/bin/python"

pids=()
cleaned_up=0

cleanup() {
  if [[ "$cleaned_up" -eq 1 ]]; then
    return
  fi
  cleaned_up=1

  echo
  echo "Stopping dev services..."
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait || true
}

trap cleanup EXIT INT TERM

if [[ ! -x "$BACKEND_PY" ]]; then
  echo "Missing backend venv python at: $BACKEND_PY"
  echo "Create it first, then install dependencies:"
  echo "  cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Missing frontend dependencies. Run: cd frontend && npm install"
  exit 1
fi

echo "Starting local infrastructure (Postgres + Redis)..."
docker compose up -d db redis

echo "Checking backend queue dependencies..."
if ! "$BACKEND_PY" -c "import arq, redis" >/dev/null 2>&1; then
  echo "Missing backend packages arq/redis in backend .venv."
  echo "Run: cd backend && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

echo "Starting backend API (uvicorn --reload)..."
(
  cd "$BACKEND_DIR"
  exec "$BACKEND_PY" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) &
pids+=("$!")

echo "Starting ARQ worker..."
(
  cd "$BACKEND_DIR"
  exec "$BACKEND_PY" -m arq app.workers.arq_worker.WorkerSettings
) &
pids+=("$!")

echo "Starting frontend dev server..."
(
  cd "$FRONTEND_DIR"
  exec npm run dev
) &
pids+=("$!")

echo
echo "All services started."
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "Docs:     http://localhost:8000/docs"
echo
echo "Press Ctrl+C to stop everything."

if ! wait -n "${pids[@]}"; then
  echo
  echo "A service exited with an error."
  exit 1
fi
