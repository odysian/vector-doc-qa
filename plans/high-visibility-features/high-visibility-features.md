# High-Visibility Feature Spec
## Streaming Responses, Pipeline Observability, PDF Viewer
*March 2026 — Updated after Codex review*

---

## Motivation

These features are selected for maximum interview impact per unit of effort.
They transform Quaero from "working RAG demo" to "polished, production-aware
AI application" — the kind of thing that makes an interviewer pause and look
closer.

## Review history

- **v1** (initial draft): Streaming, PDF viewer, thumbs up/down, pipeline meta.
- **v2** (this version): Incorporates Codex review feedback and codebase audit
  P2 items. Key changes:
  - Thumbs up/down deferred (low ROI without a visible feedback loop).
  - P2 audit items folded into foundation/streaming phases (P2-21, P2-9, P2-8).
  - Rate limiting fixed to use explicit shared scope.
  - DB session handling tightened for streaming endpoint.
  - PDF viewer upgraded: citation-to-page deep links are the real value-add.
  - Cookie-in-iframe risk called out (not just CORS).
  - Conversation continuity and stop/retry controls added as future candidates.

---

## Execution Phases

```
Phase 0: Foundation (prerequisites + P2 cleanup)
Phase 1: Streaming RAG responses + pipeline meta
Phase 2: PDF viewer + citation deep links
Phase 3: Reassess (conversation continuity, stop/retry, eval harness, remaining P2s)
```

---

## Phase 0: Foundation

Prerequisite work that unblocks Phase 1 and resolves audit items naturally
on the implementation path.

### 0a. FastAPI version bump

Bump `fastapi` from `0.128.0` to `>=0.135.0` in `requirements.txt`.

**Why:** Gains first-class SSE support via `fastapi.sse.EventSourceResponse`
and `ServerSentEvent`. Without this, streaming would require manual SSE frame
formatting over `StreamingResponse`.

**What the new API provides:**
- POST support (browser `EventSource` is GET-only; our query endpoint is POST)
- Pydantic model auto-serialization in SSE `data` fields
- Typed event names via `ServerSentEvent(data=..., event="token")`
- Auto keep-alive pings every 15s (prevents proxy/LB connection kills)
- Auto `Cache-Control: no-cache` and `X-Accel-Buffering: no` headers

**Risk:** Check for breaking changes in FastAPI 0.128→0.135 changelog.
Run full `make backend-verify` after bump to catch regressions.

### 0b. Singleton AI clients (audit P2-21)

**Current state:** Both `embedding_service.py` (lines 20, 67) and
`anthropic_service.py` (line 62) create new `AsyncOpenAI` / `AsyncAnthropic`
clients on every request. This adds redundant connection/TLS setup overhead.

**Fix:** Lazy module-level singleton for each client.

```python
# embedding_service.py
_client: AsyncOpenAI | None = None

def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client
```

Same pattern for `AsyncAnthropic` in `anthropic_service.py`.

**Why now:** We're about to add `client.messages.stream()` for the streaming
endpoint. Fix client instantiation once before adding more call sites.

### 0c. Close Spec #19

