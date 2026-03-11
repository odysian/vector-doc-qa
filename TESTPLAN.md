# TESTPLAN.md

Test case definitions for Quaero. Tests are defined here before implementation. Each section maps to a feature domain.

**Status:** Pytest suite implemented in `backend/tests/`. 40 tests covering auth, documents, search, query, and messages. Uses `quaero_test` schema with transaction rollback per test. External APIs (OpenAI, Anthropic) mocked at the service function level.

---

## Feature: Authentication

### Happy Path

- POST /api/auth/register with valid username, email, password returns 201 and user object
- POST /api/auth/login with valid credentials returns 200 and JSON body with `csrf_token` (no auth tokens in body)
- POST /api/auth/refresh with valid refresh credential returns 200 and JSON body with `csrf_token` (no auth tokens in body)
- GET /api/auth/me with valid token returns current user data (including `is_demo`)
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
- Startup succeeds when `chunk_size > 0`, `chunk_overlap >= 0`, and `chunk_overlap < chunk_size`
- Startup succeeds when `chunk_size` and `chunk_overlap` are set at configured upper bounds

### Error Cases

- Strict environments fail startup when `SECRET_KEY` is a known dev/default value
- Strict environments fail startup when `SECRET_KEY` is too short or placeholder-shaped
- Strict environments fail startup when `DATABASE_URL` uses loopback host, default dev credentials, or default dev DB name
- Startup fails when `chunk_size <= 0`
- Startup fails when `chunk_overlap < 0`
- Startup fails when `chunk_overlap >= chunk_size`
- Startup fails when `chunk_size` exceeds configured max bound
- Startup fails when `chunk_overlap` exceeds configured max bound

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
- Returns 403 for demo account uploads
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
- POST /api/documents/{id}/query includes pipeline_meta timing/similarity fields including `chunks_above_threshold`, `similarity_spread`, and `chat_history_turns_included`
- POST /api/documents/{id}/query and `/query/stream` include optional `pipeline_meta` token fields when provider usage is available: `embedding_tokens`, `llm_input_tokens`, `llm_output_tokens`
- POST /api/documents/{id}/query/stream returns SSE events in order: sources -> token* -> meta -> done
- Answer includes cited chunks from the document
- User message and assistant response are saved to messages table
- Sources include similarity scores and chunk content
- Query and streaming query include a bounded recent conversation window (oldest -> newest ordering) for same-document follow-ups

### Error Cases

- Returns 404 if document does not exist or belongs to another user
- Returns 400 if document is not yet processed (status != COMPLETED) [?]
- Streaming query emits error event with generic detail on provider/database failures

### Edge Cases

- Query with no relevant chunks in document still returns a response
- Streaming failure after partial tokens still persists a terminal assistant message when DB is available
- Very short query (single word)
- Very long query (paragraph)
- History window trims older turns beyond configured bound
- Historical messages with legacy `pipeline_meta` payloads (without token fields) still deserialize
- Messages with token-enriched `pipeline_meta` payloads deserialize and return token fields intact

### Security Cases

- Rate limit: 10/hour shared bucket across /query and /query/stream per user
- Cannot query another user's documents
- Query/search/stream error logs include structured context only (IDs + error class) without raw exception-message interpolation
- External provider logs emit `external.call_completed`/`external.call_failed` events with provider/model/duration and usage counts where available

---

## Feature: Frontend Streaming Chat Lifecycle

### Happy Path

- `queryDocumentStream()` assembles SSE frames across multiple chunks and dispatches events in order (`sources` -> `token` -> `meta` -> `done`)
- ChatWindow send controls enter streaming state during an active stream and return to normal after `done`
- ChatWindow shows a `Stop` control only during active streaming and aborts stream updates when clicked
- ChatWindow `Retry` re-submits the same query after a stopped/failed assistant response and completes on `done`
- Debug mode toggle persists in localStorage (`quaero_debug_mode`) and gates retrieval metadata visibility
- When debug mode is on, assistant messages render pipeline metadata and citations render per-source similarity scores

### Error Cases

