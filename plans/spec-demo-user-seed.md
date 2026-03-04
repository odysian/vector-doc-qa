# Spec: Demo User with Pre-Seeded Documents

## Summary

Add a demo user account with 3 pre-processed documents so visitors can try the app immediately without creating an account. The demo documents also serve as the eval harness fixture baseline.

## Value / User Impact

- **Visitors** get a working demo in one click — no signup friction
- **Eval harness** becomes functional with real documents and embeddings
- **Smoke script** (PR #77) gets a stable demo account to test against
- **Interview demos** start from a known-good state every time

## In Scope

- Demo user account seeded on app startup (if not exists)
- 3 pre-processed documents with pre-computed embeddings baked into a fixture
- One-time export script to generate the fixture from a live database
- "Try Demo" button on login page with shared credentials
- Demo user restrictions: no upload, no delete
- Additional eval fixture case for The Tell-Tale Heart
- Banner/note for demo users explaining they need an account for uploads

## Out of Scope

- Per-user document seeding (every new user gets demo docs)
- Demo user admin panel or management UI
- Auto-reset/cleanup of demo user chat history
- Read-only enforcement on query endpoints (demo user can still ask questions, which creates message rows)

## Expected Behavior

1. On app startup, if no user with `username=demo` exists, create it with a known password and insert the 3 demo documents with their chunks and pre-computed embeddings.
2. Login page shows a "Try Demo" button that auto-fills demo credentials and submits.
3. Demo user sees 3 completed documents in their dashboard and can query any of them.
4. Upload and delete endpoints return 403 for the demo user.
5. A subtle banner tells demo users to create an account for full features.

## Backend Plan

### Task 1: Demo seed infrastructure

- Add `is_demo` boolean column to `users` table (default `false`), with Alembic migration
- Create `scripts/export_demo_fixtures.py` — queries a user's documents + chunks + embeddings and writes `scripts/fixtures/demo_seed_data.json`
- Create `app/services/demo_seed_service.py`:
  - On startup, check if demo user exists
  - If not, create user + documents + chunks with pre-computed embeddings from fixture
  - Use `get_password_hash("demo")` for the demo password
- Wire into FastAPI lifespan (after `init_db`)
- Guard upload endpoint: if `current_user.is_demo` → 403
- Guard delete endpoint: if `current_user.is_demo` → 403

### Task 2: Demo documents + fixture generation

- Upload and process 3 documents through the app manually:
  1. `acme-q4-report.pdf` (earnings report with Q4 revenue $5M, customer growth 12%)
  2. `security-policy-2025.pdf` (policy doc with 90-day password rotation)
  3. `the-tell-tale-heart.pdf` (Poe short story)
- Run `scripts/export_demo_fixtures.py` to capture the fixture
- Commit the fixture JSON to the repo
- Add Tell-Tale Heart eval case to `mini_eval_cases.json`

### Task 3: Frontend demo button + restrictions

- Add "Try Demo" button on login page
- On click: fill username="demo", password="demo", submit login form
- After login, if user `is_demo`:
  - Hide upload zone or show disabled state with tooltip
  - Hide delete button on documents
  - Show subtle banner: "You're using a demo account. Create an account to upload your own documents."
- Requires `is_demo` field in `/api/auth/me` response (add to `UserResponse` schema)

## Files Expected

### Backend
- `alembic/versions/xxx_add_is_demo_to_users.py` (migration)
- `app/models/user.py` (add `is_demo` column)
- `app/schemas/user.py` (add `is_demo` to `UserResponse`)
- `app/services/demo_seed_service.py` (new)
- `app/main.py` (wire seed into lifespan)
- `app/api/documents.py` (upload/delete guards)
- `scripts/export_demo_fixtures.py` (new)
- `scripts/fixtures/demo_seed_data.json` (new, generated)
- `scripts/fixtures/mini_eval_cases.json` (add case-004)
- `backend/tests/test_demo_seed.py` (new)
- `backend/tests/test_documents.py` (add demo restriction tests)

### Frontend
- `app/login/page.tsx` (demo button)
- `app/components/dashboard/UploadZone.tsx` (disabled state for demo)
- `app/components/dashboard/DocumentList.tsx` (hide delete for demo)
- `app/dashboard/page.tsx` (demo banner)
- `lib/api.types.ts` (add `is_demo` to User type)

## Tests / Regression Notes

- Seed service: creates user + documents + chunks when demo user missing
- Seed service: skips when demo user already exists (idempotent)
- Upload endpoint: returns 403 for demo user
- Delete endpoint: returns 403 for demo user
- Query endpoint: works normally for demo user
- Login with demo credentials: succeeds
- Eval harness: all 4 cases pass with seeded documents

## Decision Locks

- Demo password is `demo` (plaintext in frontend, hashed in DB). Acceptable for a portfolio demo — not a production pattern.
- Pre-computed embeddings committed to repo as JSON. File will be ~2-5MB depending on chunk count. Acceptable for a portfolio project.
- `is_demo` is a DB column, not a config flag. Simpler to query and enforce in endpoints.

## Acceptance Criteria

- [ ] Demo user auto-created on startup with 3 completed documents
- [ ] "Try Demo" button on login page works end-to-end
- [ ] Demo user cannot upload or delete documents (403)
- [ ] Demo user can query documents and see streaming responses
- [ ] Demo banner visible with account creation prompt
- [ ] Eval harness passes all 4 cases against demo documents
- [ ] Smoke script passes with demo credentials
- [ ] `make backend-verify` and `make frontend-verify` pass

## Verification

```bash
make backend-verify
make frontend-verify
make backend-mini-eval  # all 4 cases should pass
```