All 7 P0/P1 child tasks (#20-#26) are merged. Spec #19 should be formally
closed to keep the issue board clean.

---

## Phase 1: Streaming RAG Responses + Pipeline Meta

### What it does

Instead of waiting 3-8 seconds for a complete answer, tokens stream into the
chat window in real time as Claude generates them. Each response also carries
pipeline timing metadata showing how long each RAG stage took.

### Why it matters

- Perceived latency drops from seconds to milliseconds (first token appears
  almost instantly)
- Every interviewer has used ChatGPT — they'll immediately recognize the
  polish
- Pipeline meta shows you understand what's happening inside the RAG system
- Demonstrates SSE, async generators, streaming protocols, and
  instrumentation

### Backend

#### New streaming service method

Add `generate_answer_stream` to `anthropic_service.py`:

```python
async def generate_answer_stream(
    query: str, chunks: list[dict]
) -> AsyncIterator[str]:
    """Yield answer tokens as they arrive from Claude."""
    prompt = _build_prompt(query, chunks)
    client = _get_client()  # singleton from Phase 0

    async with client.messages.stream(
        model="claude-3-haiku-20240307",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            yield text
```

The existing `generate_answer` stays unchanged for the non-streaming
`/query` endpoint and tests.

#### New streaming endpoint

```
POST /api/documents/{document_id}/query/stream
```

**SSE event protocol:**

| Event type | Data payload | When |
|---|---|---|
| `sources` | JSON array of `SearchResult` objects | After retrieval, before LLM call |
| `token` | Raw text string (partial answer) | Each token/chunk from Claude |
| `meta` | JSON `pipeline_meta` object | After answer completes, before DB save |
| `done` | `{"message_id": <int>}` | After assistant message saved to DB |
| `error` | `{"detail": "..."}` | On any failure |

Sources arrive before tokens so the frontend can render citation cards
immediately while the answer types out. Meta arrives after the last token
so timing data doesn't block the answer stream.

**Pipeline meta shape:**

```json
{
  "embed_ms": 120,
  "retrieval_ms": 45,
  "llm_ms": 2340,
  "total_ms": 2505,
  "top_similarity": 0.87,
  "avg_similarity": 0.79,
  "chunks_retrieved": 5
}
```

Collected via `time.perf_counter()` around each service call. No new tables
or schema — just measure and return. If a `pipeline_runs` table is added
later (from Sonnet's observability spec), the data is already structured.

#### DB session handling (Codex feedback)

**Problem:** Holding one DB session open for the entire stream duration
(potentially 5-10 seconds) ties up a connection pool slot unnecessarily.

**Solution:** Split into two transaction scopes:

1. **Before stream:** Validate document, check ownership, save user message,
   run search, commit. This releases the DB session.
2. **After stream completes:** Open a new session, save assistant message
   with full answer text + sources, commit.

```python
@router.post("/{document_id}/query/stream", response_class=EventSourceResponse)
@limiter.limit("10/hour", key_func=get_user_or_ip_key, scope="query")
async def query_document_stream(
    request: Request,
    document_id: int,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # --- Transaction 1: validate + save user message + retrieve ---
    document = await _validate_document_for_query(document_id, current_user, db)

    user_message = Message(
        document_id=document_id,
        user_id=current_user.id,
        role="user",
        content=body.query,
    )
    db.add(user_message)

    t0 = time.perf_counter()
    query_embedding = ...  # embed query
    embed_ms = int((time.perf_counter() - t0) * 1000)

    t1 = time.perf_counter()
    search_results = await search_chunks(...)
    retrieval_ms = int((time.perf_counter() - t1) * 1000)

    sources = [SearchResult(**r) for r in search_results]
    await db.commit()  # releases session

    # --- Stream generator (no open DB session) ---
    async def event_generator():
        yield ServerSentEvent(
            data=json.dumps([s.model_dump() for s in sources]),
            event="sources",
        )

        full_answer = []
        t2 = time.perf_counter()
        try:
            async for token in generate_answer_stream(body.query, search_results):
                full_answer.append(token)
                yield ServerSentEvent(data=token, event="token")
        except Exception as exc:
            logger.error(f"Stream failed: {exc}", exc_info=True)
            yield ServerSentEvent(
                data=json.dumps({"detail": "Answer generation failed"}),
                event="error",
            )
            return

        llm_ms = int((time.perf_counter() - t2) * 1000)
        total_ms = embed_ms + retrieval_ms + llm_ms

        # Emit pipeline meta
        similarities = [s.similarity for s in sources]
        yield ServerSentEvent(
            data=json.dumps({
                "embed_ms": embed_ms,
                "retrieval_ms": retrieval_ms,
                "llm_ms": llm_ms,
                "total_ms": total_ms,
                "top_similarity": max(similarities) if similarities else 0,
                "avg_similarity": (sum(similarities) / len(similarities))
                    if similarities else 0,
                "chunks_retrieved": len(sources),
            }),
            event="meta",
        )

        # --- Transaction 2: persist assistant message ---
        try:
            async with AsyncSessionLocal() as save_db:
                assistant_message = Message(
                    document_id=document_id,
                    user_id=current_user.id,
                    role="assistant",
                    content="".join(full_answer),
                    sources=[s.model_dump() for s in sources],
                )
                save_db.add(assistant_message)
                await save_db.commit()
                yield ServerSentEvent(
                    data=json.dumps({"message_id": assistant_message.id}),
                    event="done",
                )
        except Exception as exc:
            logger.error(f"Failed to save assistant message: {exc}", exc_info=True)
            yield ServerSentEvent(
                data=json.dumps({"detail": "Answer shown but save failed"}),
                event="error",
            )

    return EventSourceResponse(event_generator())
```

**Tradeoff:** Two separate transactions mean a crash between stream
completion and DB save loses the assistant message. This is acceptable —
the user already saw the answer, and they can re-ask. The alternative
(holding one session open for the whole stream) risks connection pool
exhaustion under concurrent load, which is worse.

#### Document validation helper (audit P2-9)

**Current state:** Both `/query` and `/search` do
`selectinload(Document.chunks)` just to check `if not document.chunks`.
This loads all chunk content into memory for a boolean check.

**Fix:** Extract a shared validation helper that uses a lightweight
existence check:

```python
async def _validate_document_for_query(
    document_id: int, current_user: User, db: AsyncSession
) -> Document:
    document = await db.scalar(
        select(Document)
        .where(Document.id == document_id, Document.user_id == current_user.id)
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Document not processed yet")

    has_chunks = await db.scalar(
        select(literal(1)).where(Chunk.document_id == document_id).limit(1)
    )
    if not has_chunks:
        raise HTTPException(status_code=400, detail="Document has no chunks")

    return document
```

Apply to both the existing `/query` and new `/query/stream` endpoints.
Also apply to `/search` for consistency.

#### Error handling (audit P2-8)

**Current state:** Lines 324-325 and 421 in `documents.py` return
`detail=f"Search failed: {str(e)}"`, which leaks internal exception
messages to clients.

**Fix:** In the new streaming endpoint, all error SSE events use generic
client-safe messages. Full exceptions are logged server-side only.

Also fix the existing `/query` and `/search` endpoints while we're in the
file:

```python
# Before
raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# After
logger.error(f"Query failed for document_id={document_id}: {e}", exc_info=True)
raise HTTPException(status_code=500, detail="Query failed")
```

#### Rate limiting (Codex feedback)

**Problem:** Putting the same limit string (`"10/hour"`) on two separate
endpoints doesn't automatically share a bucket. SlowAPI creates independent
counters per endpoint by default.

**Fix:** Use explicit `scope` parameter so both endpoints share one counter:

```python
@router.post("/{document_id}/query", ...)
@limiter.limit("10/hour", key_func=get_user_or_ip_key, scope="query")
async def query_document(...):

@router.post("/{document_id}/query/stream", ...)
@limiter.limit("10/hour", key_func=get_user_or_ip_key, scope="query")
async def query_document_stream(...):
```

A user gets 10 total queries per hour regardless of which endpoint they use.

#### Keeping the non-streaming endpoint

The existing `POST /query` stays. It's used by:
- All existing tests (no rewrite needed)
- Any future non-browser clients (scripts, mobile apps)
- Fallback if SSE doesn't work in some environment

The non-streaming endpoint should also return `pipeline_meta` in its JSON
response for consistency. Add it to the `QueryResponse` schema as an
optional field.

### Frontend

#### SSE consumer in api.ts

Add `queryDocumentStream` using the browser's native `fetch` +
`ReadableStream` (not `EventSource`, which doesn't support POST or custom
headers):

```typescript
queryDocumentStream: async (
  documentId: number,
  query: string,
  callbacks: {
    onSources: (sources: SearchResult[]) => void;
    onToken: (token: string) => void;
    onMeta: (meta: PipelineMeta) => void;
    onDone: (data: { message_id: number }) => void;
    onError: (detail: string) => void;
  },
): Promise<void> => {
  const csrf = getCsrfToken();
  const response = await fetch(
    fullUrl(`/api/documents/${documentId}/query/stream`),
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      },
      body: JSON.stringify({ query }),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new ApiError(response.status, error.detail || "Request failed");
  }

  // Parse SSE frames from ReadableStream
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Split on double-newline (SSE frame boundary)
    const frames = buffer.split("\n\n");
    buffer = frames.pop()!; // keep incomplete frame in buffer

    for (const frame of frames) {
      // Parse event type and data from SSE frame
      // Dispatch to appropriate callback
    }
  }
}
```

**401 handling:** If the initial `fetch` returns 401, attempt the same
silent refresh flow as `apiRequest`. This needs to be handled before
entering the stream reader.

#### ChatWindow streaming UI

- When user submits a query, immediately add an empty assistant message
  placeholder to the messages array with a `streaming: true` flag
- As `onSources` fires (before tokens), attach sources to the placeholder
- As `onToken` fires, append text to the placeholder's `content` via
  functional state update — React re-renders with each token
- As `onMeta` fires, attach `pipeline_meta` to the placeholder
- When `onDone` fires, set `streaming: false` on the placeholder
- If `onError` fires, append error notice to the message content and stop

Scroll-to-bottom behavior stays the same (already auto-scrolls on message
change via the existing `useEffect`).

#### Pipeline meta display component

Below each assistant message (that has `pipeline_meta`), render a subtle
expandable bar:

```
Collapsed:
┌──────────────────────────────────────────────┐
│  2.5s  ·  87% retrieval  ·  5 sources       │
│  ▸ Details                                   │
└──────────────────────────────────────────────┘

Expanded:
┌──────────────────────────────────────────────┐
│  Embedding     120ms                         │
│  Retrieval      45ms  (5 chunks, 87% avg)    │
│  Generation   2340ms                         │
│  ────────────────────                        │
│  Total        2505ms                         │
└──────────────────────────────────────────────┘
```

Style: `text-xs text-zinc-500`, doesn't compete with the answer. Uses the
same expand/collapse pattern as the existing source cards.

#### Type additions (api.types.ts)

```typescript
export interface PipelineMeta {
  embed_ms: number;
  retrieval_ms: number;
  llm_ms: number;
  total_ms: number;
  top_similarity: number;
  avg_similarity: number;
  chunks_retrieved: number;
}
```

Add `pipeline_meta?: PipelineMeta` to `QueryResponse` for the non-streaming
endpoint, and to the local `Message` interface in ChatWindow.

### CORS note

SSE over POST works with the existing CORS config — it's a standard fetch
request with `credentials: "include"`. The `allow_headers` list already
includes `Content-Type` and `X-CSRF-Token`. No CORS changes needed.

---

## Phase 2: PDF Viewer + Citation Deep Links

### What it does

Users view uploaded PDFs directly in the app, side-by-side with the chat
window. Clicking a source citation scrolls the PDF to the relevant page or
section.

### Why it matters (with citation links)

Without citation deep links, the PDF viewer is just an iframe — functional
but unremarkable. With them, it becomes a trust mechanism: "click the source,
see the evidence." This is the feature that turns a demo into something an
interviewer remembers.

### Backend

#### PDF serving endpoint

```
GET /api/documents/{document_id}/file
```

| Header | Value |
|---|---|
| `Content-Type` | `application/pdf` |
| `Content-Disposition` | `inline; filename="original.pdf"` |
| `Cache-Control` | `private, max-age=3600` |

```python
from fastapi.responses import Response

@router.get("/{document_id}/file")
@limiter.limit("30/hour", key_func=get_user_or_ip_key)
async def get_document_file(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = await db.scalar(
        select(Document)
        .where(Document.id == document_id, Document.user_id == current_user.id)
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    pdf_bytes = await read_file_bytes(document.file_path)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{document.filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )
```

Uses existing `storage_service.read_file_bytes` — works for both local and
GCS backends.

#### Page number tracking in chunks

To support citation-to-page deep links, chunks need to know which page(s)
they came from. Currently `pdf_utils.py` extracts text by page but the
chunking step loses page boundaries.

**Options:**

| Option | Description | Tradeoff |
|---|---|---|
| A. Store `page_start`/`page_end` on chunks | Add columns to chunks table, populate during processing | Requires migration + reprocess existing docs |
| B. Compute page mapping at query time | Re-extract page boundaries from stored PDF, map chunk_index to pages | No migration, but adds latency per query |
| C. Store page metadata in chunk content prefix | Embed `[Page 3]` markers in chunk text | No migration, but pollutes content and embedding |

**Recommendation:** Option A. It's the cleanest long-term solution. The
migration is simple (two nullable INTEGER columns). Existing documents can
be reprocessed via the existing `/process` endpoint. New documents get page
numbers automatically.

```python
# In Chunk model
page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

Update `pdf_utils.py` chunking to track which page(s) each chunk spans.
Update `SearchResult` schema to include `page_start`/`page_end`.

### Frontend

#### PDF rendering approach

**Primary concern (Codex feedback):** The real risk with iframe-based PDF
viewing isn't CORS — it's **cookie behavior in cross-site embedded
contexts**. Modern browsers (Chrome, Safari) increasingly block or partition
third-party cookies in iframes. Since the backend is on a different domain
than the frontend (Vercel), the httpOnly auth cookie may not be sent with
the iframe's request.

**Decision tree:**

1. Test iframe approach first in dev (same-origin) — should work.
2. Test in production (cross-origin Vercel → GCP) — may fail due to
   third-party cookie restrictions.
3. If it fails: use `react-pdf`, which fetches the PDF via JS `fetch` (where
   we control `credentials: "include"`) and renders to canvas.

**`react-pdf` details (likely needed for production):**

```bash
npm install react-pdf
```

Adds ~400KB (pdf.js worker). Provides full control over rendering, page
navigation, zoom, and programmatic scroll-to-page for citation deep links.

```tsx
import { Document, Page, pdfjs } from "react-pdf";

function PdfViewer({ documentId, highlightPage }: PdfViewerProps) {
  const [numPages, setNumPages] = useState(0);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Scroll to page when citation is clicked
  useEffect(() => {
    if (highlightPage && pageRefs.current.has(highlightPage)) {
      pageRefs.current.get(highlightPage)!.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }, [highlightPage]);

  return (
    <Document
      file={`${API_URL}/api/documents/${documentId}/file`}
      options={{
        withCredentials: true,
        httpHeaders: { "X-CSRF-Token": getCsrfToken() ?? "" },
      }}
      onLoadSuccess={({ numPages }) => setNumPages(numPages)}
    >
      {Array.from({ length: numPages }, (_, i) => (
        <div key={i} ref={(el) => el && pageRefs.current.set(i + 1, el)}>
          <Page pageNumber={i + 1} />
        </div>
      ))}
    </Document>
  );
}
```

**Tradeoff:** `react-pdf` adds bundle size but gives us citation deep links
for free (programmatic scroll-to-page). An iframe can do `#page=N` but
browser support is inconsistent and we lose control over styling.

#### Layout: split view

When a document is selected, the main area splits:

```
Desktop (lg+):
┌──────────┬────────────────┬────────────────┐
│ Sidebar  │  PDF Viewer    │  Chat Window   │
│ (w-72)   │  (flex-1)      │  (flex-1)      │
└──────────┴────────────────┴────────────────┘

Mobile/tablet:
┌──────────┬─────────────────────────────────┐
│ Sidebar  │  [PDF] [Chat]  ← tab toggle     │
│ (drawer) │  (full width, one visible)      │
└──────────┴─────────────────────────────────┘
```

CSS flexbox, no library needed. A drag-to-resize divider is nice-to-have
but not required for v1.

#### Citation-to-page interaction

When the user clicks a source citation in the chat:
1. The source card includes page number(s) from `SearchResult.page_start`
2. Clicking sets `highlightPage` state in the parent component
3. The PDF viewer scrolls to that page with smooth animation
4. A brief highlight/pulse effect on the target page (CSS animation)

This is the feature that makes interviewers pause. "Click the source, the
PDF scrolls to the evidence."

---

## Phase 3: Reassess

After Phases 0-2, evaluate these candidates based on remaining time and
energy:

### Conversation continuity (follow-up questions)

**What:** Send last N message turns as context to Claude so users can ask
follow-ups like "what about section 3?" or "explain that in simpler terms."

**Current state:** Messages are already stored per document in the
`messages` table and loaded via `getMessages`. The backend just needs to
include recent history in the prompt sent to Claude.

**Scope:** Small backend change (modify `_build_prompt` to accept optional
message history). No schema changes. Frontend already shows conversation
history.

**Interview value:** High — makes the app feel like a real chat, not a
stateless Q&A widget.

### Stop generating + retry/regenerate

**What:** Once streaming exists, add:
- "Stop" button that aborts the stream mid-generation
- "Retry" button on failed/stopped answers to re-run the query

**Scope:** Frontend-only for stop (abort the fetch reader). Retry is a
re-submission of the same query. Low incremental effort.

**Interview value:** High polish signal. Shows attention to UX edge cases.

### Small eval harness

**What:** 10-20 benchmark questions with known answers. Script that runs
them against the pipeline and reports accuracy, latency, and retrieval
quality metrics.

**Scope:** Python script + fixture data. No UI needed. Output is a
markdown table or JSON report.

**Interview value:** Excellent for technical depth conversations but not
visible in a live demo. Better suited for a README section or blog post.

### Remaining P2 audit items

These don't overlap with feature work and can be done as a standalone
cleanup pass:

| ID | Item | Notes |
|---|---|---|
| P2-7 | Query text logged at INFO | Reduce to DEBUG or log only IDs |
| P2-10 | No vector ANN index | Add HNSW index migration when chunk count grows |
| P2-11 | Message sources stores full text | Store chunk IDs + preview only |
| P2-12 | Inconsistent timestamps | Standardize on TIMESTAMPTZ |
| P2-13 | Stale processing detection | Track `processing_started_at` |
| P2-14 | Frontend redirect coupling | Return typed errors, handle in auth boundary |
| P2-19 | Helper-level commit | Already resolved by refresh rotation fix? Verify. |
| P2-20 | Health endpoint path leak | Remove `upload_dir` from `/health` |
| P2-22 | Chunking config guardrails | Validate chunk_size/overlap bounds |

---

## Deferred (not in scope)

These ideas were evaluated and explicitly deferred:

| Feature | Why deferred |
|---|---|
| Thumbs up/down feedback | Low ROI without a visible feedback loop or analytics dashboard. Revisit when/if analytics UI is built. |
| Sonnet's full observability spec | 6 new tables, separate schema, DB triggers, analytics endpoints — ~4 weeks for no visible output. Cherry-picked the high-value 20% (pipeline meta) into Phase 1 instead. |
| Frontend redesign | Separate design exercise. These features work with the current UI and carry over to any redesign. |
| Prompt version A/B testing | Requires traffic volume that a portfolio app won't have. |

---

## Interview narrative

With Phases 0-2 complete, the demo story becomes:

1. **"Upload a PDF"** — file handling, background processing, status polling
2. **"Ask a question"** — answer streams in real-time with source citations
3. **"Look at the pipeline breakdown"** — "120ms embedding, 45ms retrieval,
   2.3s generation. Retrieval is fast and accurate at 87% similarity, so the
   bottleneck is the LLM call. If I wanted to optimize, I'd look at prompt
   length or model selection, not retrieval."
4. **"View the PDF alongside the chat"** — split-view layout
5. **"Click a source citation"** — PDF scrolls to the exact page. "You can
   verify the answer against the original document."

That's a 60-second demo covering full-stack development, AI pipeline
understanding, and production thinking.