- `queryDocumentStream()` emits terminal fallback error when stream ends without `done`/`error`
- ChatWindow `error` event appends error text to the current assistant stream bubble without creating a second assistant bubble

### Edge Cases

- ChatWindow unmount aborts active stream and does not retain stale streaming state on cleanup
- ChatWindow blocks duplicate placeholder creation on rapid double-submit while a stream is already in flight

---

## Feature: Frontend Citation Precision v2 Spike

### Happy Path

- Clicking a citation source emits page + source snippet payload from ChatWindow
- PDF viewer scrolls to cited page and applies page-level highlight
- Viewer attempts text-layer snippet matching on cited page and applies transient text-level highlight on success

### Edge Cases

- If snippet matching fails, page-level citation highlight still works
- Matching handles punctuation/whitespace normalization between citation snippet and PDF text layer spans

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
- Dashboard shows demo-account banner and hides upload/delete controls when `GET /api/auth/me` returns `is_demo=true`
- Dashboard keeps upload/delete controls enabled for non-demo users
- Landing `Try Demo` logs in with demo credentials and routes directly to `/dashboard`
- Login form disables submit while request is in flight and re-enables after completion
- Login `Try Demo` shortcut submits `demo` credentials and redirects to `/dashboard` on success
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
- Assistant messages include sources (JSONB) and optional `pipeline_meta` for historical debug rendering

### Error Cases

- Returns 404 if document does not exist or belongs to another user
- Returns empty list for document with no messages

---

## Feature: Mini Eval Harness

### Happy Path

- Fixture loader validates shape and returns deterministic case ordering by `case_id`
- Fact matching reports expected hit/miss counts and recall
- Summary builder aggregates averages from successful cases only

### Error Cases

- Fixture loader raises clear errors for missing or invalid required fields
- Summary builder returns zeroed aggregates when all cases fail

---

## Feature: Document Deletion

### Happy Path

- DELETE /api/documents/{id} removes document, chunks, and messages
- File is removed from disk
- Returns 200 with success message

### Error Cases

- Returns 404 if document does not exist or belongs to another user
- Returns 403 for demo account deletes

### Edge Cases

- Deleting a document that is currently PROCESSING [?]

---

## Feature: Demo Seed Startup

### Happy Path

- Startup seed creates demo user (`username=demo`) when missing
- Demo user seed imports completed documents and chunks from fixture JSON when present
- All seeded documents are marked COMPLETED

### Error Cases

- Missing fixture file logs a warning and still creates demo user

### Edge Cases

- Seeding is idempotent (no duplicate demo user/documents on repeated startup)

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

## Feature: Workspace CRUD

### Happy Path

- POST /api/workspaces/ with valid name returns 201 and workspace object with `document_count: 0`
- GET /api/workspaces/ returns only the authenticated user's workspaces with document counts
- GET /api/workspaces/{id} returns workspace with full documents list
- PATCH /api/workspaces/{id} with valid name returns 200 and updated workspace
- DELETE /api/workspaces/{id} returns 200 and removes workspace

### Error Cases

- POST /api/workspaces/ returns 401 if not authenticated
- POST /api/workspaces/ returns 403 for demo user
- POST /api/workspaces/ returns 422 if name is empty
- POST /api/workspaces/ returns 422 if name exceeds 100 characters
- GET /api/workspaces/{id} returns 404 if workspace does not exist
- GET /api/workspaces/{id} returns 404 if workspace belongs to another user
- PATCH /api/workspaces/{id} returns 403 for demo user
- PATCH /api/workspaces/{id} returns 404 for non-existent or wrong-owner workspace
- DELETE /api/workspaces/{id} returns 403 for demo user
- DELETE /api/workspaces/{id} returns 404 for non-existent or wrong-owner workspace

### Edge Cases

- Workspace name with leading/trailing whitespace (should be stored as-is or trimmed — follow existing pattern)
- Creating multiple workspaces with the same name succeeds (names are not unique)
- Deleting a workspace cascades deletion of associated messages

### Security Cases

- Rate limit: workspace CRUD at 20/hour per user
- Cannot access another user's workspace via any endpoint

---

## Feature: Workspace Document Membership

