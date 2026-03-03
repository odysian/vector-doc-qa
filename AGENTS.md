# AGENTS.md

## Start Here (Canonical Entrypoint)

`AGENTS.md` is the canonical entrypoint for agents and contributors in this repository.

Read in this order:
1. `AGENTS.md` (this file)
2. `WORKFLOW.md`
3. `docs/ISSUES_WORKFLOW.md`
4. `docs/ARCHITECTURE.md`
5. `docs/PATTERNS.md`
6. `docs/REVIEW_CHECKLIST.md`
7. `skills/write-spec.md`
8. `skills/spec-to-issues.md`
9. `skills/issue-to-pr.md`
10. `skills/spec-workflow-gh.md`

## Unit of Work Rule

- **Unit of work is a GitHub Issue.**
- Choose an execution mode from `docs/ISSUES_WORKFLOW.md` before coding:
  - `single` (default): one feature -> one Task issue -> one PR
  - `gated`: Spec issue + child Task issue(s) for feature sets or higher-risk work
  - `fast`: quick-fix path for tiny low-risk changes
- Convert freeform requests into the selected issue mode before implementation.
- Work one Task issue at a time.
- PRs close Task issues (`Closes #123`), not Specs.
- Specs close only when all child Tasks are done or explicitly deferred.
- Detailed control-plane rules are canonical in `docs/ISSUES_WORKFLOW.md`.
- For one-shot issue body + `gh` command generation, use `skills/spec-workflow-gh.md`.
- Canonical single-line kickoff prompt:
  - `Run kickoff for feature <feature-id> from <filename> mode=<single|gated|fast>.`
  - If `mode` is omitted, default to `single`.
  - Expected output: issue body file(s), `gh issue create` command(s), created issue link(s), and a 3-5 step implementation plan.

## Agent Operating Loop

1. Whiteboard scope in `plans/*.md` or spec docs (scratch only).
2. Choose execution mode (`single` default, `gated`, or `fast`) and create required issue(s).
3. Restate goal and acceptance criteria.
4. Plan minimal files and scope.
5. Implement with tight, surgical changes.
6. Run verification commands.
7. Update tests/docs if required.
8. Open PR that closes the Task issue; close Spec after child Tasks are done/deferred.

## Process

Read and follow `WORKFLOW.md` for the full development process and `docs/ISSUES_WORKFLOW.md` for the issue-control execution modes. Together they define the Design -> Test -> Implement -> Review -> Document loop, TDD workflow, technical constraints (SQLAlchemy 2.0, Pydantic v2, async patterns), security requirements, and documentation maintenance rules.

This file contains **project-specific rules** that supplement WORKFLOW.md. If they conflict, this file wins.

---

## Project Context

Quaero is an AI-powered PDF question-answering platform that uses Retrieval Augmented Generation (RAG) to let users upload documents, ask natural language questions, and get answers with cited sources.

**Stack:** FastAPI backend, Next.js 16 + React 19 frontend, PostgreSQL + pgvector, OpenAI embeddings, Anthropic RAG responses.

**Deviations from WORKFLOW.md defaults:**

- **Dual DB drivers.** The app uses `asyncpg` for all async database operations. `psycopg2-binary` is kept solely for Alembic migrations (which run synchronously). Both drivers are in requirements.txt.
- **Next.js, not Vite.** Frontend uses Next.js App Router, but all pages are client components (`"use client"`). No server components or server-side data fetching are used.
- **Argon2, not bcrypt.** Password hashing uses `argon2-cffi` via passlib, not bcrypt.
- **Auth tokens in httpOnly cookies.** `access_token` and `refresh_token` are stored in httpOnly cookies (path-scoped: `/api/` and `/api/auth/` respectively). A readable `csrf_token` cookie is set at `/` and echoed as `X-CSRF-Token` on mutating requests (double-submit CSRF pattern). Because frontend and backend are on different domains, the frontend stores the `csrf_token` value from login/refresh JSON responses in `localStorage` (see ADR-001).
- **INTEGER primary keys.** Models use `Integer` primary keys, not `BigInteger` as WORKFLOW.md specifies.
- **Schema isolation.** Database uses `quaero` schema, not the default `public` schema.
- **No token expiration.** `access_token_expire_minutes` is set to `0` (no expiration) in config.

