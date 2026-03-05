#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/create_pr.sh --title "<title>" --body-file <path> [options]

Options:
  --title <text>           PR title (required)
  --body-file <path>       Markdown file for PR body (required)
  --base <branch>          Base branch (default: main)
  --head <branch>          Head branch (default: current git branch)
  --task-id <id>           Optional Task issue id for logging context
  --max-attempts <n>       Number of gh pr create attempts (default: 1)
  -h, --help               Show help
USAGE
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

parse_repo_slug() {
  local url="$1"
  url="${url%.git}"
  if [[ "$url" =~ github\.com[:/]([^/]+/[^/]+)$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return 0
  fi
  return 1
}

manual_pr_url() {
  local origin_url repo_slug
  origin_url="$(git remote get-url origin 2>/dev/null || true)"
  if [[ -z "$origin_url" ]]; then
    return 1
  fi

  repo_slug="$(parse_repo_slug "$origin_url" || true)"
  if [[ -z "$repo_slug" ]]; then
    return 1
  fi

  printf 'https://github.com/%s/pull/new/%s\n' "$repo_slug" "$HEAD"
}

finalize_failed() {
  local reason="$1"
  local fallback_url

  echo "$reason" >&2
  echo "Supervised fallback order:" >&2
  echo "  1) Request elevated approval to run the command below directly." >&2
  echo "  2) If elevation is unavailable, run/paste the command manually." >&2
  printf 'Retry manually:\n  gh pr create --base %q --head %q --title %q --body-file %q\n' \
    "$BASE" "$HEAD" "$TITLE" "$BODY_FILE" >&2

  fallback_url="$(manual_pr_url || true)"
  if [[ -n "$fallback_url" ]]; then
    echo "Open PR manually in browser: $fallback_url" >&2
  fi

  exit 1
}

TITLE=""
BODY_FILE=""
BASE="main"
HEAD=""
TASK_ID=""
MAX_ATTEMPTS=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)
      TITLE="${2:-}"
      shift 2
      ;;
    --body-file)
      BODY_FILE="${2:-}"
      shift 2
      ;;
    --base)
      BASE="${2:-}"
      shift 2
      ;;
    --head)
      HEAD="${2:-}"
      shift 2
      ;;
    --task-id)
      TASK_ID="${2:-}"
      shift 2
      ;;
    --max-attempts)
      MAX_ATTEMPTS="${2:-}"
      shift 2
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

if [[ -z "$TITLE" || -z "$BODY_FILE" ]]; then
  echo "--title and --body-file are required." >&2
  usage
  exit 1
fi

if [[ ! -f "$BODY_FILE" ]]; then
  echo "Body file not found: $BODY_FILE" >&2
  exit 1
fi

if ! [[ "$MAX_ATTEMPTS" =~ ^[0-9]+$ ]] || [[ "$MAX_ATTEMPTS" -lt 1 ]]; then
  echo "--max-attempts must be a positive integer." >&2
  exit 1
fi

require_cmd git

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Must run inside a git repository." >&2
  exit 1
fi

if [[ -z "$HEAD" ]]; then
  HEAD="$(git rev-parse --abbrev-ref HEAD)"
fi

if [[ "$HEAD" == "HEAD" ]]; then
  echo "Detached HEAD is not supported." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GH_PREFLIGHT="$SCRIPT_DIR/gh_preflight.sh"

if [[ ! -x "$GH_PREFLIGHT" ]]; then
  echo "Missing required helper script in $SCRIPT_DIR: gh_preflight.sh" >&2
  exit 1
fi

if [[ -n "$TASK_ID" ]]; then
  echo "Task context: #$TASK_ID"
fi

echo "Preparing PR create: base=$BASE head=$HEAD title=$TITLE"

CREATE_CMD=(
  gh pr create
  --base "$BASE"
  --head "$HEAD"
  --title "$TITLE"
  --body-file "$BODY_FILE"
)

if ! "$GH_PREFLIGHT" --quiet; then
  finalize_failed "GH preflight failed."
fi

attempt=1
while [[ "$attempt" -le "$MAX_ATTEMPTS" ]]; do
  set +e
  create_output="$("${CREATE_CMD[@]}" 2>&1)"
  create_status=$?
  set -e

  if [[ "$create_status" -eq 0 ]]; then
    echo "$create_output"
    exit 0
  fi

  echo "gh pr create failed (attempt $attempt/$MAX_ATTEMPTS)." >&2
  echo "$create_output" >&2

  if [[ "$attempt" -lt "$MAX_ATTEMPTS" ]]; then
    sleep_seconds=$((attempt * 2))
    echo "Retrying in ${sleep_seconds}s..." >&2
    sleep "$sleep_seconds"
  fi

  attempt=$((attempt + 1))
done

finalize_failed "gh pr create failed after $MAX_ATTEMPTS attempts."