### Happy Path

- POST /api/workspaces/{id}/documents with valid document_ids adds documents and returns updated workspace detail
- DELETE /api/workspaces/{id}/documents/{doc_id} removes document from workspace
- Adding a document already in the workspace is silently skipped (idempotent)
- Only COMPLETED documents can be added to a workspace

### Error Cases

- POST /api/workspaces/{id}/documents returns 400 if adding would exceed MAX_DOCUMENTS_PER_WORKSPACE (20)
- POST /api/workspaces/{id}/documents returns 403 for demo user
- POST /api/workspaces/{id}/documents returns 404 if workspace not found or wrong owner
- POST /api/workspaces/{id}/documents returns 404 if any document_id not found or not owned by user
- POST /api/workspaces/{id}/documents rejects documents that are not COMPLETED (PENDING/PROCESSING/FAILED)
- DELETE /api/workspaces/{id}/documents/{doc_id} returns 404 if document not in workspace

### Edge Cases

- Adding documents when workspace already has some (partial fill to limit)
- Removing a document from workspace preserves existing workspace chat history
- Document deleted entirely via DELETE /api/documents/{id} cascades removal from workspace_documents

---

## Feature: Cross-Document Query (Workspace RAG)

### Happy Path

- POST /api/workspaces/{id}/query returns answer with sources from multiple documents
- Sources include `document_id` and `document_filename` for each chunk
- Pipeline_meta includes timing and similarity fields matching single-doc query format
- User message and assistant response are saved to messages table with `workspace_id` (not `document_id`)
- LLM prompt includes document filename attribution in excerpt headers
- Workspace chat includes bounded recent conversation history for follow-up questions

### Error Cases

- POST /api/workspaces/{id}/query returns 400 if workspace has 0 documents
- POST /api/workspaces/{id}/query returns 404 if workspace not found or wrong owner
- POST /api/workspaces/{id}/query returns 401 if not authenticated

### Edge Cases

- Workspace with a single document returns results equivalent to single-doc query
- Query when some workspace documents have no chunks still returns results from chunked documents
- Sources are ranked by similarity regardless of which document they come from

### Security Cases

- Rate limit: 10/hour shared bucket with single-document /query and /query/stream per user
- Cannot query another user's workspace

---

## Feature: Workspace Chat History

### Happy Path

- GET /api/workspaces/{id}/messages returns all messages for a workspace ordered by created_at
- Assistant messages include sources (with document_id and document_filename) and optional pipeline_meta
- Messages have `workspace_id` set and `document_id` as null

### Error Cases

- Returns 404 if workspace not found or wrong owner
- Returns empty list for workspace with no messages

---

## Feature: Workspace Frontend

### Happy Path

- Sidebar toggle switches between Documents and Workspaces modes
- WorkspaceList renders workspace cards with name and document count
- Clicking a workspace enters workspace view with PDF viewer + chat
- Document switcher dropdown above PDF viewer lists workspace documents
- Clicking a document in sidebar or switcher changes the PDF viewer document
- Chat queries go to workspace query endpoint when in workspace mode
- Workspace chat history loads and displays on workspace entry
- Clicking a citation in workspace chat switches PDF viewer to source document and highlights page
- Citation cards show document filename alongside page number

### Error Cases

- Empty workspace shows "add documents" prompt and disables chat input
- Document removed from workspace while viewing switches viewer to next available doc

### Edge Cases

- Switching between Documents and Workspaces modes clears the other mode's selection
- Mobile tab layout (PDF / Chat toggle) works in workspace mode
- Demo user sees workspaces as read-only (create/modify/delete disabled)

---

## Feature: Message Schema Changes (Regression)

### Happy Path

- Existing single-document messages continue to work with nullable document_id (all existing rows have document_id set)
- Single-document chat is unaffected by workspace_id column addition
- MessageResponse includes both document_id and workspace_id fields

### Edge Cases

- CHECK constraint prevents creating a message with both document_id and workspace_id set
- CHECK constraint prevents creating a message with neither document_id nor workspace_id set

---

_[?] marks items needing clarification or investigation before test implementation._
