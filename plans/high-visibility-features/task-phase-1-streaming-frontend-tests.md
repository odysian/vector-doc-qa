## Summary

Add automated frontend tests for the streaming chat lifecycle to lock in the SSE behavior shipped in Task #40 and prevent regressions during remaining Phase 1 work.

Parent Spec: #38
Depends on: Task #40 (streaming frontend implementation)

## What this delivers

1. Frontend test harness for component/unit tests in `frontend/` (if absent)
2. SSE parser tests for `queryDocumentStream()` event/frame handling
3. ChatWindow lifecycle tests for `done`, `error`, unexpected stream close, and abort/unmount behavior
4. Regression guard for single streaming assistant bubble behavior

## Acceptance Criteria

- [ ] Frontend test runner is configured and runnable in CI/dev
- [ ] `queryDocumentStream()` test covers multi-chunk frame assembly and event dispatch order (`sources` -> `token` -> `meta` -> `done`)
- [ ] `queryDocumentStream()` test covers terminal fallback when stream ends unexpectedly (no `done`/`error` frame)
- [ ] ChatWindow test confirms send controls disable while streaming and re-enable on `done`
- [ ] ChatWindow test confirms `error` event appends error text without duplicating assistant bubbles
- [ ] ChatWindow test confirms abort/unmount does not leave stale streaming state
- [ ] `make frontend-verify` passes
- [ ] New frontend test command passes locally

## Implementation Notes

- Keep tests focused on streaming state transitions and SSE parsing; avoid snapshot-heavy UI tests.
- Prefer mocking `fetch` + `ReadableStream` directly for parser coverage.
- For ChatWindow behavior, use React Testing Library style interactions and assert rendered message/state changes.
- If adding new test dependencies, follow repo rule: request approval before package installation.

## Verification

```bash
make frontend-verify
# plus the new frontend test command introduced by this task
```

## Files in scope

- `frontend/lib/api.ts`
- `frontend/app/components/dashboard/ChatWindow.tsx`
- `frontend/package.json`
- `frontend/*test*` setup/config files
- `frontend/**/__tests__/**` or equivalent test directories

## Files explicitly out of scope

- Backend streaming endpoint implementation
- PDF viewer phase work
- Broader frontend visual redesign

## Labels

`type:task`, `area:frontend`, `quality`
