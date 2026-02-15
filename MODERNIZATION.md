# MODERNIZATION.md

Changes needed to align this project with the WORKFLOW.md / AGENTS.md design specification. These are not bugs — the project works as-is. These are improvements to bring it in line with the standard development workflow.

Prioritized roughly by impact.

---

## 1. Add a Test Suite (HIGH)

**Current state:** No pytest tests. Only `backend/test_setup.py` (a manual verification script).

**Target state:** Full pytest suite with `conftest.py`, transaction rollback per test, and coverage for all API endpoints.

**Steps:**
- Create `backend/tests/conftest.py` with test database session (transaction rollback pattern)
- Create `backend/tests/test_auth.py` — registration, login, token validation
- Create `backend/tests/test_documents.py` — upload, process, query, search, delete
- Create `backend/tests/test_messages.py` — chat history retrieval
- Add `pytest`, `httpx` (for `TestClient`), and `pytest-cov` to requirements
- TESTPLAN.md already defines the test cases

**Complexity:** Medium-High. Requires test database setup and mocking external APIs (OpenAI, Anthropic).

---

## 2. Migrate to Async (MEDIUM)

**Current state:** Synchronous SQLAlchemy with `psycopg2-binary`. All endpoints are `def`.

**Target state (per WORKFLOW.md):** Async SQLAlchemy with `asyncpg`. All endpoints are `async def`.

**Steps:**
- Replace `psycopg2-binary` with `asyncpg` in requirements
- Update `database.py` to use `create_async_engine`, `async_sessionmaker`, `AsyncSession`
- Update all endpoints from `def` to `async def`
- Update all service functions to be async
- Update `get_db` dependency to yield async sessions
- Update Alembic env.py for async migrations

**Complexity:** High. Touches every file in the backend. Should be done as a dedicated migration, not alongside feature work.

**Risk:** The synchronous codebase works correctly in production. Async migration could introduce subtle bugs. Only do this if there's a performance need or if starting fresh.

---

## 3. Switch to BIGINT Primary Keys (LOW)

**Current state:** All models use `Integer` primary keys.

**Target state (per WORKFLOW.md):** All models use `BigInteger` primary keys.

**Steps:**
- Create Alembic migration to alter column types from INTEGER to BIGINT
- Update model definitions to use `BigInteger`

**Complexity:** Low, but requires a migration on production data.

**Risk:** Minimal for a portfolio project. INTEGER handles up to ~2.1 billion rows which is more than sufficient.

---

## 4. Add Token Expiration (MEDIUM)

**Current state:** `access_token_expire_minutes = 0` (tokens never expire).

**Target state (per WORKFLOW.md):** Access token expires in 30 minutes. Refresh token flow for seamless re-auth.

**Steps:**
- Set `access_token_expire_minutes = 30` in config
- Add refresh token endpoint (`POST /api/auth/refresh`)
- Store refresh tokens (7-day expiry) — either in DB or as a second JWT
- Update frontend to handle 401 responses with automatic token refresh
- Add refresh token to login response

**Complexity:** Medium. Requires both backend and frontend changes.

---

## 5. Move Auth Tokens to httpOnly Cookies (MEDIUM)

**Current state:** JWT stored in `localStorage`, sent via `Authorization: Bearer` header.

**Target state (per WORKFLOW.md):** JWT stored in `httpOnly` cookies for XSS protection.

**Steps:**
- Backend: Set JWT as httpOnly cookie in login response
- Backend: Read JWT from cookie in `get_current_user` dependency
- Backend: Add CSRF protection (since cookies are sent automatically)
- Frontend: Remove `localStorage` token management
- Frontend: Remove `Authorization` header logic from API client
- Frontend: Add `credentials: "include"` to all fetch calls

**Complexity:** Medium. Auth flow changes across both backend and frontend.

**Trade-off:** httpOnly cookies are more secure against XSS but require CSRF protection and complicate cross-origin setups (Vercel → Render). Current Bearer token approach is simpler and standard for SPAs.

---

## 6. Add Background Processing (MEDIUM)

**Current state:** Document processing (PDF extraction, chunking, embedding) runs synchronously in the request handler. The client blocks until processing completes.

**Target state:** Background task processing so the upload returns immediately and processing happens asynchronously.

**Options:**
- Celery + Redis (heavyweight, standard)
- FastAPI `BackgroundTasks` (lightweight, built-in — loses work on restart)
- ARQ with Redis (lightweight async task queue)

**Steps:**
- Add task queue of choice
- Move `process_document_text` to a background worker
- Add WebSocket or polling endpoint for processing status updates
- Update frontend to poll for status changes

**Complexity:** Medium-High depending on queue choice.

---

## 7. Improve .gitignore (LOW)

**Current state:** `docs/` directory is gitignored. This means ARCHITECTURE.md, PATTERNS.md, and REVIEW_CHECKLIST.md are not tracked.

**Target state (per WORKFLOW.md):** `docs/` should be tracked. Only `TASKS.md` and `TESTPLAN.md` should be gitignored.

**Steps:**
- Remove `docs/` from `.gitignore`
- Add `TASKS.md` and `TESTPLAN.md` to `.gitignore` (TESTPLAN.md is already at root level)
- Commit the docs directory

**Complexity:** Trivial.

---

## 8. Add AI Review Log to README (LOW)

**Current state:** README.md has no AI Review Log section.

**Target state (per WORKFLOW.md):** README includes an "AI Review Log" section documenting instances where agent-generated code was reviewed and corrected.

**Steps:**
- Add `## AI Review Log` section to README.md
- Populate with any past examples of agent corrections

**Complexity:** Trivial.

---

## 9. Use Server Components Where Possible (LOW)

**Current state:** All Next.js pages are client components (`"use client"`). No server-side rendering or data fetching.

**Target state:** Landing page, login, and register pages could be server components. Only dashboard needs `"use client"`.

**Complexity:** Low. Mostly removing `"use client"` directives and adjusting data fetching patterns.

**Trade-off:** Current approach works fine. Server components would improve initial page load but add complexity to the auth flow.

---

## 10. Add Logging (LOW)

**Current state:** No structured logging. Some `print()` statements in `test_setup.py`.

**Target state (per WORKFLOW.md):** Python `logging` module throughout backend.

**Steps:**
- Configure `logging` in `main.py`
- Replace any `print()` with logger calls
- Add request logging middleware

**Complexity:** Low.

---

_This file is a backlog, not a sprint plan. Items should be pulled into TASKS.md when ready to implement._
