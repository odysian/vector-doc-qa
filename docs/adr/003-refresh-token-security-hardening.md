# ADR-003: Refresh Token Security Hardening (Code Review)

**Date:** 2026-02-18
**Status:** Applied
**Branch:** main (pre-httpOnly cookie migration)

---

## Context

### Background

The refresh token implementation used a DB-stored opaque token (`secrets.token_hex(32)`) with rotation on use. Code review before the httpOnly cookie migration identified four issues — two correctness gaps, one robustness issue, and one hard prerequisite for the cookie migration.

### Problem

Four independent defects were found:

| # | Issue | Severity |
|---|-------|----------|
| 1 | CORS wildcard (`allow_origins=["*"]`) with `allow_credentials=True` | Security / hard prerequisite |
| 2 | Non-atomic token rotation in `/refresh` | Correctness |
| 3 | Fragile timezone comparison on `expires_at` | Robustness |
| 4 | Unhandled `ValueError` in `get_current_user` | Robustness |

---

## Options Considered

Each issue had a straightforward fix. The decision was whether to apply all four before the cookie migration (keeping the migration diff minimal) or defer them to a follow-up. Deferring was rejected because Fix 1 is a hard prerequisite (cookies don't work without correct CORS) and Fix 2 would silently surface in the cookie flow.

---

## Decision

Apply all four fixes before starting the cookie migration.

### Fix 1 — CORS wildcard

`allow_origins=["*"]` with `allow_credentials=True` is invalid per the CORS spec. Browsers reject this combination silently — requests succeed when using Bearer tokens (no credentials in the CORS sense) but fail entirely with cookies. Added `frontend_url: str` to `Settings` and replaced the wildcard:

```python
# BEFORE
allow_origins=["*"]

# AFTER
allow_origins=[settings.frontend_url]
```

`FRONTEND_URL` is set to the Vercel deployment URL in Render's environment. Locally it defaults to `http://localhost:3000`.

**Files:** `app/config.py`, `app/main.py`, `.env.example`

### Fix 2 — Non-atomic token rotation

`create_refresh_token` committed internally, forcing two separate transactions in the `/refresh` endpoint — delete the consumed token (commit 1), then create the new token (commit 2 inside the helper). A crash between commits leaves the user with no valid session and no way to recover without re-login. This failure mode is realistic on Render's free tier.

**Root cause:** the helper owned its commit, preventing the caller from grouping operations atomically.

```python
# BEFORE — security.py
async def create_refresh_token(user_id: int, db: AsyncSession) -> str:
    db.add(RefreshToken(...))
    await db.commit()  # ← commits internally
    return raw_token

# BEFORE — auth.py refresh endpoint
await db.execute(delete(RefreshToken).where(...))
await db.commit()         # commit 1: delete
new_rt = await create_refresh_token(user_id, db)  # commit 2: insert

# AFTER — security.py: helper only stages, never commits
async def create_refresh_token(user_id: int, db: AsyncSession) -> str:
    db.add(RefreshToken(...))
    return raw_token  # caller is responsible for commit

# AFTER — auth.py: single atomic transaction
await db.execute(delete(RefreshToken).where(...))
new_rt = await create_refresh_token(user_id, db)
await db.commit()  # delete + insert succeed or both roll back
```

**Files:** `app/core/security.py`, `app/api/auth.py`

### Fix 3 — Fragile timezone comparison

```python
# BEFORE
if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
```

`DateTime(timezone=True)` with asyncpg returns an already-aware `datetime`. Calling `.replace(tzinfo=...)` on an aware datetime does not convert — it overwrites the `tzinfo` attribute. The comparison happened to be correct because asyncpg returns UTC-aware datetimes, making the `.replace()` a no-op. But if a test mock or driver change returned a naive datetime with a non-UTC offset, the comparison would silently produce a wrong answer (expired token passes as valid).

```python
# AFTER: check awareness before normalizing
expires_aware = (
    row.expires_at
    if row.expires_at.tzinfo is not None
    else row.expires_at.replace(tzinfo=timezone.utc)
)
if expires_aware < datetime.now(timezone.utc):
```

**File:** `app/core/security.py`

### Fix 4 — `ValueError` in `get_current_user`

```python
# BEFORE
user_id = decode_access_token(token)
if user_id is None:
    raise HTTPException(401, ...)
user = await get_user_by_id(db, int(user_id))  # ← ValueError if sub is non-numeric
```

A structurally valid JWT with a non-numeric `sub` claim (e.g. `"sub": "admin"`) passes signature verification and the `None` check, then raises an unhandled `ValueError` — returning 500 instead of 401. We control token minting so this can't happen in production, but a JWT with a valid signature and a malformed `sub` should 401, not 500.

```python
# AFTER
try:
    uid = int(user_id_str)
except ValueError:
    raise HTTPException(401, "Invalid authentication credentials")
```

**File:** `app/api/dependencies.py`

---

## Consequences

- CORS is now configured for the specific Vercel origin — the hard prerequisite for the cookie migration is met.
- Token rotation in `/refresh` is atomic: a crash during rotation never leaves a user session-less.
- Timezone comparison is defensive and behaves correctly regardless of driver behavior or test mocks.
- `get_current_user` returns 401 (not 500) for any JWT with a valid signature but a non-numeric `sub`.
- The general principle established for helpers: **stage work, let the caller own the commit**. This is documented in PATTERNS.md.
- No interface or behavioral changes from the user's perspective — all fixes are internal corrections.
- All 26 auth tests passed after the fixes were applied.
