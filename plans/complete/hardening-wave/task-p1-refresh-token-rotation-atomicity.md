## Goal
Make refresh-token rotation race-safe and fully atomic under concurrent refresh attempts.
Default: this Task should represent the entire feature end-to-end unless split criteria apply.

## Scope
**In:**
- Update refresh flow so a consumed refresh token can produce at most one new token pair.
- Ensure helper/service transaction ownership is coherent (no helper-side surprise commits).
- Add concurrency-focused tests for refresh endpoint behavior.

**Out:**
- Changing broader token model/lifetimes.
- Session UI behavior changes.

## Implementation notes
- Parent Spec: #19
- Candidate approaches:
  - `SELECT ... FOR UPDATE` lock + rotate in one transaction.
  - Single-statement consume pattern using `DELETE ... RETURNING` gate.
- Resolve helper transaction ownership in the same change (`validate_refresh_token` should not commit independently if endpoint owns the transaction).

## Decision locks (backend-coupled only)
- [ ] Locked: Atomic consume implementation strategy.
- [ ] Locked: `validate_refresh_token` contract is lookup/delete-only with **no helper-side commit**.

## Acceptance criteria
- [ ] Concurrent refresh requests using the same refresh token cannot both succeed.
- [ ] Only one new refresh token is minted per consumed token.
- [ ] Expired/invalid tokens remain rejected with stable semantics.
- [ ] No helper-level commits violate endpoint transaction boundaries.
- [ ] Refresh-path transaction behavior is documented and test-covered (including consumed-token reuse).
- [ ] Tests cover concurrency and token reuse edge cases.

## Verification
```bash
make backend-verify
cd backend && .venv/bin/pytest -v tests/test_auth.py
```

## PR checklist
- [ ] PR references this issue (`Closes #...`)
- [ ] Docs updated if needed (`docs/ARCHITECTURE.md`, `docs/PATTERNS.md`, `docs/REVIEW_CHECKLIST.md`, `docs/ISSUES_WORKFLOW.md`, `TESTPLAN.md`, `docs/adr/`)
- [ ] Tests added/updated where needed
