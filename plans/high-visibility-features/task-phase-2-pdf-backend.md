## Summary

Add PDF file serving endpoint, page number tracking on chunks, and update the chunking pipeline to record page boundaries.

Parent Spec: #41

## What this delivers

1. `GET /api/documents/{document_id}/file` — serves PDF bytes with `Content-Type: application/pdf`, ownership check, caching headers
2. `page_start` / `page_end` nullable INTEGER columns on `chunks` table (Alembic migration)
3. Updated `pdf_utils.py` chunking to track which page(s) each chunk spans
4. `page_start` / `page_end` fields in `SearchResult` schema

## Acceptance Criteria

- [ ] `GET /file` returns PDF bytes with `Content-Type: application/pdf` and `Content-Disposition: inline`
- [ ] `GET /file` enforces ownership check (404 for wrong user)
- [ ] `GET /file` sets `Cache-Control: private, max-age=3600`
- [ ] `GET /file` uses `storage_service.read_file_bytes` (works for local + GCS)
- [ ] Rate limited at 30/hour per user
- [ ] Alembic migration adds `page_start` and `page_end` nullable INTEGER columns to `chunks`
- [ ] Migration is reversible (downgrade drops columns)
- [ ] `chunk_text()` in `pdf_utils.py` returns page boundary info per chunk
- [ ] `document_service.py` populates `page_start`/`page_end` during processing
- [ ] `SearchResult` schema includes `page_start`/`page_end` (nullable, for backward compat)
- [ ] Existing documents can be reprocessed via `/process` to populate page numbers
- [ ] All existing tests pass
- [ ] New tests for `/file` endpoint (happy path, not found, wrong user)
- [ ] `make backend-verify` passes

## Implementation Notes

**Page tracking in chunking:**

`pdfplumber` extracts text page-by-page. The chunking function currently concatenates all pages then chunks by character count. To track pages:

1. Extract text per page, recording cumulative character offset per page boundary
2. After chunking, map each chunk's `[start_char, end_char]` range to page numbers using the offset table
3. Store `page_start` (first page the chunk touches) and `page_end` (last page)

**Reprocessing existing docs:**

After migration, existing chunks will have `page_start = NULL` / `page_end = NULL`. Users can reprocess documents via the existing `POST /process` endpoint, which deletes old chunks and creates new ones with page numbers populated.

## Verification

```bash
make backend-verify
```

## Files in scope

- `backend/app/api/documents.py` — new `/file` endpoint
- `backend/app/models/base.py` — add `page_start`/`page_end` to `Chunk` model
- `backend/app/utils/pdf_utils.py` — update chunking to return page boundaries
- `backend/app/services/document_service.py` — populate page fields during processing
- `backend/app/schemas/search.py` — add page fields to `SearchResult`
- `backend/alembic/versions/` — new migration file
- `backend/tests/` — new `/file` endpoint tests

## Labels

`type:task`, `area:backend`, `area:db`
