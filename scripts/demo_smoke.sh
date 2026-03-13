#!/usr/bin/env bash
set -euo pipefail

# End-to-end smoke runner for demo auth, document query, streaming, and file fetch flows.
# Boundaries: talks only to public HTTP endpoints and validates cookie/CSRF + SSE contracts.
# Side effects: remote API calls and temporary local artifact files under a transient directory.

usage() {
  cat <<'USAGE'
Usage:
  API_BASE_URL=<https://api-host> DEMO_USERNAME=<user> DEMO_PASSWORD=<pass> bash scripts/demo_smoke.sh

Required environment variables:
  API_BASE_URL            Backend base URL (for example https://api.quaero.odysian.dev)
  DEMO_USERNAME           Demo account username
  DEMO_PASSWORD           Demo account password

Optional environment variables:
  SMOKE_DOCUMENT_ID       Document ID to test (defaults to first completed document from GET /api/documents/)
  SMOKE_QUERY             Non-stream query prompt
  STREAM_SMOKE_QUERY      Stream query prompt
  CURL_TIMEOUT_SECONDS    Per-request timeout for JSON endpoints (default: 45)
  STREAM_TIMEOUT_SECONDS  Per-request timeout for stream endpoint (default: 90)
  ALLOW_INSECURE_HTTP     Set to 1 to allow non-HTTPS API_BASE_URL
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  echo "Unexpected argument: $1"
  usage
  exit 1
fi

API_BASE_URL="${API_BASE_URL:-}"
DEMO_USERNAME="${DEMO_USERNAME:-}"
DEMO_PASSWORD="${DEMO_PASSWORD:-}"
SMOKE_DOCUMENT_ID="${SMOKE_DOCUMENT_ID:-}"
SMOKE_QUERY="${SMOKE_QUERY:-What is the main topic of this document?}"
STREAM_SMOKE_QUERY="${STREAM_SMOKE_QUERY:-Give a concise one-sentence summary with one source citation.}"
CURL_TIMEOUT_SECONDS="${CURL_TIMEOUT_SECONDS:-45}"
STREAM_TIMEOUT_SECONDS="${STREAM_TIMEOUT_SECONDS:-90}"
ALLOW_INSECURE_HTTP="${ALLOW_INSECURE_HTTP:-0}"

if ! command -v curl >/dev/null 2>&1; then
  echo "Missing required command: curl"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Missing required command: jq"
  exit 1
fi

if [[ -z "$API_BASE_URL" || -z "$DEMO_USERNAME" || -z "$DEMO_PASSWORD" ]]; then
  echo "Missing required environment variables."
  usage
  exit 1
fi

if [[ "$API_BASE_URL" != https://* && "$ALLOW_INSECURE_HTTP" != "1" ]]; then
  echo "Refusing non-HTTPS API_BASE_URL. Set ALLOW_INSECURE_HTTP=1 to override."
  exit 1
fi

API_BASE_URL="${API_BASE_URL%/}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cookie_jar="$tmp_dir/cookies.txt"

passes=0
failures=0
skipped=0
CURL_LAST_ERROR=""

pass() {
  local step="$1"
  passes=$((passes + 1))
  printf '[PASS] %s\n' "$step"
}

fail() {
  local step="$1"
  local detail="$2"
  failures=$((failures + 1))
  printf '[FAIL] %s -> %s\n' "$step" "$detail"
}

skip() {
  local step="$1"
  skipped=$((skipped + 1))
  printf '[SKIP] %s\n' "$step"
}

read_json_field() {
  local expression="$1"
  local file_path="$2"
  jq -r "$expression" "$file_path" 2>/dev/null || true
}

run_curl() {
  local status_var="$1"
  shift
  local status
  local err_file="$tmp_dir/curl.err"
  CURL_LAST_ERROR=""

  if status="$(curl -sS --connect-timeout 10 --max-time "$CURL_TIMEOUT_SECONDS" "$@" -w "%{http_code}" 2>"$err_file")"; then
    printf -v "$status_var" "%s" "$status"
    return
  fi

  CURL_LAST_ERROR="$(tr '\n' ' ' <"$err_file" | sed 's/[[:space:]]\+$//')"
  status="CURL_ERROR"
  printf -v "$status_var" "%s" "$status"
}

run_curl_stream() {
  local status_var="$1"
  shift
  local status
  local err_file="$tmp_dir/curl_stream.err"
  CURL_LAST_ERROR=""

  if status="$(curl -sS -N --connect-timeout 10 --max-time "$STREAM_TIMEOUT_SECONDS" "$@" -w "%{http_code}" 2>"$err_file")"; then
    printf -v "$status_var" "%s" "$status"
    return
  fi

  CURL_LAST_ERROR="$(tr '\n' ' ' <"$err_file" | sed 's/[[:space:]]\+$//')"
  status="CURL_ERROR"
  printf -v "$status_var" "%s" "$status"
}

echo "Running demo smoke checks against: $API_BASE_URL"

health_body="$tmp_dir/health.json"
run_curl health_status \
  -X GET \
  -o "$health_body" \
  "$API_BASE_URL/health"
if [[ "$health_status" == "200" && "$(read_json_field '.status // empty' "$health_body")" == "healthy" ]]; then
  pass "HEALTH GET /health"
else
  fail "HEALTH GET /health" "status=$health_status curl_error=${CURL_LAST_ERROR:-none} body=$(cat "$health_body" 2>/dev/null)"
fi

login_payload="$(jq -nc --arg username "$DEMO_USERNAME" --arg password "$DEMO_PASSWORD" '{username:$username,password:$password}')"
login_body="$tmp_dir/login.json"
run_curl login_status \
  -X POST \
  -H "Content-Type: application/json" \
  -d "$login_payload" \
  -b "$cookie_jar" \
  -c "$cookie_jar" \
  -o "$login_body" \
  "$API_BASE_URL/api/auth/login"

csrf_token=""
if [[ "$login_status" == "200" ]]; then
  csrf_token="$(read_json_field '.csrf_token // empty' "$login_body")"
fi

if [[ "$login_status" == "200" && -n "$csrf_token" ]]; then
  pass "AUTH LOGIN POST /api/auth/login"
else
  fail "AUTH LOGIN POST /api/auth/login" "status=$login_status curl_error=${CURL_LAST_ERROR:-none} body=$(cat "$login_body" 2>/dev/null)"
fi

if ! grep -q $'\taccess_token\t' "$cookie_jar" || ! grep -q $'\trefresh_token\t' "$cookie_jar"; then
  fail "AUTH COOKIES" "access_token and/or refresh_token not present after login"
else
  pass "AUTH COOKIES"
fi

me_body="$tmp_dir/me.json"
run_curl me_status \
  -X GET \
  -b "$cookie_jar" \
  -o "$me_body" \
  "$API_BASE_URL/api/auth/me"

me_username="$(read_json_field '.username // empty' "$me_body")"
if [[ "$me_status" == "200" && "$me_username" == "$DEMO_USERNAME" ]]; then
  pass "AUTH ME GET /api/auth/me"
else
  fail "AUTH ME GET /api/auth/me" "status=$me_status curl_error=${CURL_LAST_ERROR:-none} username=$me_username body=$(cat "$me_body" 2>/dev/null)"
fi

refresh_body="$tmp_dir/refresh.json"
run_curl refresh_status \
  -X POST \
  -H "X-CSRF-Token: $csrf_token" \
  -b "$cookie_jar" \
  -c "$cookie_jar" \
  -o "$refresh_body" \
  "$API_BASE_URL/api/auth/refresh"

if [[ "$refresh_status" == "200" ]]; then
  refreshed_csrf="$(read_json_field '.csrf_token // empty' "$refresh_body")"
  if [[ -n "$refreshed_csrf" ]]; then
    csrf_token="$refreshed_csrf"
  fi
  pass "AUTH REFRESH POST /api/auth/refresh"
else
  fail "AUTH REFRESH POST /api/auth/refresh" "status=$refresh_status curl_error=${CURL_LAST_ERROR:-none} body=$(cat "$refresh_body" 2>/dev/null)"
fi

docs_body="$tmp_dir/documents.json"
run_curl docs_status \
  -X GET \
  -b "$cookie_jar" \
  -o "$docs_body" \
  "$API_BASE_URL/api/documents/"

if [[ "$docs_status" != "200" ]]; then
  fail "DOCS LIST GET /api/documents/" "status=$docs_status curl_error=${CURL_LAST_ERROR:-none} body=$(cat "$docs_body" 2>/dev/null)"
else
  pass "DOCS LIST GET /api/documents/"
fi

document_id="$SMOKE_DOCUMENT_ID"
if [[ -z "$document_id" && "$docs_status" == "200" ]]; then
  document_id="$(read_json_field '.documents[] | select(.status == "completed") | .id' "$docs_body" | head -n1)"
fi

if [[ -z "$document_id" ]]; then
  fail "DOC SELECT" "No completed document found. Set SMOKE_DOCUMENT_ID to a completed document ID."
  skip "Document-dependent checks skipped: /status, /query, /query/stream, citation prereq, /file"
fi

if [[ -n "$document_id" ]]; then
  status_body="$tmp_dir/document_status.json"
  run_curl doc_status \
    -X GET \
    -b "$cookie_jar" \
    -o "$status_body" \
    "$API_BASE_URL/api/documents/${document_id}/status"

  doc_state="$(read_json_field '.status // empty' "$status_body")"
  if [[ "$doc_status" == "200" && "$doc_state" == "completed" ]]; then
    pass "DOC STATUS GET /api/documents/${document_id}/status"
  else
    fail "DOC STATUS GET /api/documents/${document_id}/status" "status=$doc_status curl_error=${CURL_LAST_ERROR:-none} doc_status=$doc_state body=$(cat "$status_body" 2>/dev/null)"
  fi
fi

query_body="$tmp_dir/query.json"
if [[ -n "$document_id" ]]; then
  query_payload="$(jq -nc --arg query "$SMOKE_QUERY" '{query:$query}')"
  run_curl query_status \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-CSRF-Token: $csrf_token" \
    -b "$cookie_jar" \
    -d "$query_payload" \
    -o "$query_body" \
    "$API_BASE_URL/api/documents/${document_id}/query"

  answer_len="$(read_json_field '.answer | length' "$query_body")"
  sources_count="$(read_json_field '.sources | length' "$query_body")"
  if [[ "$query_status" == "200" && "${answer_len:-0}" -gt 0 && "${sources_count:-0}" -gt 0 ]]; then
    pass "QUERY POST /api/documents/${document_id}/query"
  else
    fail "QUERY POST /api/documents/${document_id}/query" "status=$query_status curl_error=${CURL_LAST_ERROR:-none} answer_len=${answer_len:-0} sources=${sources_count:-0} body=$(cat "$query_body" 2>/dev/null)"
  fi

  page_sources_count="$(read_json_field '[.sources[] | select(.page_start != null or .page_end != null)] | length' "$query_body")"
  if [[ "${page_sources_count:-0}" -gt 0 ]]; then
    pass "CITATION PREREQ (query sources include page metadata)"
  else
    fail "CITATION PREREQ (query sources include page metadata)" "No source with page_start/page_end in query response"
  fi
fi

if [[ -n "$document_id" ]]; then
  stream_payload="$(jq -nc --arg query "$STREAM_SMOKE_QUERY" '{query:$query}')"
  stream_body="$tmp_dir/stream.sse"
  stream_headers="$tmp_dir/stream.headers"
  run_curl_stream stream_status \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-CSRF-Token: $csrf_token" \
    -b "$cookie_jar" \
    -d "$stream_payload" \
    -D "$stream_headers" \
    -o "$stream_body" \
    "$API_BASE_URL/api/documents/${document_id}/query/stream"

  stream_content_type="$(grep -i '^content-type:' "$stream_headers" | tail -n1 | cut -d' ' -f2- | tr -d '\r' || true)"
  token_events="$(grep -c '^event: token$' "$stream_body" || true)"
  sources_events="$(grep -c '^event: sources$' "$stream_body" || true)"
  meta_events="$(grep -c '^event: meta$' "$stream_body" || true)"
  done_events="$(grep -c '^event: done$' "$stream_body" || true)"
  error_events="$(grep -c '^event: error$' "$stream_body" || true)"

  # Require the full stream contract: sources + token + meta + done, with no error event.
  if [[ "$stream_status" == "200" ]] && [[ "$stream_content_type" == text/event-stream* ]] \
    && [[ "$sources_events" -gt 0 ]] && [[ "$token_events" -gt 0 ]] \
    && [[ "$meta_events" -gt 0 ]] && [[ "$done_events" -gt 0 ]] && [[ "$error_events" -eq 0 ]]; then
    pass "STREAM QUERY POST /api/documents/${document_id}/query/stream"
  else
    fail "STREAM QUERY POST /api/documents/${document_id}/query/stream" \
      "status=$stream_status curl_error=${CURL_LAST_ERROR:-none} content-type=$stream_content_type events(token=$token_events,sources=$sources_events,meta=$meta_events,done=$done_events,error=$error_events)"
  fi
fi

if [[ -n "$document_id" ]]; then
  pdf_file="$tmp_dir/document.pdf"
  pdf_headers="$tmp_dir/pdf.headers"
  run_curl pdf_status \
    -X GET \
    -b "$cookie_jar" \
    -D "$pdf_headers" \
    -o "$pdf_file" \
    "$API_BASE_URL/api/documents/${document_id}/file"

  pdf_content_type="$(grep -i '^content-type:' "$pdf_headers" | tail -n1 | cut -d' ' -f2- | tr -d '\r' || true)"
  pdf_magic="$(head -c 5 "$pdf_file" 2>/dev/null || true)"
  if [[ "$pdf_status" == "200" ]] && [[ "$pdf_content_type" == application/pdf* ]] && [[ "$pdf_magic" == "%PDF-" ]]; then
    pass "PDF FILE GET /api/documents/${document_id}/file"
  else
    fail "PDF FILE GET /api/documents/${document_id}/file" \
      "status=$pdf_status curl_error=${CURL_LAST_ERROR:-none} content-type=$pdf_content_type magic=$pdf_magic"
  fi
fi

if [[ "$failures" -gt 0 ]]; then
  echo "Smoke result: FAILED ($failures failure(s), $passes pass(es), $skipped skipped)."
  exit 1
fi

echo "Smoke result: PASSED ($passes checks, $skipped skipped)."
