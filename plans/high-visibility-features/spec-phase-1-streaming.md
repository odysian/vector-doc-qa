## Summary

Add streaming RAG responses and pipeline observability metadata to Quaero. Users see answers stream token-by-token in real time (like ChatGPT), with per-query timing and retrieval quality metrics displayed in the chat UI.

**Source:** `plans/high-visibility-features.md` Phase 1

## Scope

**Backend:**
- New `generate_answer_stream` service method using Anthropic streaming API
- New `POST /api/documents/{document_id}/query/stream` SSE endpoint
- Pipeline timing instrumentation (`embed_ms`, `retrieval_ms`, `llm_ms`, similarity scores)
- Shared document validation helper — replaces eager chunk loading (audit P2-9)
- Clean error handling — no internal exception strings to clients (audit P2-8)
- Shared rate-limit scope between `/query` and `/query/stream`
- Add `pipeline_meta` to non-streaming `QueryResponse` for consistency

**Frontend:**
- SSE consumer in `lib/api.ts` using `fetch` + `ReadableStream` (not `EventSource`)
- ChatWindow streaming UI with token-by-token rendering
- Pipeline meta display component (expandable timing breakdown)
- `PipelineMeta` TypeScript type

## Non-goals

- No new database tables or schema changes
- No prompt versioning or A/B testing
- No thumbs up/down feedback (deferred)
- No conversation continuity (Phase 3 candidate)

## Decision Locks

- **SSE event protocol:** `sources` -> `token` (N) -> `meta` -> `done` (or `error` at any point)
- **DB session handling:** Two-transaction pattern. Commit user message + search results before entering stream generator. Save assistant message in a separate session after stream completes. Tradeoff: crash between stream and save loses the DB record, but user already saw the answer. Alternative (one session for whole stream) risks connection pool exhaustion.
- **Rate limiting:** Both `/query` and `/query/stream` use `scope="query"` so they share one 10/hour bucket per user. Prevents bypass by switching endpoints.
- **Non-streaming endpoint kept:** Existing `POST /query` stays for tests, non-browser clients, and fallback. Gets `pipeline_meta` added to its response.
- **Frontend SSE parsing:** Use `fetch` + `ReadableStream`, not browser `EventSource`. Reason: `EventSource` doesn't support POST requests or custom headers (needed for CSRF token).

## Child Tasks

- [ ] Task: Streaming backend (endpoint + service + P2 fixes)
- [ ] Task: Streaming frontend (SSE consumer + ChatWindow + pipeline meta UI)
- [ ] Task: Streaming frontend test coverage (SSE parser + stream lifecycle regression tests)
- [ ] Task: High-value frontend regression tests (#50) (core auth/dashboard API-contract hardening ahead of Phase 2 UI work)

Split rationale: Backend contract should land and be testable before frontend integration. Frontend test coverage is a dedicated hardening task so later P1 changes can move faster with lower regression risk.

## Verification

```bash
make backend-verify
make frontend-verify
```
