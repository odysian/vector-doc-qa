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
Task #210 polished the dashboard chat composer and compact header density without touching API contracts. The textarea is now one-line by default and auto-resizes up to a capped max height, while send/stop controls are compact icon-only buttons with explicit accessibility labels. I also updated streaming lifecycle tests to validate the new composer auto-resize behavior and to assert icon-only control semantics.

## Top 3 Decisions and Why
1. Use icon-only send/stop controls with `title` + `aria-label` in `ChatWindow` - this satisfies the compact UI requirement while preserving screen-reader accessibility and keyboard discoverability.
2. Implement inline resize logic in `ChatWindow` (`useCallback` + `useEffect` on input) rather than introducing a new dependency - this keeps the change local and avoids refactoring risk outside task scope.
3. Add targeted DOM-style assertions in `ChatWindow.streaming.test.tsx` - this directly validates the new behavior that now exists in component logic and lowers regression risk on future refactors.

## Non-Obvious Patterns Used
- The component treats layout as two concerns: visual sizing and state-driven behavior. `resizeComposer` reads `scrollHeight` from the DOM and enforces both height and overflow mode in one place, so behavior stays consistent across input changes.
- For textarea ergonomics, overflow is treated as a stateful UI affordance (`hidden` while under max, `auto` at cap), which avoids the constant scrollbar artifact while preserving access when the content actually exceeds the limit.
- The test helper `setComposerScrollHeight` mocks `scrollHeight` so UI sizing behavior can be validated deterministically in JSDOM despite browser layout differences.

## Tradeoffs Evaluated
- We traded perfect browser-like layout fidelity in unit tests for deterministic, fast regression checks using mocked `scrollHeight`; that improves CI speed but leaves one gap to real browser line-height rendering.
- We kept the icon-only send/stop markup change minimal (same state transitions, new glyphs) to avoid contract churn and preserve stream behavior in `useChatState` and related consumers.
- We accepted the pre-existing lint warning in `dashboard/page.tsx` as out-of-scope noise, so this patch stayed focused strictly on Task #210 scope.

## What I'm Uncertain About
- The autosize behavior is asserted with mocked `scrollHeight`; I would validate with browser-based testing if we see repeated field-height reports from users in real multi-line paste scenarios.
- Icon-only controls are visually compact and pass role/label tests, but I would still run a Playwright smoke test for touch target comfort across compact/mobile widths.
- If browser accessibility tooling later flags icon-only affordance touch-area nuances, I would adjust padding/size centrally in `ui-btn` styles rather than this component only.
- If this task were revisited with broader UI hardening, I would also add one focused visual acceptance test that verifies no default scrollbar is shown while the composer is below max height.

## Relevant Code Pointers
- frontend/app/components/dashboard/ChatWindow.tsx > 64
- frontend/app/components/dashboard/ChatWindow.tsx > 125
- frontend/app/components/dashboard/ChatWindow.tsx > 130
- frontend/app/components/dashboard/ChatWindow.tsx > 136
- frontend/app/components/dashboard/ChatWindow.tsx > 470
- frontend/app/components/dashboard/__tests__/ChatWindow.streaming.test.tsx > 28
- frontend/app/components/dashboard/__tests__/ChatWindow.streaming.test.tsx > 142
- frontend/app/components/dashboard/__tests__/ChatWindow.streaming.test.tsx > 150
