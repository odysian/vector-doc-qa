#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/gh_preflight.sh [--quiet]

Checks:
  1. gh CLI is installed
  2. GitHub CLI auth is valid
EOF
}

QUIET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quiet)
      QUIET=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  [[ "$QUIET" -eq 1 ]] || echo "FAIL: gh command not found" >&2
  exit 1
fi

if ! gh auth status -h github.com >/dev/null 2>&1; then
  [[ "$QUIET" -eq 1 ]] || echo "FAIL: gh auth status failed (invalid/expired token or auth missing)" >&2
  exit 1
fi

[[ "$QUIET" -eq 1 ]] || echo "PASS: gh preflight checks succeeded"
