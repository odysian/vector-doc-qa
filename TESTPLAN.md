# TESTPLAN.md

Test case definitions for Quaero. Tests are defined here before implementation. Each section maps to a feature domain.

**Status:** This project currently has no pytest test suite. Only `backend/test_setup.py` (a setup verification script) exists. All sections below are pending implementation.

---

## Feature: Authentication

### Happy Path

- POST /api/auth/register with valid username, email, password returns 201 and user object
- POST /api/auth/login with valid credentials returns 200 and JWT token
- GET /api/auth/me with valid token returns current user data
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

### Security Cases

- Rate limit: register limited to 3/hour per IP
- Rate limit: login limited to 5/minute per IP
- Token cannot be decoded with wrong secret key

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

- POST /api/documents/{id}/process on PENDING document sets status to PROCESSING then COMPLETED
- Document text is extracted and split into chunks (1000 chars, 50 overlap)
- Chunks are stored with embeddings in the database
- Chunk count is reasonable for document size

### Error Cases

- Returns 404 if document does not exist
- Returns 404 if document belongs to another user
- Returns 400 if document is already COMPLETED
- Returns 400 if document is currently PROCESSING
- Processing a corrupt/empty PDF sets status to FAILED with error message

### Edge Cases

- Processing a FAILED document retries successfully
- Very large PDF (many pages) completes within timeout
- PDF with no extractable text (scanned image) [?]

---

## Feature: Document Query (RAG)

### Happy Path

- POST /api/documents/{id}/query with valid query returns answer with sources
- Answer includes cited chunks from the document
- User message and assistant response are saved to messages table
- Sources include similarity scores and chunk content

### Error Cases

- Returns 404 if document does not exist or belongs to another user
- Returns 400 if document is not yet processed (status != COMPLETED) [?]

### Edge Cases

- Query with no relevant chunks in document still returns a response
- Very short query (single word)
- Very long query (paragraph)

### Security Cases

- Rate limit: 10/hour per user
- Cannot query another user's documents

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
