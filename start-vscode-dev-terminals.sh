#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VSCODE_DIR="$ROOT_DIR/.vscode"
TASKS_FILE="$VSCODE_DIR/tasks.json"

warn_manual() {
  echo "Workspace opened."
  echo "Run build task manually: Ctrl+Shift+B (default task: dev:stack)."
}

trigger_with_xdotool() {
  if ! command -v xdotool >/dev/null 2>&1; then
    return 1
  fi
  if [[ -z "${DISPLAY:-}" ]]; then
    return 1
  fi

  # Give VS Code time to focus/open its window before injecting keys.
  sleep 2

  local win_id
  win_id="$(xdotool search --name "Visual Studio Code" 2>/dev/null | tail -n 1 || true)"
  if [[ -z "$win_id" ]]; then
    return 1
  fi

  xdotool windowactivate --sync "$win_id"
  xdotool key --clearmodifiers ctrl+shift+b
  # If a task picker appears, default to first entry.
  sleep 0.3
  xdotool key --clearmodifiers Return
  return 0
}

ensure_dev_stack_task() {
  mkdir -p "$VSCODE_DIR"
  # Always rewrite to keep this repo's local stack commands in sync.
  cat >"$TASKS_FILE" <<'EOF'
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "dev:db",
      "type": "shell",
      "command": "docker compose up -d db redis",
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "presentation": {
        "reveal": "always",
        "panel": "new"
      },
      "problemMatcher": []
    },
    {
      "label": "dev:backend",
      "type": "shell",
      "command": "bash -lc 'test -x .venv/bin/python || { echo \"Missing backend/.venv. Run: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt\"; exit 1; }; for i in {1..60}; do (echo >/dev/tcp/127.0.0.1/5434) >/dev/null 2>&1 && (echo >/dev/tcp/127.0.0.1/6379) >/dev/null 2>&1 && break; sleep 1; done; exec .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000'",
      "options": {
        "cwd": "${workspaceFolder}/backend"
      },
      "presentation": {
        "reveal": "always",
        "panel": "new"
      },
      "problemMatcher": []
    },
    {
      "label": "dev:worker",
      "type": "shell",
      "command": "bash -lc 'test -x .venv/bin/python || { echo \"Missing backend/.venv. Run: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt\"; exit 1; }; for i in {1..60}; do (echo >/dev/tcp/127.0.0.1/6379) >/dev/null 2>&1 && break; sleep 1; done; exec .venv/bin/python -m arq app.workers.arq_worker.WorkerSettings'",
      "options": {
        "cwd": "${workspaceFolder}/backend"
      },
      "presentation": {
        "reveal": "always",
        "panel": "new"
      },
      "problemMatcher": []
    },
    {
      "label": "dev:frontend",
      "type": "shell",
      "command": "bash -lc 'test -d node_modules || { echo \"Missing frontend dependencies. Run: cd frontend && npm install\"; exit 1; }; PIDS=\"$(pgrep -f \"$PWD/node_modules/.bin/next dev\" || true)\"; if [[ -n \"$PIDS\" ]]; then echo \"Stopping existing Next dev process(es): $PIDS\"; kill $PIDS || true; sleep 1; fi; rm -f .next/dev/lock; exec npm run dev'",
      "options": {
        "cwd": "${workspaceFolder}/frontend"
      },
      "presentation": {
        "reveal": "always",
        "panel": "new"
      },
      "problemMatcher": []
    },
    {
      "label": "dev:db-shell",
      "type": "shell",
      "command": "bash -lc 'docker compose up -d db >/dev/null; for i in {1..60}; do docker compose exec -T db pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done; docker compose exec -T db pg_isready -U postgres >/dev/null 2>&1 || { echo \"Database did not become ready in time.\"; exit 1; }; exec docker compose exec db psql -U postgres -d document_intelligence'",
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "presentation": {
        "reveal": "always",
        "panel": "new"
      },
      "problemMatcher": []
    },
    {
      "label": "dev:stack",
      "dependsOn": [
        "dev:db",
        "dev:backend",
        "dev:worker",
        "dev:frontend",
        "dev:db-shell"
      ],
      "dependsOrder": "parallel",
      "group": {
        "kind": "build",
        "isDefault": true
      },
      "problemMatcher": []
    }
  ]
}
EOF
}

if ! command -v code >/dev/null 2>&1; then
  echo "VS Code CLI ('code') is not available in PATH."
  echo "Open VS Code and run build task: dev:stack"
  exit 1
fi

ensure_dev_stack_task

if ! code --reuse-window "$ROOT_DIR"; then
  echo "Failed to open workspace in VS Code."
  exit 1
fi

# Some VS Code CLI builds do not support --command. Detect and guide.
if ! code --help 2>&1 | grep -q -- "--command"; then
  echo "VS Code CLI does not support --command."
  if trigger_with_xdotool; then
    echo "Triggered build task via xdotool (dev:stack)."
    exit 0
  fi
  warn_manual
  exit 0
fi

# VS Code needs a short delay before accepting follow-up command dispatches.
sleep 1

task_output="$(code --reuse-window "$ROOT_DIR" --command workbench.action.tasks.build 2>&1 || true)"
if echo "$task_output" | grep -q "not in the list of known options"; then
  echo "VS Code CLI ignored --command."
  if trigger_with_xdotool; then
    echo "Triggered build task via xdotool (dev:stack)."
    exit 0
  fi
  warn_manual
  exit 0
fi

if [ -n "$task_output" ]; then
  echo "$task_output"
fi

echo "Started dev terminals via VS Code task: dev:stack"
