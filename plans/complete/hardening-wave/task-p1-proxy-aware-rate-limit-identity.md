## Goal
Make rate-limit identity derivation accurate behind trusted reverse proxies so limits apply per real client/user, not per proxy hop.
Default: this Task should represent the entire feature end-to-end unless split criteria apply.

## Scope
**In:**
- Update backend/proxy trust configuration for client IP derivation.
- Ensure rate-limit key functions use trusted client identity safely.
- Add tests and/or integration assertions for proxied requests.

**Out:**
- Replacing SlowAPI.
- Global traffic-shaping redesign.

## Implementation notes
- Parent Spec: #19
- Avoid blindly trusting forwarded headers from untrusted sources.
- Keep user-ID-based limits intact for authenticated flows.

## Decision locks (backend-coupled only)
- [ ] Locked: Trusted proxy boundary (which hops/headers are authoritative).
- [ ] Locked: Uvicorn/app middleware strategy for proxy headers.

## Acceptance criteria
- [ ] Rate-limit key derivation correctly resolves real client identity behind trusted proxy.
- [ ] Header spoofing from untrusted sources does not bypass controls.
- [ ] Existing user-authenticated limit behavior remains intact.
- [ ] Regression tests cover proxied and non-proxied request paths.

## Verification
```bash
make backend-verify
cd backend && .venv/bin/pytest -v tests/test_auth.py tests/test_documents.py
```

## PR checklist
- [ ] PR references this issue (`Closes #...`)
- [ ] Docs updated if needed (`docs/ARCHITECTURE.md`, `docs/PATTERNS.md`, `docs/REVIEW_CHECKLIST.md`, `docs/ISSUES_WORKFLOW.md`, `TESTPLAN.md`, `docs/adr/`)
- [ ] Tests added/updated where needed
