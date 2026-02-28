# ADR-006: Remove Auth Tokens from Login/Refresh Response Bodies

**Date:** 2026-02-28
**Status:** Applied
**Branch:** task-20-remove-auth-token-response-body

---

## Context

### Background
The application uses cookie-based authentication for browser clients:
`access_token` and `refresh_token` are stored in httpOnly cookies, and
`csrf_token` is returned in JSON so cross-domain frontend code can persist it
in `localStorage` for the `X-CSRF-Token` header.

### Problem
`POST /api/auth/login` and `POST /api/auth/refresh` still serialized
`access_token` and `refresh_token` in JSON response bodies. This duplicated
sensitive credentials into JavaScript-readable responses even though the
runtime auth path already relies on httpOnly cookies.

### Root Cause (if a bug or production incident)
A backward-compatibility decision kept token fields in response bodies after
cookie-auth migration. That compatibility path became a security hardening gap
once browser clients no longer needed those fields.

---

## Options Considered

### Option A: Remove token fields with no legacy compatibility path
Remove `access_token` and `refresh_token` from login/refresh JSON bodies for
all clients, keep only browser-safe fields (`csrf_token`, `token_type`), and
continue cookie-based auth as the canonical flow.

**Accepted.** This closes the confidentiality gap with the smallest code
surface and no additional security exceptions.

### Option B: Feature-flag token-bearing responses
Keep old response fields behind a temporary feature flag.

**Rejected.** Adds configuration complexity and extends the period where token
leakage through JSON responses remains possible.

### Option C: Separate legacy endpoint that returns tokens
Keep current endpoints hardened and add explicit legacy endpoints for token
response bodies.

**Rejected.** Introduces parallel auth contracts and permanently increases
maintenance and attack surface for a non-goal in this task.

---

## Decision

1. `POST /api/auth/login` now returns only `{ csrf_token, token_type }`.
2. `POST /api/auth/refresh` now returns only `{ csrf_token, token_type }`.
3. Auth cookies are still set/rotated identically (`access_token`,
   `refresh_token`, `csrf_token` cookies).
4. Frontend auth types and callers now expect only CSRF/token-type payload
   fields.
5. Auth regression tests enforce that token fields are absent from login/refresh
   JSON responses while verifying cookie auth flow remains intact.

---

## Consequences

- Browser clients keep working without behavior changes because cookie transport
  remains the auth credential path.
- JSON response bodies no longer expose `access_token` and `refresh_token` to
  JavaScript.
- Legacy clients that depended on token fields in login/refresh response bodies
  must migrate to cookie-auth flow or another explicit auth contract.
- API documentation and tests must keep this response-shape contract enforced to
  prevent accidental regressions.
