## Summary

Add PDF viewer component, split-view layout, and citation-to-page deep links to the frontend. Clicking a source citation in the chat scrolls the PDF to the relevant page.

Parent Spec: #41

## What this delivers

1. PDF viewer component — renders uploaded PDFs in-app
2. Split-view layout — PDF viewer and chat window side by side on desktop, tab toggle on mobile
3. Citation deep links — clicking a source card scrolls PDF to the cited page
4. `getDocumentFile()` method in `lib/api.ts` (if using `react-pdf` approach)

## Acceptance Criteria

- [ ] PDF renders in-app when a completed document is selected
- [ ] Desktop (lg+): PDF viewer and chat window display side by side (50/50 flexbox split)
- [ ] Mobile/tablet: tab toggle switches between "PDF" and "Chat" views
- [ ] Source citations in chat display page number(s) from `SearchResult.page_start`
- [ ] Clicking a source citation scrolls the PDF viewer to the cited page (smooth scroll)
- [ ] Brief highlight/pulse effect on the target page after scroll
- [ ] PDF viewer handles loading state (spinner while PDF loads)
- [ ] PDF viewer handles error state (PDF load failure shows message)
- [ ] Works in production (cross-origin Vercel → GCP) — test cookie behavior
- [ ] `make frontend-verify` passes (tsc, next lint, build)

## Implementation Decision: iframe vs react-pdf

**Test in this order:**

1. Try iframe with `src={API_URL}/api/documents/${id}/file` in dev (same-origin) — should work
2. Test in production (Vercel → GCP cross-origin) — may fail due to third-party cookie partitioning
3. If iframe fails cross-origin: switch to `react-pdf`

`react-pdf` is the likely production choice because:
- It fetches PDF via JS `fetch` where we control `credentials: "include"` and headers
- It gives programmatic scroll-to-page for citation deep links (iframe `#page=N` is inconsistent across browsers)
- It allows styling control (dark theme background, page gaps)

**If `react-pdf` is needed:**

```bash
npm install react-pdf
```

Bundle impact: ~400KB (pdf.js worker). Acceptable for the functionality gained.

## Layout Sketch

```
Desktop (lg+):
┌──────────┬────────────────┬────────────────┐
│ Sidebar  │  PDF Viewer    │  Chat Window   │
│ (w-72)   │  (flex-1)      │  (flex-1)      │
└──────────┴────────────────┴────────────────┘

Mobile:
┌──────────┬─────────────────────────────────┐
│ Sidebar  │  [PDF] [Chat]  ← tab toggle     │
│ (drawer) │  (full width, one visible)      │
└──────────┴─────────────────────────────────┘
```

## Verification

```bash
make frontend-verify
```

## Files in scope

- `frontend/app/components/dashboard/PdfViewer.tsx` — new component
- `frontend/app/components/dashboard/ChatWindow.tsx` — source cards show page numbers, click handler
- `frontend/app/dashboard/page.tsx` — split-view layout, state management for highlighted page
- `frontend/lib/api.ts` — add PDF fetch method if needed for `react-pdf`
- `frontend/lib/api.types.ts` — update `SearchResult` with `page_start`/`page_end`

## Files explicitly out of scope

- Backend code (landed in previous task)
- Other pages (login, register, landing)

## Labels

`type:task`, `area:frontend`
