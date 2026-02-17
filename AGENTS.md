# AGENTS.md

## Process

Read and follow `WORKFLOW.md` for the full development process — it defines the Design → Test → Implement → Review → Document loop, TDD workflow, technical constraints (SQLAlchemy 2.0, Pydantic v2, async patterns), security requirements, and documentation maintenance rules.

This file contains **project-specific rules** that supplement WORKFLOW.md. If they conflict, this file wins.

---

## Project Context

Quaero is an AI-powered PDF question-answering platform that uses Retrieval Augmented Generation (RAG) to let users upload documents, ask natural language questions, and get answers with cited sources.

**Stack:**

- Backend: FastAPI (Python 3.12+, async/await throughout)
- Frontend: Next.js 16 (App Router) + React 19 + TypeScript
- Database: PostgreSQL with pgvector extension (Render, `quaero` schema)
- ORM: SQLAlchemy 2.0 (async with `asyncpg` driver)
- Auth: JWT (HS256) with Argon2 password hashing
- AI: OpenAI API (text-embedding-3-small for embeddings), Anthropic API (Claude for RAG answers)
- Deployment: Vercel (frontend) + Render (backend + PostgreSQL)

**Deviations from WORKFLOW.md defaults:**

- **Dual DB drivers.** The app uses `asyncpg` for all async database operations. `psycopg2-binary` is kept solely for Alembic migrations (which run synchronously). Both drivers are in requirements.txt.
- **Next.js, not Vite.** Frontend uses Next.js App Router, but all pages are client components (`"use client"`). No server components or server-side data fetching are used.
- **Argon2, not bcrypt.** Password hashing uses `argon2-cffi` via passlib, not bcrypt.
- **Auth tokens in localStorage.** Tokens are stored in `localStorage` and sent via `Authorization: Bearer` header, not httpOnly cookies.
- **INTEGER primary keys.** Models use `Integer` primary keys, not `BigInteger` as WORKFLOW.md specifies.
- **Schema isolation.** Database uses `quaero` schema, not the default `public` schema. This is for multi-project sharing on a single Render PostgreSQL instance.
- **No token expiration.** `access_token_expire_minutes` is set to `0` (no expiration) in config.

---

## Core Rules

- **Simplicity first.** Write the minimum code that solves the problem. No features beyond what was asked. No abstractions for single-use code. No speculative flexibility. If you write 200 lines and it could be 50, rewrite it.
- **Surgical changes only.** Touch only what the task requires. Don't "improve" adjacent code, comments, or formatting. Match existing style. If you notice unrelated issues, mention them — don't fix them. Every changed line should trace to the user's request.
- **Explain what you're doing.** Include brief comments explaining _why_ for non-obvious logic. This is a learning environment.
- **Prefer explicit over clever.** Readable, straightforward code. No one-liners that sacrifice clarity.

---

## Verification

### Backend

```bash
cd backend

# Lint
ruff check .

# Type check
mypy . --ignore-missing-imports

# Run tests (when tests exist)
pytest -v

# Security check
bandit -r app/ -ll
```

### Frontend

```bash
cd frontend

# Type check
npx tsc --noEmit

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

- [ ] **ARCHITECTURE.md** — Update if you changed: DB schema, API endpoints, system diagram, or infrastructure.
- [ ] **PATTERNS.md** — Update if you introduced or changed a code convention.
- [ ] **REVIEW_CHECKLIST.md** — Update if the feature introduced a new category of checks.
- [ ] **TESTPLAN.md** — Update before writing any new tests.

Edit the specific section that changed. Do not rewrite entire files.

---

## File Structure

_See docs/ARCHITECTURE.md for the full directory tree._

### Backend (`backend/`)

- **App entry** → `app/main.py`
- **Config** → `app/config.py`, `app/constants.py`
- **Database** → `app/database.py`
- **Models** → `app/models/` (`base.py` for Document/Chunk, `user.py`, `message.py`)
- **Schemas** → `app/schemas/` (`document.py`, `auth.py`)
- **Routes** → `app/api/` (`auth.py`, `documents.py`, `dependencies.py`)
- **Services** → `app/services/` (`document_service.py`, `search_service.py`, `embedding_service.py`, `anthropic_service.py`)
- **Security** → `app/core/security.py`
- **Utilities** → `app/utils/` (`file_utils.py`, `pdf_utils.py`, `rate_limit.py`)
- **Migrations** → `alembic/versions/`

### Frontend (`frontend/`)

- **Pages** → `app/page.tsx` (landing), `app/login/page.tsx`, `app/register/page.tsx`, `app/dashboard/page.tsx`
- **Layout** → `app/layout.tsx`
- **Components** → `app/components/dashboard/` (`ChatWindow.tsx`, `DocumentList.tsx`, `UploadZone.tsx`, `DeleteDocumentModal.tsx`)
- **API client** → `lib/api.ts`, `lib/api.types.ts`
- **Styles** → `app/globals.css` (Tailwind + custom lapis theme)

---

## Planning & Execution

### Think before coding

- State assumptions explicitly. If uncertain, ask.
- If multiple valid approaches exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop and ask.

### Vague or multi-file tasks

1. Plan first — outline files, data flow, API contracts as a checklist.
2. Get approval before writing code.
3. Execute step by step, verify after each step.

### Clear, scoped tasks

Execute directly. No plan needed. Verify and report.

### Goal-driven execution

Transform tasks into verifiable goals before coding:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

---

## Common Mistakes to Avoid

_Add to this section when the agent makes a mistake. Each line prevents a repeat. These are project-specific — generic rules live in WORKFLOW.md Section 9._

- **Do not install packages without asking first.** State what and why. Wait for approval.
- **Do not create `.env` files with real secrets.** Use `.env.example` with placeholders.
- **Do not add dependencies that duplicate existing functionality.** Check what's installed.
- **Do not modify migration files after they've been applied.** Create a new one.

---

_Living document. When the agent does something wrong, add a rule. The goal: never the same mistake twice._
