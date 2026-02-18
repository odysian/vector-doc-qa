# Refresh Token Cleanup

Four issues found during code review of the refresh token implementation. Two are
robustness/defensive issues. One is a real correctness gap. One is a hard
prerequisite for the future httpOnly cookie migration.

Each section documents the problem, the before/after code, and the reasoning —
useful as interview talking points for demonstrating code review and security awareness.

**Status: All four fixes applied (2026-02-18).**

---

## Priority order

| # | Issue | Severity | Cookie relevance | Status |
|---|-------|----------|------------------|--------|
| 1 | CORS wildcard | Security / must-fix | **Hard prerequisite** — cookies don't work without this | Applied |
| 2 | Atomicity gap in `/refresh` | Correctness | Surfaces same way in cookie flow | Applied |
| 3 | Fragile timezone comparison | Robustness | Backend-only; no cookie impact | Applied |
| 4 | `ValueError` in `get_current_user` | Robustness | Backend-only; no cookie impact | Applied |

---

## Fix 1 — CORS wildcard (Applied)

**Files changed:** `backend/app/config.py`, `backend/app/main.py`, `backend/.env.example`

### The problem

```python
# BEFORE — backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # wildcard
    allow_credentials=True,   # + credentials
    ...
)
```

The combination of `allow_origins=["*"]` and `allow_credentials=True` is
rejected by browsers. The [CORS spec](https://fetch.spec.whatwg.org/#cors-protocol-and-credentials)
explicitly forbids reflecting a wildcard origin when the request includes
credentials. FastAPI/Starlette don't catch this misconfiguration — they emit
`Access-Control-Allow-Origin: *` and the browser silently drops it.

Right now this doesn't surface because Bearer tokens are sent via an explicit
`Authorization` header, which is not a "credentialed request" in the CORS sense.
But any credentialed request (cookies) will silently fail.

This is also item 5 on the security checklist: "CORS restricted to specific
frontend origin (no wildcard in production)."

### What was changed

**`backend/app/config.py`** — added `frontend_url` setting with local default:

```python
class Settings(BaseSettings):
    ...
    frontend_url: str = "http://localhost:3000"
```

**`backend/app/main.py`** — replaced wildcard with config value:

```python
# AFTER
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],  # specific origin from config
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**`backend/.env.example`** — added the variable so it's documented:

```
FRONTEND_URL=https://your-app.vercel.app
```

On Render, `FRONTEND_URL` is set to the actual Vercel deployment URL.
Locally, the default `http://localhost:3000` applies automatically.

### Why it matters for cookies

With httpOnly cookies, every request is credentialed by definition — the browser
sends the cookie automatically. `allow_origins` must name the exact frontend
origin or the browser will block the response before JS ever sees it. Without
this fix, the entire cookie migration is dead on arrival.

### Interview talking point

This is a good example of a misconfiguration that works silently in development
(Bearer tokens bypass CORS credential rules) but would break completely in
production when switching to cookies. The CORS spec is counterintuitive here —
`"*"` with credentials doesn't mean "allow all origins with credentials", it
means "invalid configuration, silently fail."

---

## Fix 2 — Atomicity gap in the refresh endpoint (Applied)

**Files changed:** `backend/app/core/security.py`, `backend/app/api/auth.py`

### The problem

The refresh endpoint performed two separate database commits:

```python
# BEFORE — auth.py refresh endpoint

# Commit 1: delete the consumed token
await db.execute(delete(RefreshToken).where(RefreshToken.id == row.id))
await db.commit()

# Commit 2: create new token (commits internally inside create_refresh_token)
access_token = create_access_token(data={"sub": str(user_id)})
new_refresh_token = await create_refresh_token(user_id, db)
```

```python
# BEFORE — security.py create_refresh_token

async def create_refresh_token(user_id: int, db: AsyncSession) -> str:
    ...
    db.add(RefreshToken(...))
    await db.commit()  # ← commits inside the helper
    return raw_token
```

If the process crashes between commit 1 and commit 2, the consumed token is
gone and no new token was issued. The user loses their session and must re-login.
This is a real failure mode on Render's free tier (which restarts regularly).

The root cause: `create_refresh_token` owns its own commit, preventing the
caller from grouping the delete and insert into a single atomic transaction.

### What was changed

**`backend/app/core/security.py`** — removed the internal commit. The helper
now only stages the row; the caller commits:

```python
# AFTER
async def create_refresh_token(user_id: int, db: AsyncSession) -> str:
    """
    Stage a new refresh token row. Does NOT commit — caller is responsible.

    This keeps the caller in control of transaction boundaries, which matters
    for the refresh endpoint where the delete and insert must be atomic.
    """
    from app.models.refresh_token import RefreshToken

    raw_token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    db.add(RefreshToken(user_id=user_id, token=raw_token, expires_at=expires_at))
    return raw_token
```

**`backend/app/api/auth.py` — `login` endpoint:** Added explicit commit after
staging (previously relied on `create_refresh_token` committing for it):

```python
# AFTER
access_token = create_access_token(data={"sub": str(db_user.id)})
refresh_token = await create_refresh_token(db_user.id, db)
await db.commit()  # caller commits — one transaction for the whole login
```

**`backend/app/api/auth.py` — `refresh` endpoint:** Delete and insert in a
single transaction:

```python
# AFTER
# Rotation: delete consumed token and stage new one in the same transaction
await db.execute(delete(RefreshToken).where(RefreshToken.id == row.id))
new_refresh_token = await create_refresh_token(user_id, db)
await db.commit()  # single commit — both operations succeed or both roll back

access_token = create_access_token(data={"sub": str(user_id)})
```

### What was intentionally left alone

`validate_refresh_token` also calls `await db.commit()` when it deletes an
expired token during validation. That commit is fine — it's a standalone cleanup
operation, not part of a multi-step sequence.

### Interview talking point

This demonstrates understanding of transaction boundaries in async Python. The
key insight: helper functions that call `db.commit()` internally prevent callers
from composing multiple operations atomically. The fix is a general principle —
helpers stage work, callers own the commit. This is especially relevant on
platforms like Render's free tier where process restarts are frequent.

---

## Fix 3 — Fragile timezone comparison (Applied)

**File changed:** `backend/app/core/security.py`

### The problem

```python
# BEFORE
if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
```

`DateTime(timezone=True)` with the asyncpg driver returns a **timezone-aware**
`datetime`. Calling `.replace(tzinfo=timezone.utc)` on an already-aware datetime
does not convert — it replaces the `tzinfo` attribute in place, bypassing any
offset conversion logic.

This happens to produce the correct result right now because PostgreSQL stores
the value in UTC and asyncpg returns it as UTC-aware. The `.replace()` call
is effectively a no-op. But if the driver changes (or a test mock returns a
naive datetime), the comparison silently produces a wrong answer — an expired
token could compare as valid if the tzinfo was something other than UTC.

### What was changed

Check whether the datetime is naive before deciding how to make it aware:

```python
# AFTER
# Make expires_at timezone-aware if the driver returned a naive datetime.
# DateTime(timezone=True) with asyncpg should always return aware, but
# .replace() on an already-aware value is wrong if tzinfo != UTC.
expires_aware = (
    row.expires_at
    if row.expires_at.tzinfo is not None
    else row.expires_at.replace(tzinfo=timezone.utc)
)
if expires_aware < datetime.now(timezone.utc):
    await db.execute(delete(RefreshToken).where(RefreshToken.id == row.id))
    await db.commit()
    return None
```

Explicit about intent: if we already have an aware datetime, use it as-is; if
the driver gave us a naive one (shouldn't happen, but might in tests), treat
it as UTC.

### Interview talking point

Demonstrates understanding of Python's datetime pitfalls. `.replace(tzinfo=...)`
is not `.astimezone()` — it doesn't convert, it overwrites. This is a common
source of subtle timezone bugs. The fix is a defensive pattern: check awareness
first, then decide how to normalize.

---

## Fix 4 — `ValueError` in `get_current_user` (Applied)

**File changed:** `backend/app/api/dependencies.py`

### The problem

```python
# BEFORE
user_id = decode_access_token(token)
if user_id is None:
    raise HTTPException(...)

user = await get_user_by_id(db, int(user_id))  # ← can raise ValueError
```

`decode_access_token` returns the `sub` claim as a raw string, or `None` if the
token is invalid. The `None` case is caught. But if a token is structurally valid
(passes JWT signature verification) yet carries a non-numeric `sub` — e.g.
`"sub": "admin"` — then `int(user_id)` raises an unhandled `ValueError` and the
endpoint returns a 500 instead of a 401.

We control token minting and always store `str(db_user.id)` in `sub`, so this
can't happen from our own login flow. But it's a correctness issue: a
structurally-valid but semantically-wrong token should return 401, not 500.

### What was changed

```python
# AFTER
user_id_str = decode_access_token(token)
if user_id_str is None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

# Convert to int — a structurally valid JWT with a non-numeric sub
# should return 401, not an unhandled 500 from ValueError.
try:
    uid = int(user_id_str)
except ValueError:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

user = await get_user_by_id(db, uid)
```

### Interview talking point

This is defensive coding at a trust boundary. Even though we control token
minting, the JWT `sub` claim is external input once it leaves the server. A
crafted token with `"sub": "admin"` passes signature verification (if the
attacker has the secret) but shouldn't crash the app. The principle: never
trust deserialized data to have the right type, even if you wrote the
serializer.

---

## Verification results

All four fixes applied and verified (2026-02-18):

- `ruff check .` — all changed files pass clean
- `pytest -v` — all 26 auth tests pass
- No interface or behavioral changes — purely internal corrections

---

## What these fixes unlock for the cookie migration

After this cleanup, the state of the system is:

| Concern | State |
|---------|-------|
| CORS configured for specific origin | Done |
| Refresh token rotation is atomic | Done |
| Timezone handling is explicit | Done |
| `get_current_user` is defensively typed | Done |

The cookie migration (MODERNIZATION.md §5) then becomes a focused,
well-scoped change:

1. **Backend `login` and `refresh`**: Set `Set-Cookie` response headers instead
   of (or in addition to) returning tokens in the JSON body. The DB-stored
   refresh token row is unchanged — only the transport changes.

2. **Backend `get_current_user`**: Switch from `HTTPBearer` → read
   `request.cookies.get("access_token")`. The `decode_access_token` and
   ownership check logic are unchanged.

3. **Backend `logout`**: In addition to deleting the DB row, clear the cookies
   in the response.

4. **Frontend `api.ts`**: Remove `getToken`, `getRefreshToken`, `saveTokens`,
   `clearTokens`, the `Authorization` header construction, and the
   `refreshPromise` single-flight lock. Add `credentials: "include"` to all
   fetch calls.

5. **CSRF protection**: The one genuinely new piece of work. The standard
   approach is the double-submit cookie pattern: a non-httpOnly `csrf_token`
   cookie (readable by JS) that must also be sent as a custom request header
   (`X-CSRF-Token`). The backend verifies the header matches the cookie on any
   state-changing request. This is straightforward to add but is a new concept
   and should be designed carefully.

The fixes in this document didn't change any interfaces or external behavior —
they were purely internal corrections. The cookie migration is where the API
contract changes.
