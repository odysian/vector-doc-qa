# Backend Core Fixes — Spec

## Fix 1: Unblock async event loop during PDF extraction

### Problem
`run_with_timeout` in `app/utils/timeout.py` is synchronous — it creates a `ProcessPoolExecutor` and blocks on `future.result()`. Called from `async def process_document_text`, this blocks the ARQ worker's event loop for up to 30 seconds, stalling Redis heartbeats and all other async activity.

### Current flow
```
process_document_text (async)
  → extract_text_from_pdf (sync)
    → run_with_timeout (sync, blocks on ProcessPoolExecutor)
```

### Proposed fix
Replace `run_with_timeout` with an async version that uses `loop.run_in_executor()` to offload to a `ProcessPoolExecutor` without blocking the event loop.

### Files to change
- `app/utils/timeout.py` — rewrite `run_with_timeout` as `async def run_with_timeout_async`. Keep a module-level `ProcessPoolExecutor` singleton instead of creating one per call.
- `app/utils/pdf_utils.py` — `extract_text_from_pdf` becomes `async def`, calls `await run_with_timeout_async(...)`.
- `app/services/document_service.py` — update call: `text = await extract_text_from_pdf(str(pdf_path))`.

### Timeout mechanism
`loop.run_in_executor` does not support a timeout natively. Wrap it with `asyncio.wait_for(loop.run_in_executor(...), timeout=N)`. On timeout, `asyncio.TimeoutError` is raised, and the process in the pool continues (can't kill a process mid-execution cleanly) but the result is discarded. This matches the current behavior — `future.cancel()` in the existing code also does not actually kill the subprocess.

### Edge cases
- Worker shutdown: the module-level executor should be shut down gracefully. Add a cleanup function or rely on Python's atexit handling.
- Nested `ProcessPoolExecutor` inside `asyncio`: works fine as long as `fork` start method is avoided with asyncio. Use `spawn` explicitly if needed.

### Tests
- Unit test: `run_with_timeout_async` returns correct result for fast function.
- Unit test: `run_with_timeout_async` raises `TimeoutError` for slow function.
- Unit test: `extract_text_from_pdf` is now a coroutine.

---

## Fix 2: Prevent duplicate chunks on retry after partial failure

### Problem
In `document_service.py`, if processing fails *after* `db.flush()` has written chunk rows (e.g. the embedding API call fails mid-batch), the error handler commits `status=FAILED` along with the partially-created chunks. On retry, new chunks are created without cleaning up old ones, corrupting the search index with duplicates.

### Current flow
```
process_document_text:
  1. status = PROCESSING, commit
  2. extract text, chunk text
  3. create Chunk objects, db.add each
  4. db.flush()                      ← chunks now in session
  5. generate_embeddings_batch()     ← if this fails...
  6. except: status=FAILED, commit   ← ...chunks are committed too
  7. retry: creates MORE chunks      ← duplicates
```

### Proposed fix
Two changes:
1. **Rollback before setting failure status.** In the error handler, call `await db.rollback()` before setting `status=FAILED` and committing. This discards the partial chunks from the flush. Then re-fetch the document (the rollback expired it), set status/error, and commit.
2. **Delete existing chunks at the start of processing.** As a defense-in-depth measure, delete any existing chunks for the document at the start of `process_document_text`, before creating new ones. This handles the case where a previous run committed chunks but the status update failed (crash between flush and error handler).

### Files to change
- `app/services/document_service.py` — error handler rollback + re-fetch; add chunk cleanup at start.

### Error handler rewrite
```python
except Exception as e:
    logger.error(f"Processing failed: {e}", exc_info=True)
    await db.rollback()
    # Re-fetch document since rollback expired the ORM object
    document = await db.scalar(
        select(Document).where(Document.id == document_id)
    )
    if document:
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        await db.commit()
    raise
```

### Chunk cleanup at start
```python
# Before creating new chunks, remove any leftover from a failed run
from sqlalchemy import delete
await db.execute(
    delete(Chunk).where(Chunk.document_id == document.id)
)
```

### Tests
- Test: processing failure after flush does not leave orphan chunks in DB.
- Test: retry after failure produces correct chunk count (no duplicates).
- Test: happy path still works (no regression).

---

## Fix 3: Fix embedding-chunk misalignment

### Problem
`generate_embeddings_batch` filters out empty/whitespace texts before calling OpenAI, returning fewer embeddings than chunks passed in. The caller does `zip(chunk_objects, embeddings)`, which silently misaligns embeddings with the wrong chunks.

### Current flow
```
texts = ["hello", "", "world"]      # 3 texts
valid_texts = ["hello", "world"]    # 2 after filter
embeddings = [emb_1, emb_2]        # 2 returned
zip(chunks, embeddings):            # chunk[0]=emb_1, chunk[1]=emb_2, chunk[2]=nothing
                                    # chunk[1] was "" but gets emb for "world"
```

### Proposed fix
Remove the filtering logic from `generate_embeddings_batch`. The caller (`document_service.py`) already guarantees non-empty texts because `chunk_text` strips empty chunks. The function should require all inputs are valid and raise if any are empty, making the contract explicit.

### Files to change
- `app/services/embedding_service.py` — remove `valid_texts` filtering in `generate_embeddings_batch`. Validate that all texts are non-empty, raise `ValueError` if any are. Compare `len(embeddings)` against `len(texts)`.

### Tests
- Test: `generate_embeddings_batch` raises `ValueError` if any text is empty.
- Test: returned embeddings count matches input count (mock OpenAI).

---

## Fix 4: Singleton API clients

### Problem
`AsyncOpenAI()` and `AsyncAnthropic()` are instantiated on every API call, each creating a new connection pool with fresh TCP+TLS handshakes.

### Proposed fix
Create module-level singleton clients using a lazy initialization pattern.

### Files to change
- `app/services/embedding_service.py` — module-level `_client: AsyncOpenAI | None = None` with a `_get_client()` helper.
- `app/services/anthropic_service.py` — same pattern for `AsyncAnthropic`.

### Pattern
```python
_client: AsyncOpenAI | None = None

def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client
```

### Tests
- Test: calling `_get_client()` twice returns the same instance.

---

## Fix 5: `validate_refresh_token` commits inside caller's transaction

### Problem
`validate_refresh_token` in `security.py` calls `await db.commit()` when it finds an expired token, breaking the caller's transaction boundary.

### Proposed fix
Remove the `commit()` from `validate_refresh_token`. Delete the expired row but let the caller commit. The function docstring already says "callers handle deletion" but the implementation doesn't match.

### Files to change
- `app/core/security.py` — remove `await db.commit()` from the expired-token branch in `validate_refresh_token`. Keep the delete.

### Tests
- Test: `validate_refresh_token` does not commit when token is expired (mock session, verify commit not called).

---

## Fix 6: `datetime.utcnow()` → `datetime.now(timezone.utc)`

### Problem
`_reset_stale_processing_documents` in `arq_worker.py` uses `datetime.utcnow()` (naive, deprecated). Rest of codebase uses `datetime.now(timezone.utc)` (aware).

### Files to change
- `app/workers/arq_worker.py` — one-line change.

### Tests
- No dedicated test needed. Existing behavior is unchanged for UTC servers.

---

## Fix 7: Health endpoint leaks filesystem path

### Problem
`/health` returns `upload_dir` as an absolute filesystem path to unauthenticated users.

### Proposed fix
Remove `upload_dir` from the health response. The health endpoint should only report service status, not internal paths.

### Files to change
- `app/main.py` — remove `upload_dir` from both the healthy and unhealthy responses.

### Tests
- Test: `/health` response does not contain `upload_dir` key.

---

## Fix 8: Clean up dead `.where()` in document_service

### Problem
`select(Document).where(Document.id == document_id).where()` has an empty `.where()` — no-op but looks like an incomplete edit.

### Files to change
- `app/services/document_service.py` — remove the empty `.where()`.

---

## Verification Plan

After all fixes:

```bash
cd backend
ruff check .
mypy . --ignore-missing-imports
pytest -v --noconftest tests/test_chunking.py   # unit tests (no DB)
pytest -v                                        # full suite (needs DB)
bandit -r app/ -ll
```

## Implementation Order

1. Fix 8 (dead code cleanup) — trivial, no risk
2. Fix 6 (datetime) — one-line, no risk
3. Fix 7 (health endpoint) — remove two lines, no risk
4. Fix 5 (validate_refresh_token commit) — small, isolated
5. Fix 4 (singleton clients) — straightforward refactor
6. Fix 3 (embedding misalignment) — contract change, needs test
7. Fix 2 (duplicate chunks) — most impactful data integrity fix
8. Fix 1 (async timeout) — largest change, touches 3 files
