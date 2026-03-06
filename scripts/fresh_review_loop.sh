#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/fresh_review_loop.sh --task-id <id> [options]

Options:
  --task-id <id>          Task issue id (required)
  --base <branch>         Base branch for review context (default: origin/main)
  --verify-cmd <command>  Verification command reference for reviewer context
  --audit-root <path>     Audit root directory (default: .codex/audit)
  --round <1|2>           Review round to prepare (default: 1)
  --audit-dir <path>      Existing audit directory (required for --round 2)
  --prior-review <path>   Prior review report file (required for --round 2)
  --pr-url <url>          Optional PR URL for reviewer context
  -h, --help              Show this help
USAGE
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

TASK_ID=""
BASE_BRANCH="origin/main"
VERIFY_CMD=""
AUDIT_ROOT=".codex/audit"
ROUND="1"
AUDIT_DIR=""
PRIOR_REVIEW=""
PR_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-id)
      TASK_ID="${2:-}"
      shift 2
      ;;
    --base)
      BASE_BRANCH="${2:-}"
      shift 2
      ;;
    --verify-cmd)
      VERIFY_CMD="${2:-}"
      shift 2
      ;;
    --audit-root)
      AUDIT_ROOT="${2:-}"
      shift 2
      ;;
    --round)
      ROUND="${2:-}"
      shift 2
      ;;
    --audit-dir)
      AUDIT_DIR="${2:-}"
      shift 2
      ;;
    --prior-review)
      PRIOR_REVIEW="${2:-}"
      shift 2
      ;;
    --pr-url)
      PR_URL="${2:-}"
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

if [[ -z "$TASK_ID" ]]; then
  echo "--task-id is required." >&2
  usage
  exit 1
fi

if [[ "$ROUND" != "1" && "$ROUND" != "2" ]]; then
  echo "--round must be 1 or 2." >&2
  exit 1
fi

require_cmd git

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Must run inside a git repository." >&2
  exit 1
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" == "HEAD" ]]; then
  echo "Detached HEAD is not supported for this workflow." >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Working tree must be clean before preparing review handoff." >&2
  echo "Commit/stash tracked changes first." >&2
  exit 1
fi

if [[ "$ROUND" == "1" ]]; then
  if [[ -n "$AUDIT_DIR" ]]; then
    echo "--audit-dir is only valid for --round 2." >&2
    exit 1
  fi

  TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
  AUDIT_DIR="$AUDIT_ROOT/task-${TASK_ID}-${TIMESTAMP}"
  mkdir -p "$AUDIT_DIR"

  SUMMARY_FILE="$AUDIT_DIR/summary.md"
  META_FILE="$AUDIT_DIR/metadata.env"
  PROMPT_FILE="$AUDIT_DIR/task-${TASK_ID}-r1-review-prompt.md"

  cat > "$META_FILE" <<META
task_id=$TASK_ID
base_branch=$BASE_BRANCH
current_branch=$CURRENT_BRANCH
timestamp_utc=$TIMESTAMP
review_mode=manual_handoff
max_review_rounds=2
META

  cat > "$SUMMARY_FILE" <<SUMMARY
# Fresh-Context Review Handoff Summary

