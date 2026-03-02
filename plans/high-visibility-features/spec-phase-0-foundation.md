## Summary

Foundation prerequisites that unblock the high-visibility feature work (streaming responses, PDF viewer, pipeline observability). Resolves remaining P2 audit items that naturally overlap with the streaming implementation path.

**Source:** `plans/high-visibility-features.md` Phase 0

## Scope

- Bump FastAPI to >=0.135.0 for first-class SSE support (`EventSourceResponse`, `ServerSentEvent`)
- Convert per-request AI client instantiation to lazy module-level singletons (audit P2-21)
- Close Spec #19 (all P0/P1 child tasks are merged)

## Non-goals

- No new features or endpoints in this phase
- No frontend changes
- No schema/migration changes

## Decision Locks

- **FastAPI target version:** >=0.135.0 (minimum for `fastapi.sse`). Pin to latest stable at time of implementation.
- **Singleton pattern:** Lazy module-level `_client` with `_get_client()` accessor. No dependency injection framework.

## Child Tasks

- [ ] Task: Bump FastAPI and verify compatibility
- [ ] Task: Singleton AI clients (P2-21)
- [ ] Task: Close Spec #19

## Verification

```bash
make backend-verify
```
