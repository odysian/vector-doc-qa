# TESTPLAN.md

Test case definitions for Quaero. Tests are defined here before implementation. Each section maps to a feature domain.

**Status:** Pytest suite implemented in `backend/tests/`. 37 tests covering auth, documents, search, query, and messages. Uses `quaero_test` schema with transaction rollback per test. External APIs (OpenAI, Anthropic) mocked at the service function level.

---

## Feature: Authentication

### Happy Path

- POST /api/auth/register with valid username, email, password returns 201 and user object
- POST /api/auth/login with valid credentials returns 200 and JSON body with `csrf_token` (no auth tokens in body)
- POST /api/auth/refresh with valid refresh credential returns 200 and JSON body with `csrf_token` (no auth tokens in body)
- GET /api/auth/me with valid token returns current user data
- GET /api/auth/csrf returns `csrf_token` for authenticated cookie sessions
- Password is hashed (not stored as plaintext) in database

### Error Cases

- Register returns 422 if username is missing
- Register returns 422 if email is invalid format
- Register returns 422 if password is missing
- Register returns 400 if username already exists
- Register returns 400 if email already exists
- Login returns 401 if username does not exist
- Login returns 401 if password is incorrect
- GET /api/auth/me returns 401 if no token provided
- GET /api/auth/me returns 401 if token is invalid/malformed

### Edge Cases

- Username with leading/trailing whitespace [?] (currently no trim)
- Very long password (128+ chars) is handled
- Email with valid but unusual format (plus addressing, etc.)
- Concurrent POST `/api/auth/refresh` requests using the same refresh token allow at most one success
- Reusing a consumed refresh token is rejected with 401

### Security Cases

- Rate limit: register limited to 3/hour per IP
- Rate limit: login limited to 5/minute per IP
- Rate-limit IP identity uses `X-Forwarded-For` only when the direct peer is in `trusted_proxy_ips`
- Untrusted peers cannot influence rate-limit identity via forwarded-header spoofing
- Spoofing a whitelisted IP in forwarded headers does not bypass limits
- Authenticated rate-limit keys still resolve to `user:<id>` (Bearer and cookie fallback)
- Token cannot be decoded with wrong secret key
- Refresh rotation keeps a single route-level transaction boundary (no helper-side commits)

---

## Feature: Runtime Config Guardrails

### Happy Path

- Strict environments (`APP_ENV=production` or similar) start successfully with a strong `SECRET_KEY` and non-dev `DATABASE_URL`

### Error Cases

- Strict environments fail startup when `SECRET_KEY` is a known dev/default value
- Strict environments fail startup when `SECRET_KEY` is too short or placeholder-shaped
- Strict environments fail startup when `DATABASE_URL` uses loopback host, default dev credentials, or default dev DB name

### Edge Cases

- Local/dev/test environments remain bootable with intentional local defaults
- `APP_ENV` matching is case-insensitive (`Production` still enforces strict guardrails)

---

## Feature: Health Endpoint Redaction

### Happy Path

- GET `/health` returns 200 with `status=healthy` and `database=connected` when DB check succeeds
- Health payload includes `max_file_size_mb` for operational visibility
- Health payload does not expose filesystem path fields (`upload_dir`)

### Error Cases

- GET `/health` returns 503 with `status=unhealthy` and `database=error` when DB check fails
- Unhealthy payload still omits filesystem path fields (`upload_dir`)

---

## Feature: Document Upload

### Happy Path

- POST /api/documents/upload with valid PDF returns 201 and document object with status PENDING
- Uploaded file is saved to disk in uploads directory
- Document record includes correct filename, file_size, user_id

### Error Cases

- Returns 401 if not authenticated
- Returns 400 if file is not a PDF (wrong extension)
- Returns 400 if file has .pdf extension but wrong magic bytes (not a real PDF)
- Returns 400 if file exceeds 10MB size limit

### Edge Cases

- PDF with unicode characters in filename
- Very small PDF (< 1KB)
- PDF filename with spaces and special characters

### Security Cases

- Rate limit: 5/hour per user
- File is validated by magic bytes, not just extension
- Path traversal in filename is prevented (sanitized)
- Uploaded file belongs to authenticated user only

---

## Feature: Document Processing

### Happy Path

- POST /api/documents/upload enqueues a background processing job and returns immediately
- POST /api/documents/{id}/process enqueues processing and returns 202 Accepted
- Background worker moves status PENDING -> PROCESSING -> COMPLETED
- Document text is extracted and split into chunks (1000 chars, 50 overlap)
- Chunks are stored with embeddings in the database
- Chunk count is reasonable for document size

### Error Cases

