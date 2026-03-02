## Summary

Add in-app PDF viewing with citation-to-page deep links. Users view uploaded PDFs side-by-side with the chat window and can click source citations to jump to the relevant page in the document.

**Source:** `plans/high-visibility-features.md` Phase 2

## Scope

**Backend:**
- `GET /api/documents/{document_id}/file` — serves raw PDF bytes with proper content headers
- Add `page_start`/`page_end` columns to `chunks` table (Alembic migration)
- Update PDF chunking to track page boundaries during processing
- Include page numbers in `SearchResult` schema

**Frontend:**
- PDF viewer component (iframe or `react-pdf` based on cross-origin cookie testing)
- Split-view layout: PDF viewer + chat window side by side on desktop, tab toggle on mobile
- Citation-to-page deep links: clicking a source scrolls PDF to the relevant page

## Non-goals

- No text highlighting within pages (just page-level navigation)
- No PDF annotation or editing
- No drag-to-resize split divider (v1 uses fixed 50/50 split)
- No thumbnail/page-list sidebar in the PDF viewer

## Decision Locks

- **Page tracking approach:** Option A from spec — store `page_start`/`page_end` on chunks table. Cleanest long-term. Requires migration + reprocess of existing docs. Alternative B (compute at query time) rejected: adds latency per query. Alternative C (markers in chunk text) rejected: pollutes embeddings.
- **PDF rendering:** Test iframe first (zero dependencies). If cross-origin cookie partitioning blocks it in production (Vercel → GCP), fall back to `react-pdf` (~400KB bundle, but gives programmatic scroll-to-page for citation links). Decision made during frontend implementation based on testing.
- **Cookie-in-iframe risk:** The primary concern is NOT CORS — it's third-party cookie partitioning in modern browsers. Chrome and Safari increasingly block/partition cookies in cross-site iframes. The httpOnly auth cookie may not be sent with the iframe request when frontend and backend are on different domains. This is the main reason `react-pdf` (which uses JS `fetch` with `credentials: "include"`) is the likely production choice.
- **Split layout:** CSS flexbox, 50/50 split on desktop (lg+). Mobile uses tab toggle between PDF and Chat. No resize handle in v1.

## Child Tasks

- [ ] Task: PDF backend (file endpoint + page tracking migration + chunking update)
- [ ] Task: PDF frontend (viewer component + split layout + citation deep links)

Split rationale: Backend includes a migration and chunking logic change — should land and be verified before frontend integration. Existing documents need reprocessing after the migration to populate page numbers.

## Verification

```bash
make backend-verify
make frontend-verify
```
