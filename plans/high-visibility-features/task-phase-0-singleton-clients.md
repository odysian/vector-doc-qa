## Summary

Convert per-request `AsyncOpenAI` and `AsyncAnthropic` client instantiation to lazy module-level singletons. Resolves audit item P2-21.

Parent Spec: #35

## Why

Both `embedding_service.py` (lines 20, 67) and `anthropic_service.py` (line 62) create new SDK clients on every request. This adds avoidable connection/TLS setup overhead. The streaming feature (Phase 1) will add another Anthropic client call site — fix the pattern once before adding more.

## Acceptance Criteria

- [ ] `embedding_service.py`: single `AsyncOpenAI` instance reused across calls
- [ ] `anthropic_service.py`: single `AsyncAnthropic` instance reused across calls
- [ ] Pattern: lazy module-level `_client` with `_get_client()` accessor function
- [ ] No behavior change — all existing tests pass
- [ ] No new dependencies

## Implementation

```python
# Pattern for each service module
_client: AsyncOpenAI | None = None

def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client
```

Replace all `client = AsyncOpenAI(...)` / `client = AsyncAnthropic(...)` calls with `_get_client()`.

## Verification

```bash
make backend-verify
```

## Files in scope

- `backend/app/services/embedding_service.py`
- `backend/app/services/anthropic_service.py`

## Labels

`type:task`, `area:backend`
