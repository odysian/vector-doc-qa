#!/usr/bin/env bash
set -euo pipefail

# Run ARQ worker in background, then launch the API server in foreground.
python -m arq app.workers.arq_worker.WorkerSettings &
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
