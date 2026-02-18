# ADR-001: Cross-Domain CSRF — Split Token Delivery

**Date:** 2026-02-18
**Status:** Accepted
**Branch:** main

---

## Context

### Architecture

The app is deployed across two separate domains:

- **Frontend:** `*.vercel.app` (Next.js)
- **Backend:** `*.onrender.com` (FastAPI)

Authentication uses httpOnly cookies (`access_token`, `refresh_token`) set by the backend, with CSRF protection via the double-submit cookie pattern: the backend also sets a non-httpOnly `csrf_token` cookie that the frontend is expected to read via `document.cookie` and echo back as the `X-CSRF-Token` request header.

### Problem

After deploying the httpOnly cookie auth branch to production, all mutating requests (including login retries) began returning:

```json
{"detail": "CSRF token missing"}
```

The `csrf_token` cookie *was* visible in DevTools under the backend's domain — confirming the backend set it correctly and the browser stored it. But the frontend was never sending the `X-CSRF-Token` header.

### Root Cause

The double-submit pattern as implemented assumes the frontend can read the CSRF cookie via `document.cookie`. This works in same-origin deployments (e.g. both on `localhost`), but **fails cross-domain**.

When the backend (`onrender.com`) sets a cookie, the browser stores it under the `onrender.com` origin. When the frontend JS on `vercel.app` calls `document.cookie`, it only sees cookies belonging to `vercel.app`. The `csrf_token` cookie is invisible to `document.cookie` on the frontend domain.

The browser *does* send the cookie automatically on cross-origin requests (because `credentials: "include"` and `SameSite=None; Secure` are configured). So:

- `csrf_token` cookie: **present** in the request (browser auto-sends it to `onrender.com`)
- `X-CSRF-Token` header: **absent** (frontend JS couldn't read the cookie to set it)
- Result: `cookie_csrf` is set, `header_csrf` is `None` → **403 CSRF token missing**

### Secondary Issue: Login Deadlock

The `verify_csrf` dependency skips CSRF validation when no `access_token` cookie is present (Bearer auth path). However, a user with a stale `access_token` cookie from a previous session triggers the CSRF check on the login endpoint itself. Since `localStorage` is also empty at that point, no CSRF token is available, and login returns 403. This creates a deadlock — the user cannot log in to obtain a fresh CSRF token.

---

## Options Considered

### Option A: Next.js Rewrites (Proxy)

Configure `next.config.ts` to rewrite `/api/*` requests to the backend. This makes both frontend and API appear same-origin to the browser, so cookies set by the proxied backend are readable by the frontend.

**Rejected.** Vercel serverless functions proxy requests synchronously. PDF processing and embedding generation can exceed the 10-second Vercel timeout on free/hobby plans, causing 504s on long operations.

### Option B: Custom Domain

Place both frontend and backend under the same parent domain (e.g. `quaero.app` and `api.quaero.app`). Set cookies with `Domain=quaero.app` so the frontend JS can read them.

**Not chosen now.** Requires purchasing a domain and DNS/CDN configuration. Valid long-term option but out of scope for this fix.

### Option C: Split Token Delivery (Chosen)

Return the CSRF token in the JSON response body on login and refresh, in addition to setting it as a cookie. The frontend stores this value in `localStorage` and reads it from there instead of `document.cookie`.

**Accepted.** `localStorage` is not automatically sent by the browser on cross-origin requests, so the double-submit guarantee is preserved — an attacker cannot forge the `X-CSRF-Token` header without JS execution on the origin. The actual session credentials (`access_token`, `refresh_token`) remain in httpOnly cookies, so XSS cannot steal them. Storing the CSRF token in `localStorage` is consistent with OWASP guidance for cross-origin deployments.

---

## Decision

Implement the split-token delivery pattern:

1. The backend generates the CSRF token value before calling `set_auth_cookies`, so the same value can be returned in the response body.
2. The `Token` schema gains a `csrf_token: str` field.
3. Login and refresh routes return `csrf_token` in the JSON body alongside the existing `access_token` and `refresh_token` fields.
4. The frontend's `saveTokens()` (currently a no-op) is restored to write `csrf_token` to `localStorage`.
5. `getCsrfToken()` reads from `localStorage` instead of `document.cookie`.
6. `isLoggedIn()` checks for the `localStorage` entry instead of the cookie.
7. `clearTokens()` removes `csrf_token` from `localStorage`.
8. `doRefresh()` parses the refresh response and calls `saveTokens()` to keep the token current after rotation.

Additionally, to break the login deadlock:

9. `verify_csrf` exempts `/api/auth/login` and `/api/auth/register`. These endpoints are credential-gated (require username + password), so CSRF is not a meaningful threat vector — an attacker cannot forge a login request on behalf of the victim without the victim's password. The exemption is path-based and does not affect any authenticated endpoint.

---

## Consequences

- CSRF protection remains fully enforced on all authenticated state-mutating endpoints.
- Login and register are exempt from CSRF (acceptable — they are not authenticated actions).
- The `csrf_token` cookie is still set on the response for potential future same-origin clients or debugging visibility.
- `localStorage` is readable by JS: XSS can read the CSRF token and make authenticated requests. However, XSS cannot steal the httpOnly `access_token` or `refresh_token` — the session credentials are still protected. The CSRF token alone is insufficient to impersonate a user without the accompanying httpOnly cookies.
- If `localStorage` is cleared while cookies persist, `isLoggedIn()` returns `false`, redirecting the user to login, which now succeeds without CSRF (exemption from point 9).
- The `access_token` and `refresh_token` fields remain in the response body for backward compatibility with Swagger UI and any non-cookie clients.