- Task: #$TASK_ID
- Branch: \`$CURRENT_BRANCH\`
- Base branch: \`$BASE_BRANCH\`
- Timestamp (UTC): \`$TIMESTAMP\`
- Review mode: \`manual_handoff\`
- Max review rounds: \`2\`

## Round Status

- r1 prompt generated: \`$(basename "$PROMPT_FILE")\`
- r1 reviewer response pending: \`task-${TASK_ID}-r1-manual-review.md\`

SUMMARY

  cat > "$PROMPT_FILE" <<PROMPT
Review Task #$TASK_ID on branch \`$CURRENT_BRANCH\` against base \`$BASE_BRANCH\`.

Scope:
- Perform read-only review of implementation quality, correctness, regressions, and missing tests/docs.
- Do not make code changes in this review run.

Context:
- Task: #$TASK_ID
- Branch: $CURRENT_BRANCH
- Base: $BASE_BRANCH
- Verify command reference: ${VERIFY_CMD:-"(not supplied)"}
- PR URL: ${PR_URL:-"(not supplied)"}

Required reviewer output format:
1. Verdict: APPROVED or ACTIONABLE
2. Summary (2-4 lines)
3. Findings (if ACTIONABLE): each item must include
   - severity: high|medium|low
   - file/path
   - issue description
   - required fix
4. If APPROVED, explicitly state no blocking findings.

Keep findings concrete and patchable.
PROMPT

  echo "Prepared round r1 reviewer handoff." 
  echo "Audit directory: $AUDIT_DIR"
  echo "Reviewer prompt: $PROMPT_FILE"
  echo "Expected reviewer response file: $AUDIT_DIR/task-${TASK_ID}-r1-manual-review.md"
  exit 0
fi

# round 2
if [[ -z "$AUDIT_DIR" ]]; then
  echo "--audit-dir is required for --round 2." >&2
  exit 1
fi
if [[ ! -d "$AUDIT_DIR" ]]; then
  echo "Audit directory not found: $AUDIT_DIR" >&2
  exit 1
fi
if [[ -z "$PRIOR_REVIEW" ]]; then
  echo "--prior-review is required for --round 2." >&2
  exit 1
fi
if [[ ! -f "$PRIOR_REVIEW" ]]; then
  echo "Prior review file not found: $PRIOR_REVIEW" >&2
  exit 1
fi

SUMMARY_FILE="$AUDIT_DIR/summary.md"
PROMPT_FILE="$AUDIT_DIR/task-${TASK_ID}-r2-review-prompt.md"
PRIOR_REVIEW_COPY="$AUDIT_DIR/task-${TASK_ID}-r1-manual-review.md"

if [[ "$PRIOR_REVIEW" != "$PRIOR_REVIEW_COPY" ]]; then
  cp "$PRIOR_REVIEW" "$PRIOR_REVIEW_COPY"
fi

if [[ ! -f "$SUMMARY_FILE" ]]; then
  cat > "$SUMMARY_FILE" <<SUMMARY
# Fresh-Context Review Handoff Summary

- Task: #$TASK_ID
- Branch: \`$CURRENT_BRANCH\`
- Base branch: \`$BASE_BRANCH\`
- Review mode: \`manual_handoff\`
- Max review rounds: \`2\`

## Round Status

SUMMARY
fi

cat > "$PROMPT_FILE" <<PROMPT
Run follow-up review round r2 for Task #$TASK_ID on branch \`$CURRENT_BRANCH\` against base \`$BASE_BRANCH\`.

Prior review report to validate against:
- $(basename "$PRIOR_REVIEW_COPY")

Goals:
- Verify whether actionable findings from r1 were addressed correctly.
- Identify only remaining or newly introduced actionable findings.
- Do not make code changes in this review run.

Required reviewer output format:
1. Verdict: APPROVED or ACTIONABLE
2. Resolution status of prior findings (resolved/unresolved)
3. Remaining findings (if any) with:
   - severity: high|medium|low
   - file/path
   - issue description
   - required fix

If fully resolved, return APPROVED explicitly.
PROMPT

{
  echo "- r2 prompt generated: \`$(basename "$PROMPT_FILE")\`"
  echo "- r2 reviewer response pending: \`task-${TASK_ID}-r2-manual-review.md\`"
} >> "$SUMMARY_FILE"

echo "Prepared round r2 reviewer handoff."
echo "Audit directory: $AUDIT_DIR"
echo "Reviewer prompt: $PROMPT_FILE"
echo "Expected reviewer response file: $AUDIT_DIR/task-${TASK_ID}-r2-manual-review.md"
