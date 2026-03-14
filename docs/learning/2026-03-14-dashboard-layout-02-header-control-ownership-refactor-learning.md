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
Task #209 moved dashboard control ownership so chat lost its desktop header, while PDF gained the context header (back action, title, date). It also moved debug mode state/persistence into dashboard state and moved the debug toggle into the app header near logout. Workspace document switching is now sidebar-only, with compact/mobile auto-closing the drawer after selection.

## Top 3 Decisions and Why
1. Move `debugMode` into `useDashboardState` and pass into `ChatWindow` - this keeps state ownership at the dashboard orchestration layer and removes localStorage side effects from presentational chat UI.
2. Extend `PdfViewer` with `filename` and `uploadedAt` string props (instead of passing full document object) - this keeps component contracts narrow and explicit while satisfying the new header context requirement.
3. Delete `DocumentSwitcher` and use `WorkspaceSidebar` as the single switch surface - this removes duplicated controls and makes workspace navigation consistent with sidebar ownership.

## Non-Obvious Patterns Used
- Responsive behavior was enforced in state logic, not only layout classes: `handleViewerDocumentSwitch` closes the sidebar only when `layoutMode !== "desktop"`, so desktop keeps push behavior while compact/mobile behaves like an overlay drawer.
- Chat context display is driven by `showContextBar` prop, which allows one `ChatWindow` component to serve desktop and compact/mobile without branching into separate components.
- PDF header ownership change was implemented without changing citation/zoom internals, limiting regression risk by isolating contract changes to header props and rendering.

## Tradeoffs Evaluated
- We kept an optional `onToggleDebugMode` prop on `ChatWindow` even though the component no longer uses it. This avoided a wider immediate cleanup pass and reduced risk during the task, at the cost of a small leftover interface cleanup candidate.
- We accepted a lint warning for existing unused `SIDEBAR_WIDTH` rather than expanding scope to do unrelated cleanup in a behavior-focused task.
- We prioritized issue-scoped test updates (control relocation, condensed bar, sidebar auto-close) and did not add extra broad regression suites beyond `make frontend-verify`.

## What I'm Uncertain About
- Keeping `onToggleDebugMode` in `ChatWindow` props was a coin flip between strict cleanup now vs. minimal-diff safety.
- With more context, I would likely remove unused `SIDEBAR_WIDTH` in the same patch if the team treats warning-free lint as strict policy.
- Edge case not directly exercised by tests: desktop back-navigation path through the new PDF header back button in all document/workspace permutations.
- Edge case not directly validated manually: environments where localStorage access is blocked/denied.

## Relevant Code Pointers
- frontend/lib/hooks/useDashboardState.ts > 23
- frontend/lib/hooks/useDashboardState.ts > 364
- frontend/lib/hooks/useDashboardState.ts > 602
- frontend/app/dashboard/page.tsx > 296
- frontend/app/dashboard/page.tsx > 458
- frontend/app/components/dashboard/PdfViewer.tsx > 20
- frontend/app/components/dashboard/PdfViewer.tsx > 449
- frontend/app/components/dashboard/ChatWindow.tsx > 157
- frontend/app/dashboard/__tests__/page.test.tsx > 725
- frontend/app/dashboard/__tests__/page.test.tsx > 815