---

## Core Rules

- **Simplicity first.** Write the minimum code that solves the problem. No features beyond what was asked. No abstractions for single-use code. No speculative flexibility.
- **Surgical changes only.** Touch only what the task requires. Do not improve adjacent code, comments, or formatting. Match existing style.
- **Explain what you're doing.** Include brief comments explaining why for non-obvious logic.
- **Prefer explicit over clever.** Readable, straightforward code. No one-liners that sacrifice clarity.

## Decision Brief (Required)

For non-trivial fixes/features, include a short decision brief before completion:

- **Chosen approach:** what was implemented.
- **Alternative considered:** one realistic alternative.
- **Tradeoff:** why this choice won (complexity/risk/perf/security).
- **Revisit trigger:** when the alternative should be reconsidered.

For tiny quick fixes, a one-line brief is enough: chosen approach + primary risk.

---

## Verification

Before considering any task complete, run the relevant checks:

### Backend

Preferred: run from repo root:
```bash
make backend-verify
```

If needed, run individual commands from `backend/`:
```bash
cd backend

# Lint
ruff check .

# Type check
mypy . --ignore-missing-imports

# Run tests
pytest -v

# Security check
bandit -r app/ -ll
```

### Frontend

Preferred: run from repo root:
```bash
make frontend-verify
```

If needed, run individual commands from `frontend/`:
```bash
cd frontend

# Type check
npx tsc --noEmit

# Run tests
npm test

# Lint
npx next lint

# Build
npm run build
```

### Database

