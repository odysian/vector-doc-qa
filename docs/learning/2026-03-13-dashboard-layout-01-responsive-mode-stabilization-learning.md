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
- Replaced dashboard responsive layout detection with explicit modes: `mobile`, `compact`, and `desktop`, driven by `matchMedia` at 1024px and 1150px.
- Updated dashboard rendering to derive tabbed vs split layout from `layoutMode`, and standardized sidebar behavior to overlay for mobile/compact and push/collapse only for desktop.
- Adjusted desktop split pane ratios to 60/40 and added a `min-w-72` floor for the chat pane, then added layout tests that assert mode transitions and sidebar behavior.

## Top 3 Decisions and Why
1. Use `matchMedia` breakpoint listeners instead of width hysteresis + `ResizeObserver` - this reduces oscillation complexity and updates only on breakpoint crossings.
2. Export `LayoutMode` from the hook and derive `useTabLayout` in `page.tsx` - this keeps the hook contract explicit while allowing view-specific derived booleans.
3. Keep all sidebar responsive class logic in `page.tsx` - this matches the task requirement and avoids scattered breakpoint behavior across components.

## Non-Obvious Patterns Used
- Ordered media-query evaluation pattern: check desktop threshold first, then compact, then fallback to mobile so mode precedence is deterministic.
- Contract narrowing pattern in hooks: expose higher-signal state (`layoutMode`) and let consumers derive coarse booleans (`layoutMode !== "desktop"`).
- Deterministic responsive test harness: a custom `matchMedia` mock with mutable `window.innerWidth` to trigger listeners exactly at 1024/1150 boundaries.

## Tradeoffs Evaluated
- Removing hysteresis simplifies behavior and prevents threshold-band drift, but relies on strict breakpoint crossings and assumes stable media-query support.
- JS-driven mode classes in `page.tsx` improve control at 1150, but reduce reliance on pure Tailwind breakpoint utilities and require tests for class composition.
- Keeping existing `xl` spacing classes avoided broad styling churn, but leaves a visual transition band (1150-1279) that should be manually validated.

## What I'm Uncertain About
- Browser-specific viewport transition behavior should still be manually validated around 1024/1150 in Safari and Chrome during real resizing.
- We did not add fallback handling for environments with missing/partial `matchMedia` behavior beyond a no-op guard.
- Layout padding still changes at `xl` (1280) while split-mode now starts at 1150, so visual density from 1150-1279 may need a follow-up tuning task.

## Relevant Code Pointers
- frontend/lib/hooks/useDashboardState.ts > 19
- frontend/lib/hooks/useDashboardState.ts > 26
- frontend/lib/hooks/useDashboardState.ts > 306
- frontend/app/dashboard/page.tsx > 129
- frontend/app/dashboard/page.tsx > 285
- frontend/app/dashboard/page.tsx > 403
- frontend/app/dashboard/__tests__/page.test.tsx > 142
- frontend/app/dashboard/__tests__/page.test.tsx > 705
- frontend/app/dashboard/__tests__/page.test.tsx > 744
