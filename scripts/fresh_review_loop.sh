#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/fresh_review_loop.sh --task-id <id> [options]

Options:
  --task-id <id>           Task issue id (required)
  --base <branch>          Base branch for diff review (default: origin/main)
  --verify-cmd <command>   Verification command to run after each patch commit
  --audit-root <path>      Audit root directory (default: .codex/audit)
  --codex-max-attempts <n> Max retries for codex review/patch calls (default: 2)
  -h, --help               Show this help
USAGE
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

escape_sed() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

TASK_ID=""
BASE_BRANCH="origin/main"
VERIFY_CMD=""
AUDIT_ROOT=".codex/audit"
CODEX_MAX_ATTEMPTS=2

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
    --codex-max-attempts)
      CODEX_MAX_ATTEMPTS="${2:-}"
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

if ! [[ "$CODEX_MAX_ATTEMPTS" =~ ^[0-9]+$ ]] || [[ "$CODEX_MAX_ATTEMPTS" -lt 1 ]]; then
  echo "--codex-max-attempts must be a positive integer." >&2
  exit 1
fi

require_cmd git
require_cmd codex
require_cmd jq

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
  echo "Working tree must be clean before running fresh review loop." >&2
  echo "Commit/stash local changes first." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_DIR="$SCRIPT_DIR/prompts"
SCHEMA_DIR="$SCRIPT_DIR/schemas"

REVIEW_TEMPLATE="$PROMPT_DIR/review-round.md"
PATCH_TEMPLATE="$PROMPT_DIR/patch-round.md"
REVIEW_SCHEMA="$SCHEMA_DIR/review-round.schema.json"
PATCH_SCHEMA="$SCHEMA_DIR/patch-round.schema.json"

for required_file in "$REVIEW_TEMPLATE" "$PATCH_TEMPLATE" "$REVIEW_SCHEMA" "$PATCH_SCHEMA"; do
  if [[ ! -f "$required_file" ]]; then
    echo "Missing required file: $required_file" >&2
    exit 1
  fi
done

TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
AUDIT_DIR="$AUDIT_ROOT/task-${TASK_ID}-${TIMESTAMP}"
mkdir -p "$AUDIT_DIR"

SUMMARY_FILE="$AUDIT_DIR/summary.md"
META_FILE="$AUDIT_DIR/metadata.env"

cat > "$META_FILE" <<META
task_id=$TASK_ID
base_branch=$BASE_BRANCH
current_branch=$CURRENT_BRANCH
timestamp_utc=$TIMESTAMP
max_review_rounds=2
max_auto_patch_commits=2
codex_max_attempts=$CODEX_MAX_ATTEMPTS
META

cat > "$SUMMARY_FILE" <<SUMMARY
# Fresh-Context Review Loop Summary

