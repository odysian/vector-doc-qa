## Summary

Add the streaming RAG query endpoint and pipeline timing instrumentation to the backend. Includes P2 audit fixes that are on the direct implementation path.

Parent Spec: #38

## What this delivers

1. `generate_answer_stream()` in `anthropic_service.py` — async generator yielding tokens from Claude's streaming API
2. `POST /api/documents/{document_id}/query/stream` — SSE endpoint using `EventSourceResponse`
3. Pipeline timing metadata (embed_ms, retrieval_ms, llm_ms, similarity scores)
4. Shared `_validate_document_for_query()` helper (fixes P2-9: no more eager chunk loading)
5. Clean error responses (fixes P2-8: no internal exception strings to clients)
6. Shared rate-limit scope between `/query` and `/query/stream`
7. `pipeline_meta` added to non-streaming `QueryResponse` schema

## SSE Event Protocol

| Event type | Data payload | When |
|---|---|---|
| `sources` | JSON array of `SearchResult` objects | After retrieval, before LLM call |
| `token` | Raw text string | Each token from Claude |
| `meta` | JSON `pipeline_meta` object | After last token, before DB save |
| `done` | `{"message_id": <int>}` | After assistant message saved |
| `error` | `{"detail": "..."}` | On any failure |

## DB Session Handling

Two-transaction pattern per Spec decision lock:
1. **Before stream:** Validate document, save user message, embed query, search chunks, commit. Releases DB session.
2. **After stream:** Open new `AsyncSessionLocal()` session, save assistant message with full answer + sources, commit.

## Acceptance Criteria

- [ ] `generate_answer_stream()` yields tokens from Anthropic streaming API using singleton client
- [ ] `/query/stream` endpoint returns `EventSourceResponse` with correct SSE event types
- [ ] Pipeline timing collected via `time.perf_counter()` and emitted as `meta` event
- [ ] `_validate_document_for_query()` uses lightweight existence check instead of `selectinload`
- [ ] Both `/query` and `/query/stream` share rate-limit scope `"query"`
- [ ] Existing `/query` endpoint updated: uses validation helper, returns `pipeline_meta`, no internal exception leakage
- [ ] Existing `/search` endpoint updated: uses validation helper, no internal exception leakage
- [ ] All existing tests pass (no behavior regression)
- [ ] New tests for streaming endpoint (at minimum: happy path, document not found, document not processed)
- [ ] `make backend-verify` passes

## Verification

```bash
make backend-verify
```

## Files in scope

- `backend/app/services/anthropic_service.py` — add `generate_answer_stream()`
- `backend/app/api/documents.py` — new endpoint, validation helper, fix existing endpoints
- `backend/app/schemas/query.py` — add `PipelineMeta` schema, update `QueryResponse`
- `backend/app/schemas/search.py` — add `similarity` to `SearchResult` if not present
- `backend/tests/` — new streaming endpoint tests

## Files explicitly out of scope

- Frontend code (separate task)
- Database migrations (none needed)
- `anthropic_service.py` `generate_answer()` (existing non-streaming method unchanged)

## Labels

`type:task`, `area:backend`
