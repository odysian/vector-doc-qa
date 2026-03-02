## Summary

Add SSE consumption and streaming chat UI to the frontend. Tokens appear in real time as they arrive from the backend streaming endpoint. Pipeline timing metadata is displayed below each assistant message.

Parent Spec: #38

## What this delivers

1. `queryDocumentStream()` method in `lib/api.ts` — SSE consumer using `fetch` + `ReadableStream`
2. ChatWindow streaming mode — token-by-token rendering with immediate source card display
3. Pipeline meta display component — expandable timing/retrieval quality breakdown
4. `PipelineMeta` TypeScript type in `lib/api.types.ts`

## Acceptance Criteria

- [ ] `queryDocumentStream()` in `lib/api.ts` consumes SSE via `fetch` + `ReadableStream` with POST
- [ ] CSRF token included in streaming request headers
- [ ] 401 responses trigger silent refresh attempt before failing
- [ ] ChatWindow uses streaming endpoint instead of blocking `/query`
- [ ] Empty assistant message placeholder appears immediately on query submission
- [ ] Source cards render when `sources` event arrives (before answer tokens)
- [ ] Tokens append to assistant message content in real time
- [ ] Pipeline meta component renders below assistant messages (collapsed by default)
- [ ] Expanded view shows: Embedding ms, Retrieval ms (chunks + avg similarity), Generation ms, Total ms
- [ ] Loading indicator shows during stream, stops on `done` or `error`
- [ ] Error events display gracefully (partial answer + error notice)
- [ ] Auto-scroll to bottom works during streaming
- [ ] `PipelineMeta` type defined in `lib/api.types.ts`
- [ ] `make frontend-verify` passes (tsc, next lint, build)

## Implementation Notes

**Why not `EventSource`:** Browser `EventSource` API is GET-only and doesn't support custom headers. We need POST (query in body) and `X-CSRF-Token` header.

**SSE parsing:** Split incoming `ReadableStream` chunks on `\n\n` (SSE frame boundary). Parse `event:` and `data:` fields from each frame. Dispatch to callbacks by event type.

**State management:** Use a `streaming` boolean flag on the assistant message placeholder. While `streaming === true`, the loading indicator shows and the send button is disabled.

**Pipeline meta persistence:** Store `pipeline_meta` on the local `Message` interface. For messages loaded from history (via `getMessages`), `pipeline_meta` will be `undefined` — the component handles this gracefully by not rendering the meta bar.

## Verification

```bash
make frontend-verify
```

## Files in scope

- `frontend/lib/api.ts` — add `queryDocumentStream()` method
- `frontend/lib/api.types.ts` — add `PipelineMeta` interface
- `frontend/app/components/dashboard/ChatWindow.tsx` — streaming UI + pipeline meta display

## Files explicitly out of scope

- Backend code (landed in previous task)
- Other dashboard components (DocumentList, UploadZone, DeleteDocumentModal)
- Dashboard page layout (`dashboard/page.tsx`)

## Labels

`type:task`, `area:frontend`