- Task: #$TASK_ID
- Branch: \`$CURRENT_BRANCH\`
- Base branch: \`$BASE_BRANCH\`
- Timestamp (UTC): \`$TIMESTAMP\`
- Max review rounds: \`2\`
- Max auto patch commits: \`2\`
- Codex max attempts per call: \`$CODEX_MAX_ATTEMPTS\`

## Rounds

SUMMARY

render_template() {
  local template_file="$1"
  local output_file="$2"
  local round="$3"
  local review_json_file="$4"
  local prior_review_file="$5"
  local rendered

  rendered="$(cat "$template_file")"
  rendered="$(printf '%s' "$rendered" | sed "s/{{TASK_ID}}/$(escape_sed "$TASK_ID")/g")"
  rendered="$(printf '%s' "$rendered" | sed "s/{{BASE_BRANCH}}/$(escape_sed "$BASE_BRANCH")/g")"
  rendered="$(printf '%s' "$rendered" | sed "s/{{ROUND}}/$(escape_sed "$round")/g")"
  rendered="$(printf '%s' "$rendered" | sed "s#{{REVIEW_JSON_FILE}}#$(escape_sed "$review_json_file")#g")"
  rendered="$(printf '%s' "$rendered" | sed "s#{{PRIOR_REVIEW_FILE}}#$(escape_sed "$prior_review_file")#g")"
  printf '%s\n' "$rendered" > "$output_file"
}

write_review_markdown() {
  local round="$1"
  local review_json="$2"
  local md_file="$3"

  {
    echo "# Task $TASK_ID Review Round r$round"
    echo
    echo "- Patch required: \`$(jq -r '.patch_required' "$review_json")\`"
    echo "- Repeat/churn signal: \`$(jq -r '.repeat_signal' "$review_json")\`"
    echo "- Summary: $(jq -r '.summary' "$review_json")"
    echo
    echo "## Findings"
    if [[ "$(jq '.findings | length' "$review_json")" -eq 0 ]]; then
      echo "- None."
    else
      jq -r '.findings[] | "- [\(.severity)] \(.id): \(.title) (\(.disposition)) | files: \((.files | if length == 0 then \"n/a\" else join(\", \") end))"' "$review_json"
    fi
    echo
    echo "## Deferred Follow-Ups"
    if [[ "$(jq '.deferred_followups | length' "$review_json")" -eq 0 ]]; then
      echo "- None."
    else
      jq -r '.deferred_followups[] | "- \(.title): \(.reason)"' "$review_json"
    fi
  } > "$md_file"
}

write_patch_markdown() {
  local round="$1"
  local patch_json="$2"
  local md_file="$3"

  {
    echo "# Task $TASK_ID Patch Round r$round"
    echo
    echo "- Applied: \`$(jq -r '.applied' "$patch_json")\`"
    echo "- Commit SHA: \`$(jq -r '.commit_sha' "$patch_json")\`"
    echo "- Commit message: \`$(jq -r '.commit_message' "$patch_json")\`"
    echo "- Summary: $(jq -r '.summary' "$patch_json")"
    echo
    echo "## Patched Finding IDs"
    if [[ "$(jq '.patched_finding_ids | length' "$patch_json")" -eq 0 ]]; then
      echo "- None."
    else
      jq -r '.patched_finding_ids[] | "- \(.)"' "$patch_json"
    fi
    echo
    echo "## Deferred Finding IDs"
    if [[ "$(jq '.deferred_finding_ids | length' "$patch_json")" -eq 0 ]]; then
      echo "- None."
    else
      jq -r '.deferred_finding_ids[] | "- \(.)"' "$patch_json"
    fi
  } > "$md_file"
}

validate_review_json() {
  local review_json="$1"

  jq -e '
    (.summary | type == "string" and length > 0) and
    (.patch_required | type == "boolean") and
    (.repeat_signal | type == "boolean") and
    (.findings | type == "array") and
    (.deferred_followups | type == "array") and
    (all(.findings[]?;
      (.id | type == "string" and length > 0) and
      (.severity | type == "string" and length > 0) and
      (.title | type == "string" and length > 0) and
      (.disposition | type == "string" and length > 0) and
      (.files | type == "array")
    )) and
    (all(.deferred_followups[]?;
      (.title | type == "string" and length > 0) and
      (.reason | type == "string" and length > 0)
    ))
  ' "$review_json" >/dev/null
}

validate_patch_json() {
  local patch_json="$1"

  jq -e '
    (.applied | type == "boolean") and
    (.commit_sha | type == "string") and
    (.commit_message | type == "string") and
    (.summary | type == "string" and length > 0) and
    (.patched_finding_ids | type == "array") and
    (.deferred_finding_ids | type == "array")
  ' "$patch_json" >/dev/null
}

review_log_has_transport_failure() {
  local review_log="$1"
  grep -Eiq 'network|connect|connection|timeout|timed out|unreachable|dns|socket|transport|rate limit|429|5[0-9]{2}|service unavailable|tls|handshake' "$review_log"
}

write_manual_review_prompt() {
  local round="$1"
  local reason="$2"
  local review_log="$3"
  local prompt_file="$AUDIT_DIR/task-${TASK_ID}-r${round}-manual-review-fallback.md"

  cat > "$prompt_file" <<PROMPT
Run a fresh-context review for Task #$TASK_ID.

Why this fallback prompt was generated:
- Automated fresh review failed: $reason

Repository context:
- Branch: $CURRENT_BRANCH
- Base: $BASE_BRANCH
- Task: #$TASK_ID
- Verify command: ${VERIFY_CMD:-"(none supplied)"}

Artifacts to inspect:
- Automated review prompt: task-${TASK_ID}-r${round}-review-prompt.md
- Automated review log: $(basename "$review_log")
- Fresh-loop summary: $(basename "$SUMMARY_FILE")

Required output:
1) summary
2) patch_required (boolean)
3) repeat_signal (boolean)
4) findings with severity/id/title/disposition/files
5) deferred follow-ups (title/reason)

If patch_required=true, patch notable findings on the same branch, re-run verification, and report commit SHA(s).
PROMPT

  printf '%s\n' "$prompt_file"
}

run_verify() {
  local round="$1"
  local verify_log="$AUDIT_DIR/task-${TASK_ID}-r${round}-verify.log"

  if [[ -z "$VERIFY_CMD" ]]; then
    echo "skipped" > "$verify_log"
    return 0
  fi

  set +e
  bash -lc "$VERIFY_CMD" > "$verify_log" 2>&1
  local verify_status=$?
  set -e

  if [[ $verify_status -ne 0 ]]; then
    echo "- r$round verify failed. See \`$(basename "$verify_log")\`" >> "$SUMMARY_FILE"
    echo "Verification failed for round r$round. See: $verify_log" >&2
    exit 1
  fi

  echo "- r$round verify passed. See \`$(basename "$verify_log")\`" >> "$SUMMARY_FILE"
}

run_review_round() {
  local round="$1"
  local prior_review_file="$2"
  local prompt_file="$AUDIT_DIR/task-${TASK_ID}-r${round}-review-prompt.md"
  local review_json="$AUDIT_DIR/task-${TASK_ID}-r${round}-review.json"
  local review_log="$AUDIT_DIR/task-${TASK_ID}-r${round}-review.log"
  local review_md="$AUDIT_DIR/task-${TASK_ID}-r${round}-review.md"
  local review_status
  local review_reason=""
  local fallback_prompt
  local attempt=1

  render_template "$REVIEW_TEMPLATE" "$prompt_file" "$round" "" "$prior_review_file"

  : > "$review_log"
  while [[ "$attempt" -le "$CODEX_MAX_ATTEMPTS" ]]; do
    echo "=== codex review attempt $attempt/$CODEX_MAX_ATTEMPTS ===" >> "$review_log"
    set +e
    codex exec \
      --ephemeral \
      --full-auto \
      --color never \
      -s read-only \
      --output-schema "$REVIEW_SCHEMA" \
      -o "$review_json" \
      "$(cat "$prompt_file")" >> "$review_log" 2>&1
    review_status=$?
    set -e

    if [[ "$review_status" -ne 0 ]]; then
      review_reason="codex review command failed with exit $review_status"
    elif [[ ! -s "$review_json" ]]; then
      review_reason="codex review JSON output is missing or empty"
    elif ! jq empty "$review_json" >/dev/null 2>&1; then
      review_reason="codex review JSON output is invalid"
    elif ! validate_review_json "$review_json"; then
      review_reason="codex review JSON failed required-field validation"
    else
      write_review_markdown "$round" "$review_json" "$review_md"
      echo "$review_json"
      return 0
    fi

    if review_log_has_transport_failure "$review_log"; then
      review_reason="$review_reason (transport/connectivity indicators found in review log)"
    fi

    if [[ "$attempt" -lt "$CODEX_MAX_ATTEMPTS" ]]; then
      sleep_seconds=$((attempt * 2))
      echo "Review round r$round attempt $attempt failed: $review_reason. Retrying in ${sleep_seconds}s..." >&2
      sleep "$sleep_seconds"
    fi
    attempt=$((attempt + 1))
  done

  fallback_prompt="$(write_manual_review_prompt "$round" "$review_reason" "$review_log")"
  echo "- r$round review automation failed: $review_reason" >> "$SUMMARY_FILE"
  echo "- r$round manual fallback prompt: \`$(basename "$fallback_prompt")\`" >> "$SUMMARY_FILE"
  echo "Fresh-context review automation failed for r$round: $review_reason" >&2
  echo "Use manual fallback prompt: $fallback_prompt" >&2
  exit 2
}

run_patch_round() {
  local round="$1"
  local review_json="$2"
  local prompt_file="$AUDIT_DIR/task-${TASK_ID}-r${round}-patch-prompt.md"
  local patch_json="$AUDIT_DIR/task-${TASK_ID}-r${round}-patch.json"
  local patch_log="$AUDIT_DIR/task-${TASK_ID}-r${round}-patch.log"
  local patch_md="$AUDIT_DIR/task-${TASK_ID}-r${round}-patch.md"
  local head_before
  local head_after
  local commits_added
  local latest_subject
  local patch_status
  local patch_attempt=1

  render_template "$PATCH_TEMPLATE" "$prompt_file" "$round" "$review_json" ""
  head_before="$(git rev-parse HEAD)"

  : > "$patch_log"
  while [[ "$patch_attempt" -le "$CODEX_MAX_ATTEMPTS" ]]; do
    echo "=== codex patch attempt $patch_attempt/$CODEX_MAX_ATTEMPTS ===" >> "$patch_log"
    set +e
    codex exec \
      --ephemeral \
      --full-auto \
      --color never \
      -s workspace-write \
      --output-schema "$PATCH_SCHEMA" \
      -o "$patch_json" \
      "$(cat "$prompt_file")" >> "$patch_log" 2>&1
    patch_status=$?
    set -e

    if [[ "$patch_status" -eq 0 ]]; then
      break
    fi

    if [[ "$patch_attempt" -lt "$CODEX_MAX_ATTEMPTS" ]]; then
      sleep_seconds=$((patch_attempt * 2))
      echo "Patch round r$round attempt $patch_attempt failed (exit $patch_status). Retrying in ${sleep_seconds}s..." >&2
      sleep "$sleep_seconds"
    fi
    patch_attempt=$((patch_attempt + 1))
  done

  if [[ "${patch_status:-1}" -ne 0 ]]; then
    echo "Patch round r$round failed after $CODEX_MAX_ATTEMPTS attempts. See: $patch_log" >&2
    exit 1
  fi

  if [[ ! -s "$patch_json" ]]; then
    echo "Patch round r$round produced empty JSON output. See: $patch_log" >&2
    exit 1
  fi
  if ! jq empty "$patch_json" >/dev/null 2>&1; then
    echo "Patch round r$round produced invalid JSON output. See: $patch_log" >&2
    exit 1
  fi
  if ! validate_patch_json "$patch_json"; then
    echo "Patch round r$round JSON failed required-field validation. See: $patch_log" >&2
    exit 1
  fi

  head_after="$(git rev-parse HEAD)"
  write_patch_markdown "$round" "$patch_json" "$patch_md"

  if [[ "$head_before" != "$head_after" ]]; then
    commits_added="$(git rev-list --count "$head_before..$head_after")"
    if [[ "$commits_added" -ne 1 ]]; then
      echo "Patch round r$round produced $commits_added commits; expected exactly 1." >&2
      exit 1
    fi

    latest_subject="$(git log -1 --pretty=%s)"
    if [[ "$latest_subject" != "fix(review-r${round}):"* ]]; then
      echo "Latest commit subject does not match required prefix fix(review-r${round}):" >&2
      echo "Found: $latest_subject" >&2
      exit 1
    fi

    echo "commit_added"
    return 0
  fi

  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Patch round r$round changed files but did not create a commit." >&2
    exit 1
  fi

  echo "no_commit"
}

REVIEW_ROUNDS=0
PATCH_COMMITS=0
REPEAT_SIGNAL="false"

REVIEW1_JSON="$(run_review_round 1 "")"
REVIEW_ROUNDS=1

PATCH_REQUIRED_R1="$(jq -r '.patch_required' "$REVIEW1_JSON")"
REPEAT_SIGNAL="$(jq -r '.repeat_signal' "$REVIEW1_JSON")"
echo "- r1 review complete: patch_required=\`$PATCH_REQUIRED_R1\`, repeat_signal=\`$REPEAT_SIGNAL\`" >> "$SUMMARY_FILE"

PATCH1_STATUS="no_patch"
if [[ "$PATCH_REQUIRED_R1" == "true" && "$PATCH_COMMITS" -lt 2 && "$REPEAT_SIGNAL" != "true" ]]; then
  PATCH1_STATUS="$(run_patch_round 1 "$REVIEW1_JSON")"
  echo "- r1 patch status: \`$PATCH1_STATUS\`" >> "$SUMMARY_FILE"
  if [[ "$PATCH1_STATUS" == "commit_added" ]]; then
    PATCH_COMMITS=$((PATCH_COMMITS + 1))
    run_verify 1
  fi
fi

if [[ "$PATCH1_STATUS" == "commit_added" && "$REVIEW_ROUNDS" -lt 2 ]]; then
  REVIEW2_JSON="$(run_review_round 2 "$REVIEW1_JSON")"
  REVIEW_ROUNDS=2
  PATCH_REQUIRED_R2="$(jq -r '.patch_required' "$REVIEW2_JSON")"
  REPEAT_SIGNAL_R2="$(jq -r '.repeat_signal' "$REVIEW2_JSON")"
  echo "- r2 review complete: patch_required=\`$PATCH_REQUIRED_R2\`, repeat_signal=\`$REPEAT_SIGNAL_R2\`" >> "$SUMMARY_FILE"

  if [[ "$PATCH_REQUIRED_R2" == "true" && "$PATCH_COMMITS" -lt 2 && "$REPEAT_SIGNAL_R2" != "true" ]]; then
    PATCH2_STATUS="$(run_patch_round 2 "$REVIEW2_JSON")"
    echo "- r2 patch status: \`$PATCH2_STATUS\`" >> "$SUMMARY_FILE"
    if [[ "$PATCH2_STATUS" == "commit_added" ]]; then
      PATCH_COMMITS=$((PATCH_COMMITS + 1))
      run_verify 2
    fi
  fi
fi

{
  echo
  echo "## Final State"
  echo
  echo "- Review rounds executed: \`$REVIEW_ROUNDS\`"
  echo "- Patch commits added: \`$PATCH_COMMITS\`"
  echo "- Audit directory: \`$AUDIT_DIR\`"
} >> "$SUMMARY_FILE"

echo "Fresh-context review loop complete."
echo "Summary: $SUMMARY_FILE"