- Returns 404 if document does not exist
- Returns 404 if document belongs to another user
- Returns 400 if document is already COMPLETED
- Returns 400 if document is currently PROCESSING
- Upload returns 503 and sets status FAILED if queueing fails
- Processing a corrupt/empty PDF sets status to FAILED with error message
- Failure after chunk `flush()` rolls back uncommitted chunk rows and persists `FAILED` status/error
- Batch embedding generation fails fast if any chunk text is empty/whitespace (no silent filtering)

### Edge Cases

- Processing a FAILED document retries successfully
- Retrying with pre-existing chunks rebuilds a single canonical chunk set (no duplicates)
- Failed processing attempt does not leave partial chunk rows committed
- Embedding batch output count/order must match input chunk count/order exactly; mismatch fails processing
- GET /api/documents/{id}/status reflects status transitions until terminal state
- Very large PDF (many pages) completes within timeout
- PDF with no extractable text (scanned image) [?]

---

## Feature: Document Query (RAG)

### Happy Path

- POST /api/documents/{id}/query with valid query returns answer with sources
- POST /api/documents/{id}/query includes pipeline_meta timing/similarity fields
- POST /api/documents/{id}/query/stream returns SSE events in order: sources -> token* -> meta -> done
- Answer includes cited chunks from the document
- User message and assistant response are saved to messages table
- Sources include similarity scores and chunk content

### Error Cases

- Returns 404 if document does not exist or belongs to another user
- Returns 400 if document is not yet processed (status != COMPLETED) [?]
- Streaming query emits error event with generic detail on provider/database failures

### Edge Cases

- Query with no relevant chunks in document still returns a response
- Streaming failure after partial tokens still persists a terminal assistant message when DB is available
- Very short query (single word)
- Very long query (paragraph)

### Security Cases

- Rate limit: 10/hour shared bucket across /query and /query/stream per user
- Cannot query another user's documents

---

## Feature: Frontend Streaming Chat Lifecycle

### Happy Path

- `queryDocumentStream()` assembles SSE frames across multiple chunks and dispatches events in order (`sources` -> `token` -> `meta` -> `done`)
- ChatWindow send controls enter streaming state during an active stream and return to normal after `done`

### Error Cases

- `queryDocumentStream()` emits terminal fallback error when stream ends without `done`/`error`
- ChatWindow `error` event appends error text to the current assistant stream bubble without creating a second assistant bubble

### Edge Cases

- ChatWindow unmount aborts active stream and does not retain stale streaming state on cleanup

---

## Feature: Frontend Auth and Dashboard Regression

### Happy Path

- `apiRequest()` retries the original request once after a successful refresh (`401 -> /auth/refresh -> retry`)
- `queryDocumentStream()` throws a typed `SessionExpiredError` when refresh fails during stream setup
- Dashboard loads the document list successfully and renders document rows
- Dashboard renders the empty-state message when the document list is empty
- Dashboard upload success path calls upload API and reloads the document list
- Dashboard process trigger path calls process API and reloads the document list
- Dashboard delete success path calls delete API and reloads the document list
- Dashboard route boundary redirects to `/login` when API calls surface `SessionExpiredError`
- Login form disables submit while request is in flight and re-enables after completion
- Register form disables submit while request is in flight and re-enables after completion

### Error Cases

- `apiRequest()` refresh failure clears client auth storage and throws typed `SessionExpiredError` (no API-client redirect side effect)
- Dashboard shows API error text when initial document load fails
- Login shows API error text after failed submit
- Register shows API error text after failed submit

---

## Feature: Document Search

### Happy Path

- POST /api/documents/{id}/search returns ranked chunks by similarity
- Results respect top_k parameter
- Similarity scores are between 0 and 1

### Error Cases

- Returns 404 if document does not exist or belongs to another user

---

## Feature: Chat History

### Happy Path

- GET /api/documents/{id}/messages returns all messages for a document
- Messages are ordered by created_at
- Assistant messages include sources (JSONB)

### Error Cases

- Returns 404 if document does not exist or belongs to another user
- Returns empty list for document with no messages

---

## Feature: Document Deletion

### Happy Path

- DELETE /api/documents/{id} removes document, chunks, and messages
- File is removed from disk
- Returns 200 with success message

### Error Cases

- Returns 404 if document does not exist or belongs to another user

### Edge Cases

- Deleting a document that is currently PROCESSING [?]

---

## Feature: Document List

### Happy Path

- GET /api/documents/ returns only the authenticated user's documents
- Response includes total count
- Documents include all fields (status, filename, etc.)

### Error Cases

- Returns 401 if not authenticated
- Returns empty list for user with no documents

---

_[?] marks items needing clarification or investigation before test implementation._
