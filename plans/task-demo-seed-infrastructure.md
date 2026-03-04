## Summary

Add demo user seed infrastructure: `is_demo` column, startup seeding from a pre-computed fixture, and upload/delete endpoint restrictions.

Parent Spec: #79

## Scope

**In scope:**
- Alembic migration adding `is_demo` boolean to `users` table
- `demo_seed_service.py` that creates demo user + documents + chunks + embeddings from fixture on startup
- Wire seed service into FastAPI lifespan
- Upload endpoint returns 403 for demo user
- Delete endpoint returns 403 for demo user
- `is_demo` field added to `UserResponse` schema and `/api/auth/me`
- `export_demo_fixtures.py` script for one-time fixture generation
- Unit tests for seed service and endpoint restrictions

**Out of scope:**
- Frontend changes (separate task)
- Actual demo document PDFs and fixture data (separate task)
- Eval fixture updates (separate task)

## Files

- `alembic/versions/xxx_add_is_demo_to_users.py`
- `app/models/user.py`
- `app/schemas/user.py`
- `app/services/demo_seed_service.py` (new)
- `app/main.py`
- `app/api/documents.py`
- `scripts/export_demo_fixtures.py` (new)
- `backend/tests/test_demo_seed.py` (new)
- `backend/tests/test_documents.py` (add demo restriction tests)

## Acceptance Criteria

- [ ] `is_demo` column exists on `users` table with migration
- [ ] Startup seeds demo user + documents + chunks from fixture when user missing
- [ ] Startup is idempotent (skips if demo user exists)
- [ ] `POST /api/documents/upload` returns 403 for demo user
- [ ] `DELETE /api/documents/{id}` returns 403 for demo user
- [ ] `GET /api/auth/me` includes `is_demo` field
- [ ] `export_demo_fixtures.py` exports user's docs/chunks/embeddings to JSON
- [ ] Tests cover seed, skip-if-exists, upload 403, delete 403

## Verification

```bash
make backend-verify
```