```bash
cd backend

# Verify migrations
alembic check

# Test migration up/down
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

If any check fails, fix before moving on.

### Documentation (after every feature)

- [ ] **docs/ARCHITECTURE.md** — Update if you changed DB schema, API endpoints, system diagram, or infrastructure.
- [ ] **docs/PATTERNS.md** — Update if you introduced or changed a code convention.
- [ ] **docs/REVIEW_CHECKLIST.md** — Update if the feature introduced a new category of checks.
- [ ] **docs/ISSUES_WORKFLOW.md** — Update if issue workflow rules changed.
- [ ] **TESTPLAN.md** — Update before writing any new tests.
- [ ] **docs/adr/** — Create a new numbered ADR if you chose between competing approaches, resolved a non-obvious production issue, or made a decision with lasting security/performance consequences.

Edit the specific section that changed. Do not rewrite entire files.

---

## File Structure

See `docs/ARCHITECTURE.md` for the full directory tree.

### Backend (`backend/`)

- **App entry** -> `app/main.py`
- **Config** -> `app/config.py`, `app/constants.py`
- **Database** -> `app/database.py`
- **Models** -> `app/models/` (`base.py`, `user.py`, `message.py`, `refresh_token.py`)
- **Schemas** -> `app/schemas/`
- **Routes** -> `app/api/` (`auth.py`, `documents.py`, `dependencies.py`)
- **Services** -> `app/services/`
- **Security** -> `app/core/security.py`
- **Utilities** -> `app/utils/`
- **Workers** -> `app/workers/`
- **Migrations** -> `alembic/versions/`

### Frontend (`frontend/`)

- **Pages** -> `app/page.tsx`, `app/login/page.tsx`, `app/register/page.tsx`, `app/dashboard/page.tsx`
- **Layout** -> `app/layout.tsx`
- **Components** -> `app/components/dashboard/`
- **API client** -> `lib/api.ts`, `lib/api.types.ts`
- **Styles** -> `app/globals.css`

---

## Planning & Execution

### Think before coding

- State assumptions explicitly. If uncertain, ask.
- If multiple valid approaches exist, present them; do not pick silently.
- If a simpler approach exists, say so.
- If something is unclear, stop and ask.

### When a task is vague or spans multiple files

1. Plan first: outline files, data flow, and API contracts as a checklist.
2. Get approval before writing code.
3. Execute step by step and verify after each step.

### When a task is clear and scoped

Execute directly. No plan needed. Verify and report.

### Issues Workflow (Control Plane)

- Choose mode first: `single` (default), `gated` (Spec + Tasks), or `fast` (tiny low-risk fixes).
- Default sizing in issue modes: 1 feature -> 1 Task -> 1 PR unless split criteria apply.
- GitHub issues are the execution source of truth. `TASKS.md` is scratchpad-only if present.
- Follow canonical rules in `docs/ISSUES_WORKFLOW.md` for DoR/DoD.
- Decision Locks live in the controlling issue (Task in `single`, Spec in `gated`).
- If a decision has lasting architecture/security/performance impact, create and link an ADR (`docs/adr/NNN-kebab-case-title.md`).

### Goal-driven execution

Transform tasks into verifiable goals before coding:

- "Add validation" -> "Write tests for invalid inputs, then make them pass"
- "Fix the bug" -> "Write a test that reproduces it, then make it pass"
- "Refactor X" -> "Ensure tests pass before and after"

---

## Common Mistakes to Avoid

_Add to this section when the agent makes a mistake. Each line prevents a repeat._

- **Do not install packages without asking first.** State what and why. Wait for approval.
- **Do not create `.env` files with real secrets.** Use `.env.example` with placeholders.
- **Do not add dependencies that duplicate existing functionality.** Check what's installed.
- **Do not modify migration files after they've been applied.** Create a new one.
- **Before running `gh` issue/PR commands, run preflight once per session:** `gh auth status`, `gh repo set-default odysian/vector-doc-qa`, `gh repo view --json nameWithOwner,url`.
- **If `gh` fails with transient API connectivity errors, retry 2-3 times, then use the equivalent `gh api` endpoint as fallback.**
- **When using `gh api` with query strings in zsh, quote the endpoint string to avoid shell globbing.**

---

## Skill Governance

Keep external skills high-signal and conflict-free:

- Precedence order: `AGENTS.md` -> `WORKFLOW.md` -> `docs/ISSUES_WORKFLOW.md` -> local `skills/*` -> external installed skills.
- Install external skills globally in Codex home, not inside project repos.
- Keep a small baseline (about 4-6 active external skills).
- Use skills intentionally (named skill or clear task match), not by default for every request.
- Avoid overlap: keep one primary skill per domain.
- If an external skill conflicts with repo docs, follow repo docs and treat the skill as advisory.
- Review and prune unused or low-value skills regularly.

---

## ADR Format

Architecture Decision Records live in `docs/adr/` and capture decisions with lasting consequences. Use ADR-001 as the canonical example.

**When to write one:**
- You chose between two or more real alternatives.
- A production issue revealed a design flaw that required a deliberate fix.
- The decision has non-obvious security, performance, or correctness implications.
- Future contributors would reasonably question why something was done this way.

**When NOT to write one:**
- Routine feature additions with no competing approaches.
- Bug fixes with a single obvious solution.
- Anything fully covered by PATTERNS.md.

**File naming:** `NNN-kebab-case-title.md` (three-digit sequence number).

**Required sections:**

```
# ADR-NNN: Short Title

**Date:** YYYY-MM-DD
**Status:** Accepted | Applied | Superseded by ADR-XXX
**Branch:** branch-name-or-pr

---

## Context

### Background
[What is the relevant architecture or system state?]

### Problem
[What specific issue or requirement triggered this decision?]

### Root Cause (if a bug or production incident)
[Why did the problem occur?]

---

## Options Considered

### Option A: Name
[Description. Accepted/Rejected, and why.]

### Option B: Name
[Description. Accepted/Rejected, and why.]

---

## Decision

[Numbered list of what was implemented and how.]

---

## Consequences

[Bullet list: what is now true as a result, including tradeoffs, edge cases, and any new risks introduced.]
```

---

_Living document. When the agent does something wrong, add a rule. The goal: never the same mistake twice._
