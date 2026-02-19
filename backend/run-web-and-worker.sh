#!/usr/bin/env bash
set -euo pipefail

# Run worker and API side by side, and fail fast if either process exits.
python -m arq app.workers.arq_worker.WorkerSettings &
worker_pid=$!

python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" &
web_pid=$!

cleanup() {
  kill "$worker_pid" "$web_pid" 2>/dev/null || true
  wait "$worker_pid" "$web_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

wait -n "$worker_pid" "$web_pid"
exit_code=$?

if ! kill -0 "$worker_pid" 2>/dev/null; then
  echo "ARQ worker exited; shutting down API process."
fi

exit "$exit_code"
