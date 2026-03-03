## Summary

Add high-value, low-brittleness frontend regression tests for core user flows that must remain stable through upcoming PDF viewer/frontend rework.

Parent Spec: #38
Depends on: Task #48 (streaming frontend test coverage)

## What this delivers

1. API client auth/refresh regression tests for core request retry behavior
2. Dashboard flow tests for document list state and key mutation paths (upload/delete/process trigger behavior via mocked API)
3. Login/register page behavior tests for submit-state and error rendering
4. Guardrails to keep tests resilient to UI refactors (behavior-first assertions, no snapshots)

## Acceptance Criteria

- [ ] `apiRequest()` 401 -> refresh -> retry path is covered in frontend tests
- [ ] `apiRequest()` refresh failure path is covered (session-expired behavior)
- [ ] Dashboard document-list behavior is covered for load success/error and empty state
- [ ] Dashboard mutation behavior is covered for upload success path and delete success path
- [ ] Auth form behavior is covered for submit disable/enable and API-error display
- [ ] New tests avoid snapshot-heavy assertions and focus on user-visible behavior/state transitions
- [ ] `make frontend-verify` passes with the expanded suite

## Implementation Notes

- Prioritize tests that protect contracts and lifecycle behavior over fragile styling/layout details.
- Use React Testing Library interactions and mock API boundaries (`lib/api.ts`) for page/component tests.
- Keep selectors semantic (`role`, visible text, labels) to reduce churn during UI refactors.

## Verification

```bash
make frontend-verify
```

## Files in scope

- `frontend/lib/api.ts` and `frontend/lib/__tests__/`
- `frontend/app/dashboard/page.tsx` and dashboard component tests
- `frontend/app/login/page.tsx` tests
- `frontend/app/register/page.tsx` tests
- Test setup/util files as needed

## Files explicitly out of scope

- PDF viewer implementation details (Phase 2)
- Visual styling assertions and snapshot baselines
- Backend endpoint changes

## Labels

`type:task`, `area:frontend`
