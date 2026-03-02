## Goal
Remove `access_token` and `refresh_token` from login/refresh JSON bodies for browser cookie-auth flow while preserving session behavior through httpOnly cookies + CSRF token.
Default: this Task should represent the entire feature end-to-end unless split criteria apply.

## Scope
**In:**
- Update backend auth response schema/handlers to stop returning bearer tokens in JSON body.
- Keep CSRF token return path required for cross-domain frontend.
- Update frontend API types/calls to align with new response contract.
- Add regression tests for login/refresh/logout/me flows under cookie auth.

**Out:**
- Full auth system redesign.
- Non-browser API auth strategy beyond agreed compatibility path.

## Implementation notes
- Parent Spec: #19
- Legacy compatibility lock resolved: no feature flag and no legacy token-bearing endpoint for login/refresh responses.
- Final auth response shape lock resolved: login/refresh return `{ csrf_token, token_type }` only.
- Ensure sensitive tokens are not serialized in response payloads after change.
- Merged implementation: PR #27 (`Closes #20`), merged on 2026-02-28.

## Decision locks (backend-coupled only)
- [x] Locked: Legacy compatibility approach (none, feature flag, or separate legacy endpoint).
- [x] Locked: Final auth response shape for login/refresh.

## Acceptance criteria
- [x] `POST /api/auth/login` no longer returns `access_token` or `refresh_token` in JSON body.
- [x] `POST /api/auth/refresh` no longer returns `access_token` or `refresh_token` in JSON body.
- [x] Auth cookies continue to be set/rotated correctly.
- [x] Frontend login/refresh/session flows still function using cookie transport + stored CSRF token.
- [x] Automated tests verify token fields are absent from JSON responses.

## Verification
```bash
make backend-verify
make frontend-verify
cd backend && .venv/bin/pytest -v tests/test_auth.py
```

## PR checklist
- [x] PR references this issue (`Closes #20`)
- [x] Docs updated if needed (`docs/ARCHITECTURE.md`, `docs/PATTERNS.md`, `docs/REVIEW_CHECKLIST.md`, `docs/ISSUES_WORKFLOW.md`, `TESTPLAN.md`, `docs/adr/`)
- [x] Tests added/updated where needed
