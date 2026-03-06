## Summary
Add stop and retry controls for streaming chat responses.

Parent Spec: #69

## Scope
**In scope:**
- `frontend/app/components/dashboard/ChatWindow.tsx`
- `frontend/lib/api.ts` (stream options/callback compatibility)
- Frontend tests for stream lifecycle and terminal states

**Out of scope:**
- Backend endpoint changes
- Analytics additions

## Acceptance Criteria
- [ ] Add `AbortController`-based cancel for active stream.
- [ ] Show `Stop` only while streaming is active.
- [ ] Add `Retry` for failed/stopped assistant responses by re-submitting the same query.
- [ ] Prevent duplicate placeholders and double-submit races.
- [ ] Preserve sources and pipeline meta rendering behavior.
- [ ] Stop halts token updates immediately and leaves a clear stopped state.
- [ ] Retry re-runs query and completes normally.
- [ ] No orphaned loading/streaming states.
- [ ] Tests cover `done`, `error`, `abort`, `unmount` transitions.

## Verification
```bash
make frontend-verify
```
