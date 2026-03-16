---
TUTORING SESSION CONTEXT (do not modify)

I am a junior developer learning through code review. You are a
senior dev explaining this to me as your intern.

My stack: FastAPI, PostgreSQL + pgvector, SQLAlchemy async,
Next.js/TypeScript, Redis, ARQ, OpenAI embeddings, Anthropic API.
My projects: Quaero (RAG/document Q&A), Rostra (real-time chat),
FAROS (task manager/AWS).

How to explain: go block by block, 5-15 lines at a time. For each
block give me WHAT, WHY, TRADEOFF, and PATTERN. Stop after each
block and ask if I want to go deeper or move on. Do not proceed
until I respond.

If a concept connects to Rostra, FAROS, or another part of Quaero,
say so explicitly. If there is a security implication, flag it
with [SECURITY]. If I ask "why not X", give me a real answer.

Depth signals: "keep going" = next block, "go deeper" = expand
current block, "how would I explain this in an interview" = give
me a 2-sentence out-loud answer.
---

## What Was Built
- Added recovery boundaries around the dashboard page shell and chat messages stream so runtime render errors no longer hard-crash the full UI.
- Implemented focused tests for both page-level and inline fallbacks, including `Reload` interaction and error logging assertions.
- Refined the chat message list rendering path so a message-level boundary actually catches render-time faults in message content and still preserves existing chat behaviors.

## Top 3 Decisions and Why
1. Add a shared `ErrorBoundary` component with `page` and `inline` variants - centralized fallback UI keeps behavior consistent across scopes while avoiding duplicated inline fallback logic.
2. Wrap `DashboardPage` with a page-level boundary and `ChatWindow` messages with inline boundaries - scoped recovery improves UX by preserving unaffected areas and avoids full-page reloads unless needed.
3. Extract each message row into `MessageRow` and place per-row boundaries - this makes message rendering failures catchable by React error boundaries and keeps boundary state local.

## Non-Obvious Patterns Used
- Using `ErrorBoundary` as a component boundary means failures in child render trees are isolated by branch, but only if the problematic JSX actually executes within the boundary subtree; that’s why the message rows are separated.
- Stubbing `window.location` via `vi.stubGlobal("location", ...)` in tests avoids non-configurable property issues with `window.location.reload` in jsdom.
- Keeping fallback text and reload control assertions near boundary tests prevents silent regression of the recovery UX contract.

## Tradeoffs Evaluated
- A single page-level boundary was considered for speed, but it would hide recoverability opportunities when only one chat message breaks.
- Per-message boundaries were chosen over global try/catch in render logic to avoid invasive refactors and to align with React’s boundary model.
- Boundary wrappers were preferred over silent error swallowing to keep issues visible to users and provide an explicit recovery path.

## What I'm Uncertain About
- Whether each message should have its own boundary or messages could be chunked into larger grouped boundaries if future performance profiling shows mount/render overhead.
- Whether to expose `errorMessage` in UI for support troubleshooting; currently kept generic to avoid leaking internals.
- Whether retry-from-fallback behavior should include state-reset logic beyond `window.location.reload` for very large conversations.

## Relevant Code Pointers
- frontend/app/components/dashboard/ErrorBoundary.tsx > 15
- frontend/app/dashboard/page.tsx > 262
- frontend/app/components/dashboard/ChatWindow.tsx > 200
- frontend/app/components/dashboard/ChatWindow.tsx > 508
- frontend/app/components/dashboard/__tests__/ChatWindow.streaming.test.tsx > 682
- frontend/app/dashboard/__tests__/page.boundary.test.tsx > 39
