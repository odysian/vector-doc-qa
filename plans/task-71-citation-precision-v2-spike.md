# Task 71 Kickoff Backfill: Citation Precision v2 Spike

- Task issue: #71
- Parent spec: #69
- Mode: single
- Branch: task-71-citation-precision-v2-spike
- Date: 2026-03-05

## Goal
Improve citation click precision in the PDF viewer by attempting text-level highlight on the cited page while preserving current page-level jump/highlight fallback behavior.

## Non-goals
- Backend schema/API changes
- OCR
- Guaranteed exact character offsets across all PDFs
- Re-indexing chunks

## Acceptance Criteria
1. Citation clicks still jump to the cited page reliably.
2. Viewer attempts text-level snippet matching on the cited page using existing source payload content.
3. Successful text matches apply a subtle short-lived text highlight.
4. If text match fails, existing page-level highlight behavior still applies.
5. `make frontend-verify` passes.

## Scope
In scope:
- `frontend/app/components/dashboard/ChatWindow.tsx`
- `frontend/app/components/dashboard/PdfViewer.tsx`
- `frontend/app/dashboard/page.tsx`
- frontend tests for citation click payload wiring and highlight helper behavior

Out of scope:
- backend changes
- migration changes
- broad UI redesign

## Verification Commands
- `make frontend-verify`
