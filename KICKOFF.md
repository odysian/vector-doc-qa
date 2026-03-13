# Kickoff Prompts

Use these prompts to start an agent on already-scoped work with predictable output.

## 1) Execute Existing Task Issue

```text
Run kickoff for existing Task #<task-id> mode=single.

Then execute the full Task flow end-to-end:
1. Restate goal, non-goals, acceptance criteria, and exact verification commands from the issue.
2. Create/switch to branch `task-<id>-<slug>`.
3. Implement minimally and surgically, preserving existing contracts unless issue scope says otherwise.
4. Run relevant verification once after implementation.
5. Open PR with `Closes #<task-id>`.
6. Return the standardized reviewer follow-up prompt from section 3 in KICKOFF.md.
7. After review verdict is relayed back:
   - if verdict is `ACTIONABLE`: patch required fixes and rerun targeted verification only.
   - if verdict is `APPROVED`: write `docs/learning/YYYY-MM-DD-feature-slug-learning.md` using section 4 below, then return the file path and final completion summary.

Constraints:
- Keep mode `single` unless explicitly requested otherwise.
- No environment triage loops, no worktree setup, no broad verification reruns.
- Keep output concise and findings-first.
```

## 2) Planning-Only Kickoff (No Code Changes)

```text
Run kickoff for feature <feature-id> from <filename> mode=<single|gated|fast>, planning-only (no code changes, no PR).

Deliver:
1. Problem framing (goal, non-goals, constraints).
2. Proposed implementation plan (3-5 steps, smallest viable path first).
3. Risks and edge cases.
4. Acceptance criteria draft.
5. Verification plan (exact commands).
6. Recommended issue artifact markdown (Task/Spec as applicable) ready for `gh issue create --body-file` when applicable.

Constraints:
- Keep it lean and concrete.
- Default to one Task unless explicitly asked for split/gated mode.
- No speculative architecture.
```

Notes:
- If `mode=gated`, output Spec + default child Task issue bodies and commands.
- If `mode=fast`, output a quick-fix checklist and verification plan; no issue creation by default.

## 3) Standard Reviewer Follow-Up Prompt (Robust)

Use this exact prompt after opening a Task PR.

```text
Review Task #<task-id> / PR #<pr-id> on branch <task-branch> vs <base-branch>.

Goal:
- Identify correctness bugs, regressions, contract drift, boundary/pattern violations, and missing tests/docs.

Review Scope (in priority order):
1. Correctness and regressions (runtime behavior, edge cases, state transitions)
2. Contract parity (status codes, response shapes, error semantics, side effects) if scope claims no contract change
3. Architecture consistency (layer boundaries, dependency direction, service/repository responsibilities)
4. Security and performance risks introduced by this diff
5. Missing or weak tests/docs for changed behavior

Constraints:
- Use local diff and repository context first.
- No environment triage loops or worktree setup.
- Run targeted checks only when needed to validate a specific finding.
- Do not rerun broad verification already reported green unless prior results are suspect.
- Keep output concise and findings-first.
- No command transcript unless a command failed and that failure matters to a finding.

Required Output:
1. Verdict: APPROVED or ACTIONABLE
2. Findings (if ACTIONABLE), one per line with:
   [severity] file/path:line | category | issue | impact | required fix
   - severity: critical/high/medium/low
   - category: correctness|regression|contract|architecture|security|performance|tests|docs
3. Verification notes:
   - targeted checks run (if any) and why
4. Residual risk/testing gaps:
   - up to 5 concise bullets
```

## 4) Required Learning Handoff Template (After APPROVED)

Use this after explicit reviewer verdict `APPROVED` is provided back to the implementation agent.

Filename and location:
- `docs/learning/YYYY-MM-DD-feature-slug-learning.md`

The following header block is static and must be copied verbatim at the top of every generated learning handoff:

```text
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
```

Everything below the header is agent-generated per task/spec.

Required section order below the header:

```text
## What Was Built
- 2-3 sentences describing what was delivered.

## Top 3 Decisions and Why
1. <decision> - <why>
2. <decision> - <why>
3. <decision> - <why>

## Non-Obvious Patterns Used
- Patterns a junior dev might not immediately recognize, with plain-English explanation.

## Tradeoffs Evaluated
- Options considered and why one was chosen.

## What I'm Uncertain About
- Any decisions that felt like a coin flip
- Anything I'd do differently with more context
- Edge cases I didn't handle and why

## Relevant Code Pointers
- Use `filename > line number` entries for web-chat/no-IDE contexts.
```
