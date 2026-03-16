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

Replaced the plain `<p>` renderer for assistant chat messages in `ChatWindow.tsx` with `ReactMarkdown` + `remark-gfm`, scoped inside a `.chat-prose` div with manually written dark-theme styles in `globals.css`. Added a blinking `|` streaming cursor while a response is actively typing, hover timestamps on history bubbles via the `title` attribute, and a `markdownComponents` override that strips unsafe link protocols (`javascript:`, `data:`, etc.) so assistant content can never produce a clickable injection payload.

## Top 3 Decisions and Why

1. **Manual `.chat-prose` styles instead of `@tailwindcss/typography`** — The `prose` plugin assumes light backgrounds and injects its own color system. Writing the styles manually took about 60 extra lines but gave exact control over dark zinc backgrounds without fighting plugin defaults or adding a new dependency.

2. **Protocol allowlist via `components` prop instead of `rehype-sanitize`** — The issue locked out `rehype-raw` (which opens arbitrary HTML injection). `rehype-sanitize` would have been safe but added another dependency and a full HTML sanitization pass for a problem that only needed one targeted fix: `<a>` elements. Overriding the `a` component with a regex test against `^(https?:\/\/|mailto:)` is explicit, auditable, and zero-dependency.

3. **`created_at` on `ChatMessage` populated only from history, not from streamed messages** — Timestamps come from the server, so live-streamed messages don't have one until the next history reload. Rather than fake a client-side timestamp (which would differ from server time and cause confusion), we leave `created_at` undefined for streamed messages and show no `title`. The issue explicitly accepted this tradeoff.

## Non-Obvious Patterns Used

- **`components` prop in react-markdown** — `ReactMarkdown` accepts a `components` map where each key is an HTML element name and the value is a React component that receives the element's normal props. This lets you intercept any rendered element without touching the markdown parsing layer. It's the correct extension point for security overrides — you're not changing what gets parsed, only how specific output elements render.

- **`className` on `ReactMarkdown` doesn't exist (v9+)** — In older versions `ReactMarkdown` accepted `className` directly. In v9+ it doesn't — you must wrap in a container `div` and put the class there. This is a common gotcha that produces a TypeScript error that looks confusing at first.

- **`@keyframes` inside `@layer components`** — Keyframe animations can be declared inside a `@layer` block in Tailwind v4. The `blink` keyframe is scoped inside `@layer components` alongside `.streaming-cursor` so they ship together and don't pollute the global animation namespace.

- **`step-start` timing function** — The streaming cursor uses `animation: blink 1s step-start infinite`. `step-start` jumps instantly at each step rather than easing, which produces a crisp on/off blink rather than a fade. This matches the classic terminal cursor feel.

## Tradeoffs Evaluated

- **`title` attribute vs. visible timestamp label** — A visible label (e.g., "Sent at 2:03 PM") adds noise to every bubble. `title` gives the timestamp on hover only, which is how most chat apps handle it (iMessage, Slack). The tradeoff is that it's not keyboard-accessible and invisible on touch devices. Accepted because this is a desktop-focused dev portfolio app, not a product targeting all users.

- **Wrapping `ReactMarkdown` in a `div` vs. forwarding refs** — Wrapping adds one extra DOM element. The alternative is using `ReactMarkdown`'s `components` to make the root element carry the class. Both work; the `div` wrapper is simpler and doesn't require mapping every possible root element ReactMarkdown might emit.

- **Regex vs. URL constructor for protocol check** — `new URL(href).protocol` would be more robust (handles edge cases like `JAVASCRIPT:` with unusual casing), but the regex `/^(https?:\/\/|mailto:)/i` uses the `i` flag which handles mixed-case fine and avoids a `try/catch` around URL construction for invalid hrefs. For this surface (Anthropic API output) it's sufficient.

## What I'm Uncertain About

- The streaming cursor animates on every token update because `msg.streaming && msg.content` re-renders the whole bubble. For very long responses with many tokens, this could cause unnecessary repaints. A `useMemo` on the markdown render or splitting the cursor into a sibling component might help, but it wasn't measurable without profiling.

- `.chat-prose` styles are not tested for visual correctness — the 8 new tests verify DOM structure (element types, attributes) but not that the CSS actually applies. CSS-in-JS tests or visual regression snapshots (Playwright/Percy) would catch regressions here; they weren't added because the project has no visual regression infrastructure.

- `title` tooltip behavior is browser/OS-dependent. On macOS Safari it appears with a delay; on touch devices it doesn't appear at all. This is acceptable for now but would need a custom tooltip component if the requirement ever extends to mobile.

## Relevant Code Pointers

- `frontend/app/components/dashboard/ChatWindow.tsx` > line 44 — `markdownComponents` definition with protocol allowlist
- `frontend/app/components/dashboard/ChatWindow.tsx` > line 231 — assistant message render branch: `ReactMarkdown` + `.chat-prose` wrapper + streaming cursor span
- `frontend/app/components/dashboard/ChatWindow.tsx` > line 222 — `title={msg.created_at ? formatDate(msg.created_at) : undefined}` on bubble div
- `frontend/lib/hooks/useChatState.ts` > line 10 — `created_at?: string` on `ChatMessage` interface
- `frontend/lib/hooks/useChatState.ts` > line 302 — `created_at: msg.created_at` populated during history map
- `frontend/app/globals.css` > `.chat-prose` block — scoped dark-theme markdown styles
- `frontend/app/globals.css` > `.streaming-cursor` + `@keyframes blink` — cursor animation
- `frontend/app/components/dashboard/__tests__/ChatWindow.markdown.test.tsx` > line 77 — unsafe-link regression tests (javascript: and data: blocking)
