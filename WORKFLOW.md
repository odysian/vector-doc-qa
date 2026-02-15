# WORKFLOW.md — Agentic Development Process

This document defines the complete development workflow for all projects. Any agent working on this codebase must read and follow this document. It covers project setup, architecture design, test-driven development, implementation, code review, and documentation maintenance.

The developer (Chris) is a backend/full-stack developer building production applications. The workflow is designed for AI-assisted development where the developer architects and reviews, and agents implement and verify. Every feature follows the same loop: **Design → Test → Implement → Review → Document.**

---

## Table of Contents

1. [Project Setup](#1-project-setup)
2. [Architecture-First Design](#2-architecture-first-design)
3. [Test-Driven Development](#3-test-driven-development)
4. [Implementation](#4-implementation)
5. [Code Review & Verification](#5-code-review--verification)
6. [Documentation Maintenance](#6-documentation-maintenance)
7. [Technical Constraints](#7-technical-constraints)
8. [Security Requirements](#8-security-requirements)
9. [Agent Operating Rules](#9-agent-operating-rules)

---

## 1. Project Setup

### Workspace Structure

Every project follows this layout. Create it at project initialization before writing any application code.

```
project-root/
├── AGENTS.md                  # Agent behavior rules (root level — auto-read by Cursor)
├── TASKS.md                   # Current sprint tasks (GITIGNORED)
├── TESTPLAN.md                # Test case definitions (GITIGNORED)
├── docs/
│   ├── ARCHITECTURE.md        # System design, schemas, API contracts
│   ├── PATTERNS.md            # Code conventions and reusable patterns
│   └── REVIEW_CHECKLIST.md    # Post-implementation verification checklist
├── tests/
│   ├── conftest.py            # Shared fixtures, test DB setup, factories
│   ├── test_auth.py           # Tests organized by domain
│   └── ...
├── .gitignore                 # Must include TASKS.md, TESTPLAN.md
├── README.md                  # Includes AI Review Log section
└── src/ or app/               # Application code
```

### .gitignore Requirements

Always include these entries:

```
TASKS.md
TESTPLAN.md
.env
.env.local
.env.production
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
venv/
.venv/
node_modules/
.next/
.cursor/
.DS_Store
```

### Initial File Creation

When starting a new project, create all workspace files immediately with placeholder content. Do not wait until the project is "far enough along." The files guide development from the first line of code.

**AGENTS.md** — Start with the baseline rules (see Section 9). Add project-specific rules as mistakes are discovered during development.

**docs/ARCHITECTURE.md** — Populated during the whiteboard/design phase BEFORE any implementation begins. This file is the implementation spec, not post-hoc documentation.

**docs/PATTERNS.md** — Starts mostly empty. Populated after the first 3-4 features are built by scanning the codebase for established conventions.

**docs/REVIEW_CHECKLIST.md** — Starts with the generic checklist. Updated with project-specific checks after the first feature is reviewed.

**TASKS.md** — Populated with the first sprint of agent-sized tasks after the design phase.

**TESTPLAN.md** — Populated feature-by-feature during the design phase, before implementation.

**README.md** — Created at project start with project overview. Includes an "AI Review Log" section that is updated throughout development (see Section 6).

---

## 2. Architecture-First Design

### Purpose

ARCHITECTURE.md is not documentation — it is the **implementation specification**. It must be specific enough that an agent can implement features directly from it with minimal clarification. Vague architecture produces vague code. Precise architecture produces correct code on the first pass.

### When to Write It

ARCHITECTURE.md is written BEFORE any application code. The developer whiteboard the system design with Claude, then the output is structured into the file. This is the most important step in the entire workflow — everything downstream depends on it.

### What It Must Contain

#### System Overview

One paragraph explaining what the application does, who it is for, and what problem it solves. Written so a non-technical person could understand it.

#### Tech Stack Table

Every technology choice with a reason. No technology is used "just because."

```markdown
| Layer      | Technology              | Why                                           |
| ---------- | ----------------------- | --------------------------------------------- |
| Frontend   | Next.js 14 + TypeScript | App Router, server components, type safety    |
| Backend    | FastAPI (Python 3.11+)  | Async, auto-docs, Pydantic validation         |
| Database   | PostgreSQL 16           | Relational, pgvector for embeddings if needed |
| ORM        | SQLAlchemy 2.0          | Async support, type-safe queries              |
| Auth       | JWT (access + refresh)  | Stateless, standard                           |
| Deployment | Vercel + Render         | Free tier, separate frontend/backend          |
```

#### System Diagram

ASCII diagram showing all components, how they connect, and the direction of data flow. Include external services (APIs, file storage, etc.).

```
[Browser] → [Next.js Frontend (Vercel)]
                    |
                    v  (REST API / WebSocket)
            [FastAPI Backend (Render)]
                    |
                    v
            [PostgreSQL (Supabase)]
                    |
                    v (if applicable)
            [Redis Cache] / [S3 Storage] / [External APIs]
```

#### Database Schema (COMPLETE)

Every table, every column, every relationship. This is the single source of truth for the data model.

```markdown
### users

| Column        | Type         | Constraints               |
| ------------- | ------------ | ------------------------- |
| id            | BIGINT       | PK, auto-increment        |
| email         | VARCHAR(255) | UNIQUE, NOT NULL, indexed |
| password_hash | VARCHAR(255) | NOT NULL                  |
| display_name  | VARCHAR(100) | NOT NULL                  |
| created_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now()   |
| updated_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now()   |

### rooms

| Column     | Type         | Constraints                      |
| ---------- | ------------ | -------------------------------- |
| id         | BIGINT       | PK, auto-increment               |
| name       | VARCHAR(100) | NOT NULL                         |
| created_by | BIGINT       | FK → users.id, ON DELETE CASCADE |
| created_at | TIMESTAMPTZ  | NOT NULL, DEFAULT now()          |

### Relationships

- users → rooms: one-to-many (user creates rooms)
- users ↔ rooms: many-to-many through room_members
```

Include indexes explicitly:

```markdown
### Indexes

| Table        | Column(s)           | Type   | Why                          |
| ------------ | ------------------- | ------ | ---------------------------- |
| users        | email               | UNIQUE | Login lookup                 |
| messages     | room_id, created_at | BTREE  | Message history queries      |
| room_members | user_id, room_id    | UNIQUE | Prevent duplicate membership |
```

#### API Contracts (COMPLETE)

Every endpoint with method, path, auth requirement, request body, response body, and error responses.

````markdown
### POST /api/auth/register

- **Auth:** None (public)
- **Request Body:**
  ```json
  { "email": "string", "password": "string", "display_name": "string" }
  ```
````

- **Success Response (201):**
  ```json
  { "id": 1, "email": "user@example.com", "display_name": "Chris" }
  ```
- **Error Responses:**
  - 422: Validation error (missing fields, invalid email format)
  - 409: Email already registered

````

#### Key Decisions
Document architectural decisions with context on what was considered and why the choice was made.

```markdown
| Decision                    | Choice            | Alternatives Considered  | Why                                    |
|----------------------------|-------------------|-------------------------|----------------------------------------|
| Auth token storage          | httpOnly cookie   | localStorage             | XSS protection                          |
| Message loading             | Pagination (cursor)| Load all                | Performance with large message history  |
| Real-time updates           | WebSocket         | Polling, SSE             | Bidirectional, low latency              |
````

### Updating ARCHITECTURE.md

The file is updated in two situations:

1. **During design** — when a new feature is planned, add its schema, endpoints, and decisions BEFORE implementation.
2. **After implementation** — if implementation diverged from the design (it often does), update the file to reflect what was actually built. The file must always match reality.

An agent may be asked to scan the codebase and update ARCHITECTURE.md to reflect the current state. When doing so, document ONLY what exists in the code, not assumptions.

---

## 3. Test-Driven Development

### The Core Rule

**No feature is implemented until its test cases are defined.** The sequence is always:

1. Developer defines test cases in TESTPLAN.md (during whiteboard with Claude)
2. Agent implements test code from the test plan
3. Agent implements feature code to pass the tests
4. Agent runs tests to self-verify
5. Developer reviews both tests and implementation

### Writing Test Cases (TESTPLAN.md)

Test cases are defined by the developer, not the agent. Each feature section includes five categories:

```markdown
## Feature: Create Room

### Happy Path

- POST /api/rooms with valid name returns 201 and room object
- Creator is automatically added to room_members
- Room appears in GET /api/rooms for the creator

### Error Cases

- Returns 401 if no auth token provided
- Returns 422 if room name is empty string
- Returns 422 if room name exceeds 100 characters
- Returns 409 if user already has a room with that name

### Edge Cases

- Room name with leading/trailing whitespace is trimmed
- Room name with unicode characters (emoji, accented letters) works
- Creating room immediately after deleting one with same name works

### Security Cases

- Cannot create a room with another user's ID in the request
- Request is rate limited (no more than 10 rooms per minute)

### Performance Considerations

- Room creation with 1000 existing rooms completes in < 200ms
```

### Implementing Tests

When an agent implements tests from TESTPLAN.md, it must follow these rules:

**Test Structure:** Every test uses Arrange-Act-Assert (AAA) pattern.

```python
async def test_create_room_returns_201_with_valid_name(client, auth_headers):
    # Arrange
    room_data = {"name": "Test Room"}

    # Act
    response = await client.post("/api/rooms", json=room_data, headers=auth_headers)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Room"
    assert "id" in data
```

**Test Naming:** Every test function name must describe the scenario and expected outcome. A developer should understand what failed from the test name alone without reading the test body.

```python
# GOOD - descriptive
test_create_room_returns_401_without_auth_token
test_create_room_returns_422_when_name_exceeds_100_chars
test_create_room_trims_whitespace_from_name

# BAD - vague
test_create_room
test_create_room_error
test_room_validation
```

**Assertions Must Be Specific:**

```python
# BAD - only checks status code
assert response.status_code == 200

# GOOD - checks status AND response content
assert response.status_code == 200
data = response.json()
assert data["name"] == "Test Room"
assert data["created_by"] == user.id
assert "id" in data
assert "created_at" in data
```

**Test Database:** Use a real PostgreSQL test database with transaction rollback, not SQLite or mocks. Each test runs inside a transaction that rolls back after the test completes.

```python
# conftest.py pattern
@pytest.fixture
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()
```

**Fixtures and Factories:** Use factory fixtures for test data. Never hardcode user IDs, emails, or other values that could collide.

```python
@pytest.fixture
async def test_user(db_session):
    user = User(
        email=f"test-{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
        display_name="Test User"
    )
    db_session.add(user)
    await db_session.flush()
    return user
```

**Test Organization:** One test file per domain, mirroring the router/service structure.

```
tests/
├── conftest.py          # Shared fixtures, DB setup, client fixture
├── test_auth.py         # Registration, login, token refresh
├── test_rooms.py        # Room CRUD, membership
├── test_messages.py     # Message sending, retrieval, unread counts
└── test_websocket.py    # WebSocket connection, real-time events
```

### Agent Self-Verification

After implementing tests AND feature code, the agent must run verification before considering the task complete:

```bash
# 1. Run the tests
pytest -v --tb=short

# 2. Check that tests actually fail without the feature
#    (Agent should note if all tests passed before implementation —
#    that means the tests are testing nothing)

# 3. Lint
ruff check .

# 4. Type check
mypy . --ignore-missing-imports

# 5. If frontend changes were made
npx tsc --noEmit
npx next lint
```

If any step fails, fix the issue before reporting completion. Do not leave broken tests, lint errors, or type errors for the developer to clean up.

---

## 4. Implementation

### Feature Implementation Flow

1. Read TESTPLAN.md for the current feature's test cases
2. Read docs/ARCHITECTURE.md for the schema, API contract, and design decisions
3. Read docs/PATTERNS.md for established conventions in this codebase
4. Implement tests first (they should fail — no feature code yet)
5. Implement feature code to pass the tests
6. Run full verification suite (tests, lint, types)
7. Report results including any tests that unexpectedly passed or failed

### One Task at a Time

Never implement multiple features in a single session. Each task from TASKS.md is one unit of work:

- One endpoint
- One component
- One database migration
- One test suite for one feature

If a feature requires changes across backend, database, and frontend, break it into separate tasks:

1. Database migration (schema change)
2. Backend endpoint (API implementation)
3. Backend tests (verify API behavior)
4. Frontend component (UI implementation)
5. Integration (connect frontend to backend)

### Code Organization

**Backend (FastAPI):**

```
app/
├── main.py              # App factory, middleware, CORS, lifespan
├── config.py            # Settings via pydantic-settings (BaseSettings)
├── database.py          # Async engine, async session factory, Base
├── models/              # SQLAlchemy 2.0 models (one file per domain)
│   ├── __init__.py      # Re-exports all models
│   ├── user.py
│   └── room.py
├── schemas/             # Pydantic v2 request/response models
│   ├── __init__.py
│   ├── user.py
│   └── room.py
├── routers/             # Route handlers — thin, delegates to services
│   ├── __init__.py
│   ├── auth.py
│   └── rooms.py
├── services/            # Business logic — all domain logic lives here
│   ├── __init__.py
│   ├── auth_service.py
│   └── room_service.py
├── dependencies/        # FastAPI Depends() functions
│   ├── __init__.py
│   ├── auth.py          # get_current_user
│   └── database.py      # get_db session
├── middleware/           # Custom middleware (logging, rate limiting)
└── utils/               # Pure helper functions
```

**Routers are thin.** They validate input (via Pydantic), call a service, and return the response. No business logic in routers.

```python
@router.post("/rooms", status_code=201, response_model=RoomResponse)
async def create_room(
    room_data: RoomCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await room_service.create_room(db, user, room_data)
```

**Services contain all business logic.** They receive a database session and validated data, perform operations, and return results or raise HTTPException.

**Frontend (Next.js App Router):**

```
src/
├── app/                     # App Router pages and layouts
│   ├── layout.tsx           # Root layout (providers, global styles)
│   ├── page.tsx             # Landing/home page
│   ├── (auth)/              # Auth route group
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   └── (dashboard)/         # Protected route group
│       ├── layout.tsx       # Dashboard layout with nav
│       └── rooms/
│           ├── page.tsx     # Room list
│           └── [id]/page.tsx # Single room
├── components/
│   ├── ui/                  # Generic primitives (Button, Input, Card)
│   └── features/            # Feature-specific (RoomList, MessageBubble)
├── lib/
│   ├── api.ts               # Centralized API client — all fetch calls go through here
│   ├── types.ts             # Shared TypeScript interfaces
│   └── utils.ts             # Pure helper functions
├── hooks/                   # Custom React hooks
│   └── use-auth.ts
└── styles/
    └── globals.css
```

---

## 5. Code Review & Verification

### Post-Implementation Review

After every implementation session, before committing, run through docs/REVIEW_CHECKLIST.md. The checklist covers:

**Security:** Input validation, auth checks, authorization (user can only access own data), no secrets in code, XSS prevention, SQL injection prevention, CORS configuration, rate limiting.

**Performance:** N+1 queries (check every query that loads related data), missing indexes, unnecessary data fetching, frontend re-render issues.

**Code Quality:** Error handling, type safety, edge cases, consistent patterns, no dead code, meaningful names.

**Database:** Migrations exist, migrations are reversible, foreign key ON DELETE behavior specified, indexes on queried columns.

**Tests:** Happy path, error path, and edge cases covered. Tests have specific assertions. Test names are descriptive.

### AI Review Log (README.md Section)

Every project README includes a section documenting specific instances where agent-generated code was reviewed and corrected. This serves two purposes: it proves code comprehension to hiring managers, and it creates a reference for future agent instructions.

Format:

```markdown
## AI Review Log

### N+1 Query in Unread Message Count (Feb 5, 2026)

**What the agent produced:** A query that fetched all rooms, then looped through each room to count unread messages with a separate query per room.
**The problem:** For a user in 20 rooms, this generated 21 database queries instead of 1.
**What I fixed:** Replaced with a single query using a subquery that counts unread messages per room and joins it to the room list.
**Lesson:** Always check ORM-generated queries for N+1 patterns when loading related data. Added `selectinload` as the default relationship loading strategy in PATTERNS.md.

### Hardcoded CORS Origin (Feb 12, 2026)

**What the agent produced:** `allow_origins=["*"]` in the CORS middleware configuration.
**The problem:** Wildcard CORS in production allows any website to make API requests, enabling CSRF attacks.
**What I fixed:** Changed to `allow_origins=[settings.FRONTEND_URL]` pulling from environment variable, with `["http://localhost:3000"]` only in development.
**Lesson:** Added rule to AGENTS.md: "Never use wildcard CORS. Always pull allowed origins from environment configuration."
```

### When the Agent Makes a Mistake

Every agent mistake triggers two updates:

1. **AGENTS.md** — Add a rule preventing the mistake from recurring
2. **AI Review Log** — Document the mistake, the fix, and the lesson

This is harness engineering. Over time, the AGENTS.md becomes increasingly specific and the agent produces increasingly correct output.

---

## 6. Documentation Maintenance

### Which Files Update When

| Event                               | Files to Update                                    |
| ----------------------------------- | -------------------------------------------------- |
| New feature designed                | ARCHITECTURE.md, TESTPLAN.md, TASKS.md             |
| Feature implemented                 | PATTERNS.md (if new convention), TASKS.md          |
| Agent made a mistake                | AGENTS.md (new rule), README.md (Review Log)       |
| Code review completed               | REVIEW_CHECKLIST.md (if new check type discovered) |
| Session completed                   | TASKS.md (check off done items)                    |
| Schema changed                      | ARCHITECTURE.md (database section)                 |
| New endpoint added                  | ARCHITECTURE.md (API contracts section)            |
| Implementation diverged from design | ARCHITECTURE.md (update to match reality)          |

### Agent Responsibilities for Documentation

Agents are expected to:

- Read ARCHITECTURE.md, PATTERNS.md, and AGENTS.md before starting any task
- Follow all conventions documented in PATTERNS.md
- Suggest updates to ARCHITECTURE.md when implementation differs from the spec
- Flag when a task requires a schema or API contract not yet in ARCHITECTURE.md
- Update the AI Review Log when instructed to do so after a review session
- Never modify AGENTS.md directly — only the developer adds rules

### Generating Initial Documentation

When asked to generate documentation for an existing codebase, the agent must:

1. Read every file in the backend (models, routers, services, schemas, config, middleware, dependencies)
2. Read every file in the frontend (pages, components, hooks, lib, API client)
3. Read existing tests for patterns and conventions
4. Generate documentation based ONLY on what exists in the code — never invent features or endpoints
5. Mark anything ambiguous with `[?]` for the developer to clarify

---

## 7. Technical Constraints

These are non-negotiable requirements for all code in every project.

### Python / Backend

**Python version:** 3.11+. Use modern syntax (match/case, type unions with `|`, etc.).

**SQLAlchemy 2.0 style ONLY.** Never use SQLAlchemy 1.x patterns.

```python
# CORRECT — SQLAlchemy 2.0 mapped_column style
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase
from sqlalchemy import String, ForeignKey, BigInteger
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    rooms: Mapped[list["Room"]] = relationship(back_populates="creator")

# WRONG — SQLAlchemy 1.x Column style. NEVER use this.
# id = Column(Integer, primary_key=True)
# email = Column(String, unique=True)
```

**SQLAlchemy 2.0 query style ONLY:**

```python
# CORRECT — 2.0 select() style
from sqlalchemy import select

stmt = select(User).where(User.email == email)
result = await db.execute(stmt)
user = result.scalar_one_or_none()

# CORRECT — relationship loading to prevent N+1
from sqlalchemy.orm import selectinload

stmt = select(Room).options(selectinload(Room.members)).where(Room.created_by == user.id)

# WRONG — 1.x Query style. NEVER use this.
# db.query(User).filter(User.email == email).first()
```

**Async everything.** All database operations use async sessions. All FastAPI endpoints are `async def`. Use `asyncpg` as the PostgreSQL driver.

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine("postgresql+asyncpg://...", echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

**Pydantic v2 for all request/response models:**

```python
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    created_at: datetime
```

**Type hints on everything.** Every function signature has full type annotations. No untyped functions.

```python
async def create_room(db: AsyncSession, user: User, data: RoomCreate) -> Room:
    ...
```

**Environment configuration via pydantic-settings:**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    FRONTEND_URL: str = "http://localhost:3000"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = ConfigDict(env_file=".env")

settings = Settings()
```

**Error format is always consistent:**

```json
{ "detail": "Human-readable error message" }
```

Use `HTTPException` for all error responses. Never return raw strings or unstructured error objects.

**Logging over print.** Use Python's `logging` module. Never leave `print()` statements in committed code.

**Password hashing with bcrypt.** Never store plaintext passwords. Use `passlib[bcrypt]` or `bcrypt` directly.

**BIGINT for all primary keys.** Not INTEGER. This prevents ID exhaustion on growing tables.

### TypeScript / Frontend

**Strict TypeScript.** No `any` types. Use `unknown` and narrow with type guards when dealing with uncertain types.

```typescript
// CORRECT
interface Room {
  id: number;
  name: string;
  createdBy: number;
  createdAt: string;
}

// WRONG — never use any
const data: any = await response.json();
```

**Explicit props interfaces:**

```typescript
interface MessageBubbleProps {
  content: string;
  sender: string;
  timestamp: string;
  isOwn: boolean;
}

export function MessageBubble({
  content,
  sender,
  timestamp,
  isOwn,
}: MessageBubbleProps) {
  // ...
}
```

**Server components by default.** Only add `'use client'` when the component needs interactivity (hooks, event handlers, browser APIs). Data fetching happens in server components or route handlers, not in `useEffect` unless there's a specific reason.

**Centralized API client.** All API calls go through `lib/api.ts`. Components never use raw `fetch()`.

```typescript
// lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL;

export async function apiClient<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    credentials: "include", // send cookies for auth
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}
```

**Tailwind CSS for styling.** No inline style objects. No separate CSS files unless absolutely necessary (global resets, fonts).

### Database

**All schema changes go through Alembic migrations.** Never modify the database directly. Never edit a migration after it has been applied — create a new one.

**Every migration must be reversible.** The `downgrade()` function must work.

**Foreign keys always specify ON DELETE behavior:** CASCADE, SET NULL, or RESTRICT. Never leave it as the implicit default.

**Index any column used in WHERE clauses or JOINs** on tables expected to grow beyond a few hundred rows.

**Use TIMESTAMPTZ (timestamp with time zone)** for all datetime columns. Never use naive timestamps.

### Git

**Commit messages follow conventional format:**

```
type: short description

# Types: feat, fix, refactor, test, docs, chore, style
# Examples:
feat: add room creation endpoint with validation
fix: prevent N+1 query in unread message count
test: add error case tests for auth endpoints
refactor: extract message service from router
docs: update ARCHITECTURE.md with WebSocket schema
```

**One logical change per commit.** Do not bundle unrelated changes. A schema migration, its corresponding endpoint, and its tests can be one commit if they're all part of the same feature.

---

## 8. Security Requirements

Security is non-negotiable. Every feature must satisfy these requirements before it is considered complete.

### Input Validation

- All user input validated through Pydantic models (backend) or Zod schemas (frontend)
- String fields have explicit max_length constraints
- Email fields use EmailStr or equivalent validation
- File uploads validated for type (MIME type, not just extension), size, and content
- Never trust client-side validation alone — backend always validates independently

### Authentication

- JWT tokens with expiration (access token: 30 min, refresh token: 7 days)
- Passwords hashed with bcrypt (minimum 12 rounds)
- Auth tokens stored in httpOnly cookies (not localStorage — XSS vulnerability)
- Every endpoint is authenticated by default. Public endpoints must be explicitly marked and documented.

### Authorization

- Users can ONLY access their own data. Every database query that returns user-specific data MUST filter by the authenticated user's ID.
- Check ownership before UPDATE and DELETE operations: load the resource, verify `resource.user_id == current_user.id`, then proceed.
- Never rely on frontend to enforce access control — backend must verify independently.

### Output Security

- All user-generated content must be escaped before rendering (React handles this by default, but be careful with `dangerouslySetInnerHTML` — never use it with user content)
- API responses never include `password_hash` or other sensitive fields. Use separate Pydantic response models that exclude sensitive data.
- Error messages never expose internal details (stack traces, database errors, file paths)

### Infrastructure

- CORS restricted to specific frontend origin. Never `allow_origins=["*"]` in production.
- Rate limiting on authentication endpoints (login, register, password reset)
- Rate limiting on any public-facing endpoints
- HTTPS only in production (enforce via middleware or reverse proxy)
- No secrets in code, environment variables, or logs. Use `.env` files locally, environment variables in production.
- `.env.example` with placeholder values committed to repo. `.env` is gitignored.

### Database Security

- Parameterized queries only (SQLAlchemy handles this — but check any raw SQL)
- No SQL string interpolation, concatenation, or f-strings in queries EVER
- Database user has minimum required permissions (not superuser)
- Connection strings never logged or exposed in error messages

---

## 9. Agent Operating Rules

These rules govern agent behavior across all tasks. They supplement project-specific AGENTS.md rules.

### Before Starting Any Task

1. Read AGENTS.md for project-specific rules
2. Read docs/ARCHITECTURE.md for system design context
3. Read docs/PATTERNS.md for code conventions
4. Read TESTPLAN.md if the task involves implementing tests or features with test coverage
5. Check TASKS.md to understand the current task scope

### During Implementation

- **One task at a time.** Never implement multiple features or fix multiple unrelated issues in one session.
- **Do not install packages without stating what and why first.** Wait for approval.
- **Do not create .env files with real secrets.** Create .env.example with placeholder values.
- **Do not use `console.log` or `print()` for error handling.** Use proper logging and error boundaries.
- **Do not write tests that only test the happy path.** Include at least one error case and one edge case.
- **Do not use `*` imports.** Always import specific names.
- **Do not add dependencies that duplicate existing functionality.** Check what's already installed.
- **Do not create API routes without authentication unless explicitly told the route is public.**
- **Do not use string concatenation for URLs or file paths.** Use proper URL building and pathlib.
- **Do not modify migration files after they've been applied.** Create a new migration.
- **Do not catch broad exceptions and silently swallow them.** Log and re-raise or return proper error.
- **Do not use SQLAlchemy 1.x patterns.** Use 2.0 mapped_column and select() syntax only.
- **Do not use `any` type in TypeScript.** Use `unknown` and type guards.

### After Implementation

1. Run all verification commands (tests, lint, type check)
2. Fix any failures before reporting completion
3. Note any tests that passed unexpectedly (may indicate weak tests)
4. Suggest updates to ARCHITECTURE.md if implementation diverged from spec
5. Flag any security concerns discovered during implementation

### Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State your assumptions explicitly. If uncertain, ask.
- If multiple valid approaches exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### Planning vs Execution

**When a task is vague or spans multiple files:**

1. Plan first — outline files to create/modify, data flow, and API contracts as a checklist.
2. Get approval before writing code.
3. Execute step by step. Run verification after each step.

**When a task is clear and scoped (fix a bug, add a field, write one test):**
Execute directly. No plan needed. Verify and report.

### Goal-Driven Execution

Transform tasks into verifiable goals. Define success criteria before writing code.

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan with checks:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

### Self-Verification Checklist

Before reporting any task as complete:

- [ ] Tests pass (`pytest -v`)
- [ ] Lint passes (`ruff check .`)
- [ ] Type check passes (`mypy . --ignore-missing-imports`)
- [ ] Frontend builds (`npx tsc --noEmit && npx next lint`)
- [ ] No hardcoded secrets, URLs, or credentials
- [ ] New endpoints are documented in ARCHITECTURE.md or flagged for update
- [ ] New patterns are consistent with PATTERNS.md

---

## Quick Reference: The Complete Loop

```
┌─────────────────────────────────────────────────────────┐
│  1. DESIGN (Developer + Claude)                         │
│     Whiteboard architecture → Update ARCHITECTURE.md    │
│     Define test cases → Update TESTPLAN.md              │
│     Break into tasks → Update TASKS.md                  │
├─────────────────────────────────────────────────────────┤
│  2. TEST (Agent implements from TESTPLAN.md)             │
│     Write test code → Tests should FAIL (no feature yet)│
│     Verify tests are meaningful (specific assertions)    │
├─────────────────────────────────────────────────────────┤
│  3. IMPLEMENT (Agent implements from ARCHITECTURE.md)    │
│     Build feature → Tests should PASS                    │
│     Follow PATTERNS.md conventions                       │
│     Run verification suite (tests, lint, types)          │
├─────────────────────────────────────────────────────────┤
│  4. REVIEW (Developer + Claude)                         │
│     Check security (REVIEW_CHECKLIST.md)                │
│     Check performance (N+1, missing indexes)             │
│     Check code quality (types, error handling, names)    │
│     Update AI Review Log if issues found                 │
├─────────────────────────────────────────────────────────┤
│  5. DOCUMENT (Developer + Agent)                        │
│     Update ARCHITECTURE.md if design changed             │
│     Update PATTERNS.md if new convention established     │
│     Update AGENTS.md if agent made a mistake             │
│     Check off TASKS.md                                   │
│     Write LEARNINGS.md entry                             │
└─────────────────────────────────────────────────────────┘
```

This loop repeats for every feature. No exceptions.
