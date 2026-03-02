## Summary

Bump `fastapi` from `0.128.0` to `>=0.135.0` in `backend/requirements.txt` to gain first-class SSE support needed for streaming RAG responses.

Parent Spec: #35

## Why

FastAPI 0.135.0 added `fastapi.sse.EventSourceResponse` and `ServerSentEvent` with:
- POST support (browser `EventSource` is GET-only; our query endpoint is POST)
- Pydantic model auto-serialization in SSE `data` fields
- Typed event names via `ServerSentEvent(data=..., event="token")`
- Auto keep-alive pings every 15s (prevents proxy/LB connection kills)
- Auto `Cache-Control: no-cache` and `X-Accel-Buffering: no` headers

Without this, streaming would require manual SSE frame formatting over `StreamingResponse`.

## Acceptance Criteria

- [ ] `fastapi` version in `requirements.txt` is `>=0.135.0`
- [ ] Review FastAPI changelog for breaking changes between 0.128.0 and target version
- [ ] All existing tests pass (`pytest -v`)
- [ ] Lint passes (`ruff check .`)
- [ ] Type check passes (`mypy . --ignore-missing-imports`)
- [ ] Security check passes (`bandit -r app/ -ll`)
- [ ] `from fastapi.sse import EventSourceResponse, ServerSentEvent` imports successfully

## Verification

```bash
cd backend
pip install -r requirements.txt
make backend-verify
python -c "from fastapi.sse import EventSourceResponse, ServerSentEvent; print('SSE imports OK')"
```

## Files in scope

- `backend/requirements.txt`

## Labels

`type:task`, `area:backend`
