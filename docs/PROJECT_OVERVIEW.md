# Quaero — Complete Project Overview

> **Purpose:** Interview-ready reference covering architecture, design decisions, tradeoffs, deployment, security, testing, and known gaps.

---

## Table of Contents

1. [What Is Quaero](#1-what-is-quaero)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Tech Stack & Rationale](#3-tech-stack--rationale)
4. [Data Flow](#4-data-flow)
5. [Backend Architecture](#5-backend-architecture)
6. [Database Design](#6-database-design)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Security Model](#8-security-model)
9. [Background Processing](#9-background-processing)
10. [Deployment & Infrastructure](#10-deployment--infrastructure)
11. [Testing Strategy](#11-testing-strategy)
12. [Design Philosophies](#12-design-philosophies)
13. [Key Tradeoffs & Interview Q&A](#13-key-tradeoffs--interview-qa)
14. [Future Roadmap & Known Gaps](#14-future-roadmap--known-gaps)

---

## 1. What Is Quaero

Quaero is an AI-powered document intelligence platform that lets users upload PDF documents, processes them into vector embeddings, and provides natural language question-answering with cited sources using Retrieval Augmented Generation (RAG).

**The name** comes from Latin, meaning "I search / I seek."

**What it demonstrates:**
- Full-stack application design (FastAPI + Next.js + PostgreSQL)
- AI/ML integration (OpenAI embeddings + Anthropic RAG)
- Production deployment patterns (cross-domain auth, background processing, rate limiting)
- Security engineering (httpOnly cookies, CSRF protection, Argon2 hashing)
- Async systems design (durable job queue, polling, state machines)

**Live:** https://quaero.odysian.dev

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BROWSER                                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  REST API
                           │  httpOnly cookies + X-CSRF-Token header
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  NEXT.JS FRONTEND (Vercel)                                          │
│                                                                      │
│  Landing ──→ Login/Register ──→ Dashboard                            │
│                                    │                                 │
│                          ┌─────────┼─────────┐                       │
│                          │         │         │                       │
│                    Upload Zone  Doc List  Chat Window                 │
│                                    │                                 │
│                          Polls status via lightweight endpoint        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  FASTAPI BACKEND (Render)                                           │
│                                                                      │
│  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐          │
│  │ Routes │→ │ Services │→ │  Models  │→ │  PostgreSQL   │          │
│  │ (thin) │  │ (logic)  │  │ (ORM)    │  │  + pgvector   │          │
│  └────────┘  └──────────┘  └──────────┘  └───────────────┘          │
│       │            │                                                 │
│       │            ├──→ OpenAI API (embeddings)                      │
│       │            ├──→ Anthropic API (RAG answers)                  │
│       │            └──→ Redis Queue (Upstash)                        │
│       │                       │                                      │
│       │                       ▼                                      │
│       │              ┌─────────────────┐                             │
│       │              │  ARQ Worker     │                             │
│       │              │  (same service) │                             │
│       │              └─────────────────┘                             │
│       │                                                              │
│       └── CORS, Rate Limiting, CSRF Middleware                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| Next.js Frontend | UI, auth state, document management, chat interface, status polling |
| FastAPI Backend | API, auth, file handling, business logic, external API orchestration |
| ARQ Worker | Async document processing (PDF extraction, chunking, embedding) |
| PostgreSQL + pgvector | Relational data + vector similarity search |
| Redis (Upstash) | Durable job queue for background processing |
| OpenAI API | Generate 1536-dim embeddings for text chunks and queries |
| Anthropic API | Generate RAG answers from retrieved chunks + user questions |

---

## 3. Tech Stack & Rationale

| Layer | Choice | Why This | What Else Was Considered |
|-------|--------|----------|--------------------------|
| **Frontend** | Next.js 16 + React 19 + TypeScript | App Router, type safety, Vercel deployment | Vite + React (less deployment integration) |
| **Styling** | Tailwind CSS 4 | Utility-first, custom theme tokens, no CSS files | styled-components (runtime overhead) |
| **Backend** | FastAPI (Python 3.12) | Auto-docs, Pydantic validation, async-native, lightweight | Django REST (heavier), Express (less type safety) |
| **Background Jobs** | ARQ + Redis | Async-native, lightweight, durable across restarts | FastAPI BackgroundTasks (lost on restart), Celery (heavier) |
| **Queue/Broker** | Redis (Upstash) | Durable queue, free tier, managed service | RabbitMQ (self-hosted complexity) |
| **ORM** | SQLAlchemy 2.0 (async) | Type-safe, mapped_column, async sessions | Tortoise ORM (less mature), raw SQL (harder to maintain) |
| **Database** | PostgreSQL + pgvector | Relational + vector search in one DB, no extra service | Pinecone (separate service, more cost), Weaviate (overkill) |
| **Embeddings** | OpenAI text-embedding-3-small | 1536 dims, cost-effective, good quality | text-embedding-3-large (more cost), ada-002 (older) |
| **RAG Model** | Anthropic Claude 3 Haiku | Fast, accurate for Q&A, cost-effective | GPT-4 (slower, more expensive), Claude Sonnet (higher cost) |
| **Auth** | JWT (HS256) + Argon2 + httpOnly cookies | Stateless auth, XSS-safe token storage, modern hashing | Session-based (requires sticky sessions), bcrypt (less modern) |
| **PDF Processing** | pdfplumber | Best text quality for complex layouts | PyPDF2 (worse quality), PyMuPDF (license issues) |
| **Rate Limiting** | SlowAPI | Battle-tested, per-endpoint configuration | Custom middleware (reinventing the wheel) |
| **Deployment** | Vercel (FE) + Render (BE) | Free tier, auto-deploy from main, separate scaling | Single server (coupling), AWS (complexity) |

---

## 4. Data Flow

### Upload → Process → Query (Complete Pipeline)

```
UPLOAD PHASE (synchronous, fast)
────────────────────────────────
User selects PDF
  → Frontend sends multipart POST /api/documents/upload
  → Backend validates:
      • File extension (.pdf)
      • Magic bytes (%PDF- signature on first chunk)
      • Size limit (10MB, checked during streaming write)
  → Saves file to disk (uploads/YYYY-MM-DD_HEX_sanitized-name.pdf)
  → Creates Document record (status: PENDING)
  → Enqueues process_document_task in Redis (deterministic job ID: doc:{id})
  → Returns 201 immediately (non-blocking)


PROCESSING PHASE (asynchronous, ARQ worker)
────────────────────────────────────────────
Worker picks up job from Redis queue
  → Sets Document status: PROCESSING
  → Extracts text from PDF (pdfplumber, 30s timeout via ProcessPoolExecutor)
  → Chunks text:
      • 1000 characters per chunk
      • 50 character overlap
      • Word-boundary preservation (doesn't split mid-word)
  → Creates Chunk records, flushes to get IDs
  → Generates embeddings in batch (OpenAI API, 1536 dimensions)
  → Assigns embedding vectors to Chunk records
  → Sets Document status: COMPLETED, processed_at: now()
  → On any failure: status: FAILED, error_message: str(exception)


POLLING PHASE (frontend, during processing)
────────────────────────────────────────────
Frontend detects documents with status pending/processing
  → Polls GET /api/documents/{id}/status (lightweight endpoint)
  → Initial interval: 3 seconds
  → Adaptive backoff:
      • All succeed: stays at 3s
      • Some fail: delay × 1.5
      • All fail: delay × 2
      • Cap: 10 seconds
  → Uses Promise.allSettled (one failure doesn't block others)
  → Stops when all documents reach terminal state (completed/failed)


QUERY PHASE (synchronous, RAG pipeline)
────────────────────────────────────────
User types question in chat
  → Frontend sends POST /api/documents/{id}/query
  → Backend generates query embedding (OpenAI, single call)
  → pgvector cosine similarity search against document's chunks (top 5)
  → Constructs prompt with numbered excerpts + question
  → Sends to Claude 3 Haiku (max 1024 tokens)
  → Saves user message + assistant response to messages table (single transaction)
  → Returns answer + source citations (chunk content, similarity scores)
```

### Authentication Flow

```
REGISTRATION
  → POST /api/auth/register (username, email, password)
  → Backend: hash password (Argon2), create user
  → Frontend: auto-login after successful registration

LOGIN
  → POST /api/auth/login (username, password)
  → Backend: verify password, generate JWT + refresh token
  → Response includes:
      • JSON body: { access_token, refresh_token, csrf_token }
      • Set-Cookie: access_token (httpOnly, Path=/api/)
      • Set-Cookie: refresh_token (httpOnly, Path=/api/auth/)
      • Set-Cookie: csrf_token (NOT httpOnly, Path=/)
  → Frontend: stores csrf_token in localStorage (needed for cross-domain CSRF)

AUTHENTICATED REQUEST
  → Frontend: includes credentials: "include" (sends cookies)
  → Frontend: reads csrf_token from localStorage, sends as X-CSRF-Token header
  → Backend: reads access_token from cookie (or Bearer header fallback)
  → Backend: validates JWT, extracts user_id
  → Backend: timing-safe compares X-CSRF-Token header vs csrf_token cookie

TOKEN REFRESH (silent, automatic)
  → On 401 response: frontend calls POST /api/auth/refresh
      • No body needed (refresh_token is in httpOnly cookie)
      • Single-flight pattern: concurrent 401s share one refresh attempt
  → Backend: validates refresh token, rotates atomically
      • Delete old token + create new token in single transaction
  → New tokens set in cookies + JSON body
  → Original request retried with new CSRF token
  → If refresh fails: clear localStorage, redirect to /login
```

---

## 5. Backend Architecture

### Layer Separation

```
Routes (thin)          → Input validation, call service, return response
  │
  ▼
Services (fat)         → All business logic, DB operations, external API calls
  │
  ▼
Models (data)          → SQLAlchemy 2.0 ORM, schema definitions
  │
  ▼
Database               → PostgreSQL + pgvector (async via asyncpg)
```

**Why this matters:** Routes never contain business logic. This means:
- Services are testable independently of HTTP concerns
- Business rules are in one place, not scattered across endpoints
- Services can be reused (e.g., `process_document_text` is called by both the worker task and could be called inline)

### File Structure

```
backend/app/
├── main.py              # App factory, CORS, lifespan (startup/shutdown), middleware
├── config.py            # Pydantic Settings (env vars, defaults, computed properties)
├── constants.py         # Magic numbers (MAX_FILE_SIZE, CHUNK_SIZE, EMBEDDING_DIMS, etc.)
├── database.py          # Dual engines (async for app, sync for Alembic), session factory
│
├── models/              # SQLAlchemy 2.0 models (Mapped + mapped_column)
│   ├── base.py          # Document, Chunk, DocumentStatus enum
│   ├── user.py          # User model
│   ├── message.py       # Message model (user/assistant roles, JSONB sources)
│   └── refresh_token.py # RefreshToken model (opaque hex token)
│
├── schemas/             # Pydantic v2 request/response models
│   ├── user.py          # UserCreate, UserLogin, UserResponse, Token
│   ├── document.py      # DocumentResponse, UploadResponse, DocumentStatusResponse
│   ├── search.py        # SearchRequest, SearchResult, SearchResponse
│   ├── query.py         # QueryRequest, QueryResponse
│   └── message.py       # MessageResponse, MessageListResponse
│
├── api/                 # FastAPI routers (thin handlers)
│   ├── auth.py          # /api/auth/* (register, login, refresh, logout, me)
│   ├── documents.py     # /api/documents/* (upload, list, delete, process, search, query)
│   └── dependencies.py  # get_db, get_current_user, verify_csrf
│
├── services/            # Business logic
│   ├── document_service.py   # PDF processing pipeline (extract → chunk → embed → store)
│   ├── search_service.py     # Vector similarity search (pgvector cosine distance)
│   ├── embedding_service.py  # OpenAI embedding generation (single + batch)
│   ├── anthropic_service.py  # Claude RAG answer generation
│   └── queue_service.py      # ARQ job enqueueing (lazy Redis pool, deterministic IDs)
│
├── core/
│   └── security.py      # JWT create/decode, Argon2 hash/verify, refresh token helpers
│
├── crud/
│   └── user.py          # User CRUD operations
│
├── utils/
│   ├── file_utils.py    # PDF validation (magic bytes), upload saving (streaming)
│   ├── pdf_utils.py     # Text extraction (pdfplumber), chunking (word-boundary)
│   ├── rate_limit.py    # SlowAPI setup, IP/user key functions
│   ├── cookies.py       # Set/clear httpOnly auth cookies + CSRF cookie
│   ├── timeout.py       # ProcessPoolExecutor timeout wrapper (CPU-bound safety)
│   └── logging_config.py # Structured logging setup
│
└── workers/
    ├── arq_worker.py     # ARQ WorkerSettings, startup reconciliation
    └── document_tasks.py # process_document_task (thin wrapper around service)
```

### Key Backend Patterns

**1. Async everywhere.** All endpoints are `async def`. All DB operations use `AsyncSession`. External API calls are async. CPU-bound work (PDF extraction) runs in `ProcessPoolExecutor` with timeout protection.

**2. SQLAlchemy 2.0 exclusively.** `Mapped` type hints, `mapped_column`, `select()` statements. Never 1.x `Column()` or `db.query()` patterns.

```python
# How queries look in Quaero
stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
document = await db.scalar(stmt)
```

**3. Helper staging pattern.** Security helpers like `create_refresh_token` stage work (add to session) but don't commit. The calling route owns the transaction boundary. This enables atomic operations (e.g., delete old token + create new token + commit in one go).

**4. Streaming file validation.** Uploads are read chunk-by-chunk. Magic bytes are checked on the first chunk. File size is accumulated during write, not after. This prevents both disk exhaustion and deceptive file uploads.

**5. Deterministic job IDs.** ARQ jobs use `doc:{document_id}` as the job ID. If the same document is enqueued twice (e.g., upload + retry), the second enqueue is a no-op. Prevents duplicate processing.

---

## 6. Database Design

### Schema Isolation

All tables live in the `quaero` schema (not `public`). This allows sharing a single PostgreSQL instance across multiple portfolio projects on Render's free tier.

Every model declares: `__table_args__ = {"schema": "quaero"}`

**Gotcha (ADR-002):** Alembic autogenerate produces phantom diffs when the schema is `quaero` because of how schema reflection interacts with `search_path`. Fixed by creating a dedicated Alembic engine with `search_path=public` and using `include_name` instead of `include_object` for schema filtering.

### Entity-Relationship Diagram

```
┌──────────────┐     1:N     ┌──────────────┐     1:N     ┌──────────────┐
│    users     │────────────→│  documents   │────────────→│    chunks    │
│              │             │              │             │              │
│ id (PK)      │             │ id (PK)      │             │ id (PK)      │
│ username     │             │ filename     │             │ document_id  │
│ email        │             │ file_path    │             │ content      │
│ hashed_pw    │             │ file_size    │             │ chunk_index  │
│ created_at   │             │ status       │             │ embedding    │
└──────┬───────┘             │ user_id (FK) │             │   VECTOR(1536)
       │                     │ uploaded_at  │             │ created_at   │
       │                     │ processed_at │             └──────────────┘
       │                     │ error_message│
       │                     └──────┬───────┘
       │                            │
       │         1:N                │  1:N
       │    ┌───────────────────────┘
       │    │
       ▼    ▼
┌──────────────┐
│   messages   │
│              │
│ id (PK)      │
│ document_id  │  ← CASCADE delete
│ user_id      │  ← CASCADE delete
│ role         │  ← CHECK ('user', 'assistant')
│ content      │
│ sources      │  ← JSONB (search results for assistant msgs)
│ created_at   │
└──────────────┘

┌──────────────────┐
│ refresh_tokens   │
│                  │
│ id (PK)          │
│ user_id (FK)     │  ← CASCADE delete
│ token            │  ← UNIQUE (opaque hex, not JWT)
│ expires_at       │
│ created_at       │
└──────────────────┘
```

### Table Details

| Table | PK Type | Key Columns | Notable Constraints |
|-------|---------|-------------|---------------------|
| users | INTEGER | username (UNIQUE), email (UNIQUE) | Argon2 hashed password |
| documents | INTEGER | status (ENUM: PENDING/PROCESSING/COMPLETED/FAILED), user_id (FK) | Indexed on status + user_id |
| chunks | INTEGER | embedding VECTOR(1536), document_id (FK) | Nullable embedding (populated async) |
| messages | INTEGER | role (CHECK: user/assistant), sources (JSONB) | CASCADE on document + user delete |
| refresh_tokens | INTEGER | token (UNIQUE, 64-char hex) | Expiry-based cleanup, CASCADE on user delete |

### Index Strategy

| Table | Column(s) | Type | Purpose |
|-------|-----------|------|---------|
| users | username | UNIQUE | Login lookup |
| users | email | UNIQUE | Registration uniqueness check |
| documents | status | BTREE | Filter by processing state |
| documents | user_id | BTREE | User's document list |
| chunks | document_id | BTREE | Chunk retrieval for a document |
| refresh_tokens | token | UNIQUE | Token lookup on every refresh |
| refresh_tokens | user_id | BTREE | Bulk cleanup / revoke all sessions |
| chunks | embedding | ivfflat (pgvector) | Vector similarity search |

### Document Status State Machine

```
                ┌──────────┐
   Upload ────→ │ PENDING  │ ←── Startup reconciliation (stale PROCESSING reset)
                └────┬─────┘
                     │ Worker picks up job
                     ▼
                ┌──────────────┐
                │ PROCESSING   │
                └──┬───────┬───┘
       Success     │       │  Failure
                   ▼       ▼
            ┌──────────┐ ┌────────┐
            │COMPLETED │ │ FAILED │
            └──────────┘ └───┬────┘
                             │ User clicks "Retry"
                             │ POST /process → re-enqueue
                             ▼
                        ┌──────────┐
                        │ PENDING  │ (re-enters queue)
                        └──────────┘
```

### Why pgvector Over a Dedicated Vector DB

| Factor | pgvector | Pinecone/Weaviate |
|--------|----------|-------------------|
| Operational complexity | Zero — same DB as relational data | Separate service to manage |
| Cost | Free (PostgreSQL extension) | Paid tiers for production |
| Joins with relational data | Native SQL joins | Requires cross-service queries |
| Scale ceiling | ~1M vectors per table | Billions+ |
| Consistency | ACID with relational data | Eventually consistent |

**Tradeoff:** pgvector is ideal at this scale (thousands of chunks per user). If the system needed to handle millions of documents with sub-millisecond search, a dedicated vector DB would be warranted. The migration path would be: keep relational data in Postgres, move embeddings to Pinecone, query Pinecone for chunk IDs then join back.

---

## 7. Frontend Architecture

### Technology Choices

- **Next.js 16 + React 19** — App Router, but all pages are `"use client"` (no server components)
- **TypeScript strict mode** — No `any` types, full type coverage
- **Tailwind CSS 4** — Custom lapis color palette, semantic CSS classes
- **No state management library** — React hooks (useState, useEffect, useRef) are sufficient

### Why Client Components Only?

The backend is on a different domain (Render) than the frontend (Vercel). Server components would need to make authenticated requests to the backend, which means managing cookies server-side in Next.js. Since all data fetching is authenticated and goes through the centralized API client with httpOnly cookies, client components with `credentials: "include"` are simpler and avoid the complexity of server-side cookie forwarding.

### Page Structure

```
app/
├── layout.tsx           # Root layout: Google Fonts (Geist Sans, Geist Mono, Cormorant)
├── page.tsx             # Landing: auto-redirect if logged in, CTA buttons
├── login/page.tsx       # Login form: username + password, error display
├── register/page.tsx    # Registration: username + email + password, auto-login after
├── dashboard/page.tsx   # Main app: document list + chat + polling orchestration
└── components/dashboard/
    ├── UploadZone.tsx         # Drag-drop PDF upload, file validation
    ├── DocumentList.tsx       # Sidebar list with status icons, process/delete buttons
    ├── ChatWindow.tsx         # RAG chat: messages, sources, suggested prompts
    └── DeleteDocumentModal.tsx # Confirmation dialog
```

### API Client Design (lib/api.ts)

The centralized API client handles:

1. **CSRF token management** — Reads from localStorage, sends as `X-CSRF-Token` header
2. **Credential forwarding** — All requests use `credentials: "include"` for httpOnly cookies
3. **Silent token refresh** — On 401, attempts refresh once, retries original request
4. **Single-flight deduplication** — Concurrent 401s share one refresh promise
5. **Error normalization** — All API errors become `ApiError` instances with status + detail

```
Request Flow:
  apiRequest(path, options)
    → Add X-CSRF-Token header (from localStorage)
    → Add credentials: "include"
    → Detect FormData (skip Content-Type for multipart)
    → Execute fetch
    → On 401: attempt silent refresh (single-flight)
      → On refresh success: retry with new CSRF token
      → On refresh failure: clear tokens, redirect to /login
    → On other error: throw ApiError with status + detail
    → On success: return parsed JSON
```

### Smart Polling System

The dashboard implements adaptive polling for document processing status:

```
Has active documents (pending/processing)?
  │
  YES → Start polling loop
  │      → GET /api/documents/{id}/status for each active doc
  │      → Uses Promise.allSettled (partial failures don't block)
  │      → Update document state immutably
  │      │
  │      ├─ All succeed → delay stays at 3s
  │      ├─ Some fail   → delay × 1.5
  │      ├─ All fail    → delay × 2
  │      └─ Cap at 10s
  │
  │      → Detect 404 (deleted doc) → filter out
  │      → Detect 401 (expired) → redirect to /login
  │      → Check if any docs still active → continue or stop
  │
  NO → Don't poll
```

**Why not WebSockets?** Polling is simpler, the status endpoint is lightweight (just returns `{id, status, error_message}`), and the update frequency (every 3-10 seconds) doesn't warrant persistent connections. WebSockets would add complexity (connection management, reconnection logic, server-side pub/sub) for minimal benefit.

### UI/UX Design

**Dark theme** with zinc backgrounds and a custom lapis (blue) accent palette.

**Typography:** Three font families:
- Cormorant Garamond (serif) — headings, branding
- Geist Sans — body text
- Geist Mono — technical content

**Responsive layout:**
- Desktop: fixed sidebar (w-72) + main content area
- Mobile: drawer sidebar with overlay, responsive padding

**Empty states:** Every state has a designed empty experience:
- Loading: animated Quaero logo pulse
- No documents: upload prompt with zone
- No selection: "Select a document" with mobile-aware button
- Empty chat: suggested prompts ("Summarize this document", etc.)

**Chat interface:**
- User messages: right-aligned, lapis blue
- Assistant messages: left-aligned, zinc with border
- Sources: collapsible per-message, shows similarity %, chunk preview, expandable full text
- Loading: animated bouncing dots

---

## 8. Security Model

### Authentication Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      TOKEN STORAGE                               │
│                                                                  │
│  access_token   → httpOnly cookie (Path=/api/)                   │
│  refresh_token  → httpOnly cookie (Path=/api/auth/)              │
│  csrf_token     → readable cookie + localStorage                 │
│                                                                  │
│  JavaScript CANNOT read access_token or refresh_token            │
│  JavaScript CAN read csrf_token (needed for CSRF header)         │
└─────────────────────────────────────────────────────────────────┘
```

**Why httpOnly cookies instead of localStorage?**
localStorage is readable by any JavaScript on the page. An XSS vulnerability (injected script, compromised dependency) could steal tokens from localStorage. httpOnly cookies are invisible to JavaScript — they're automatically sent by the browser but can never be read or exfiltrated by scripts.

**Why not just use cookies for everything?**
The frontend and backend are on different domains (Vercel vs Render). Due to the Same-Origin Policy, JavaScript on `quaero.odysian.dev` cannot read cookies set by `quaero-api.onrender.com` via `document.cookie`. The CSRF token must be readable by JS to be sent as a header, so it's returned in the JSON body and stored in localStorage.

### CSRF Protection (Double-Submit Pattern)

```
1. Login → Backend sets csrf_token cookie (readable) + returns in JSON body
2. Frontend stores csrf_token in localStorage
3. On mutating request:
   → Browser sends csrf_token cookie automatically
   → Frontend reads localStorage, sends as X-CSRF-Token header
   → Backend does timing-safe comparison of cookie vs header
4. Attacker from evil.com:
   → Can trigger browser to send cookie (via form/fetch)
   → Cannot read the cookie value (Same-Origin Policy)
   → Cannot set X-CSRF-Token header with correct value
   → Request rejected with 403
```

**Exemptions:** Login and register endpoints skip CSRF checks because they require valid credentials (username + password), which CSRF attacks don't have.

### Password Security

- **Algorithm:** Argon2id (memory-hard, winner of the Password Hashing Competition)
- **Library:** argon2-cffi via passlib CryptContext
- **Why not bcrypt?** Argon2 is the modern standard. It's memory-hard (resistant to GPU/ASIC attacks), while bcrypt is only compute-hard.

### Refresh Token Design

| Property | Value | Why |
|----------|-------|-----|
| Format | `secrets.token_hex(32)` (64-char hex) | No embedded claims needed; opaque lookup |
| Storage | Database row (not JWT) | Server-side revocation; delete row = revoke |
| Rotation | Delete old + create new atomically | Detects token theft (reuse = compromised) |
| Expiry | 7 days | Balance between convenience and risk |
| Cleanup | Expired rows deleted on validate + startup | Prevents table bloat |

**Atomic rotation (ADR-003):** The old token is deleted and the new token is created in the same database transaction. If the process crashes mid-rotation, the transaction rolls back and the old token remains valid. The user is never left without a valid session.

### Rate Limiting

| Endpoint | Limit | Rationale |
|----------|-------|-----------|
| Register | 3/hour per IP | Prevent account spam |
| Login | 5/minute per IP | Brute force defense |
| Refresh | 10/minute per IP | Prevent refresh storms |
| Upload | 5/hour per user | OpenAI embedding cost control |
| Query | 10/hour per user | Anthropic API cost control |
| Search | 15/hour per user | OpenAI embedding cost (query only) |
| Status | 120/minute per user | Allow frequent polling |
| List/Get | 20-30/hour per user | Standard API protection |

Key function selection: public endpoints use IP-based limiting (`get_ip_key`), authenticated endpoints use user ID or IP fallback (`get_user_or_ip_key`).

### Input Validation

- **Pydantic schemas** validate all request bodies (max_length, min_length, type constraints)
- **File uploads** validated three ways: extension check, magic bytes check (`%PDF-`), size check during streaming write
- **SQL injection** prevented by SQLAlchemy parameterized queries (never string interpolation)
- **Ownership checks** on every user-specific query: `WHERE user_id = current_user.id`

### CORS Configuration

```python
allow_origins=[settings.frontend_url]  # Specific origin, never "*"
allow_credentials=True                  # Required for httpOnly cookies
allow_methods=["*"]
allow_headers=["*"]
```

**ADR-003 established:** Wildcard CORS (`["*"]`) is incompatible with `allow_credentials=True` and was a security prerequisite to fix before migrating to httpOnly cookies.

---

## 9. Background Processing

### Why Not Inline Processing?

The document processing pipeline (PDF extraction → chunking → embedding) takes 10-60 seconds depending on document size. Running this inline in a request handler:
- Blocks the request (poor UX)
- Risks timeout on Render free tier (30-second limit)
- Ties up a worker thread, reducing concurrency

### Architecture (ADR-004)

```
Upload Request                    Redis Queue              ARQ Worker
─────────────                    ───────────              ──────────
POST /upload                     quaero:queue
  → Save file                      │
  → Create PENDING doc              │
  → enqueue(doc_id)  ──────────→  [doc:42]
  → Return 201                      │
                                    │
                              Worker polls (10s)
                                    │
                              Picks up job
                                    │
                              process_document_task(42)
                                    │
                              PENDING → PROCESSING
                                    │
                              Extract → Chunk → Embed
                                    │
                              PROCESSING → COMPLETED (or FAILED)
```

### Worker Configuration

| Setting | Value | Why |
|---------|-------|-----|
| `max_jobs` | 1 | Serialize processing (prevent memory spikes from parallel PDF extraction) |
| `job_timeout` | 900s (15 min) | Large PDFs with many pages need time |
| `poll_delay` | 10s | Balance between responsiveness and Redis load |
| `keep_result` | 0 | Don't store results (status is in the document record) |

### Startup Reconciliation

On worker startup, any document stuck in PROCESSING status for more than 15 minutes is reset to PENDING with an error message. This handles:
- Render free-tier sleep (process killed mid-job)
- Worker crashes
- Deployment restarts

The document re-enters the queue and will be processed again.

### Deployment: Combined Process

On Render, both the FastAPI API and the ARQ worker run as a single service using a startup script:

```bash
# Start both processes, exit if either dies
uvicorn app.main:app & API_PID=$!
arq app.workers.arq_worker.WorkerSettings & WORKER_PID=$!
wait -n $API_PID $WORKER_PID  # Exit when first process dies
```

**Why combined?** Render free tier only allows one service. Running them together keeps costs at zero. The tradeoff is they can't scale independently.

---

## 10. Deployment & Infrastructure

### Production Architecture

| Component | Platform | Tier | Domain |
|-----------|----------|------|--------|
| Frontend | Vercel | Free | quaero.odysian.dev |
| Backend + Worker | Render | Free | quaero-api.onrender.com |
| Database | Render | Free | Shared PostgreSQL |
| Redis | Upstash | Free | Managed Redis |
| DNS | Cloudflare | Free | Custom domain routing |

### Local Development

Docker Compose provides PostgreSQL + pgvector and Redis:

```yaml
services:
  db:
    image: pgvector/pgvector:pg15
    port: 5434
    # Tuned for stability:
    # max_parallel_maintenance_workers=2 (prevents CPU spike during index builds)
    # maintenance_work_mem=1GB
    # Resource limits: 6.4 CPUs, 8GB RAM
    # Restart policy: on-failure:5

  redis:
    image: redis:7-alpine
    port: 6379
```

### Known Deployment Challenges

**1. Cold Starts (Render Free Tier)**
Render spins down the backend after 15 minutes of inactivity. First request takes 30-60 seconds. The frontend shows loading states during this time.

**Mitigation:** The status polling endpoint is lightweight, and the worker has startup reconciliation to handle documents that were being processed when the service went to sleep.

**2. File Storage (Ephemeral)**
Uploaded PDFs are stored on Render's filesystem, which is ephemeral. On redeploy or restart, uploaded files are lost. The database records remain, but the files are gone.

**Future fix:** Move to cloud storage (S3/Cloudflare R2). The `file_path` column already stores relative paths, making migration straightforward.

**3. Shared Database**
The PostgreSQL instance is shared with other portfolio projects. Schema isolation (`quaero` schema) prevents table name collisions.

**Gotcha:** Connection pool is tuned conservatively (`pool_size=3, max_overflow=5`) to share resources.

---

## 11. Testing Strategy

### Test Infrastructure

- **Database:** Real PostgreSQL with `quaero_test` schema (not SQLite, not mocks)
- **Isolation:** Each test runs inside a SAVEPOINT transaction that rolls back after completion
- **External APIs:** OpenAI and Anthropic are mocked at the service function level
- **Auth:** Tests use Bearer token headers (simpler than cookie-based in test client)
- **Rate limiting:** Disabled in tests to avoid flaky failures

### Test Organization

| File | Coverage Area | Example Tests |
|------|--------------|---------------|
| `test_auth.py` | Registration, login, token refresh, CSRF | Register with duplicate username returns 400; Login with wrong password returns 401 |
| `test_documents.py` | Upload, list, delete, process, status | Upload non-PDF returns 400; Delete another user's doc returns 404 |
| `test_query.py` | Search, RAG query, message persistence | Query returns sources with similarity scores; Messages persist after query |
| `test_document_tasks.py` | Background job execution | Worker task calls service correctly; Status transitions properly |

### Test Fixtures (conftest.py)

```python
# Key fixtures and their scope:
client          # Function-scoped: AsyncClient with test DB, rate limiting off
test_user       # Function-scoped: unique user (UUID-based email)
auth_headers    # Function-scoped: Bearer token for test_user
second_user     # Function-scoped: second user for ownership tests
test_document   # Function-scoped: PENDING document owned by test_user
processed_document  # Function-scoped: COMPLETED document with 3 fake chunks
mock_embeddings     # Autouse: patches OpenAI embedding calls
mock_anthropic      # Autouse: patches Anthropic API calls
```

### What's Tested

- **Happy paths:** Registration, login, upload, processing, query, search, delete
- **Error cases:** Invalid credentials, duplicate registration, non-PDF upload, unauthorized access
- **Security:** Ownership checks (user A can't access user B's documents), CSRF validation
- **State transitions:** PENDING → PROCESSING → COMPLETED/FAILED
- **Edge cases:** Empty query results, large files, concurrent operations

### What's NOT Tested (Known Gaps)

- No frontend tests (no Jest/Vitest/Playwright setup)
- No integration tests for the full polling flow
- No load/stress testing
- No tests for WebSocket-less real-time behavior
- Cookie-based auth path not tested (tests use Bearer tokens)

### Verification Commands

```bash
# Backend
cd backend
ruff check .                          # Lint
mypy . --ignore-missing-imports       # Type check
pytest -v                             # Tests
bandit -r app/ -ll                    # Security scan

# Frontend
cd frontend
npx tsc --noEmit                      # Type check
npx next lint                         # Lint
npm run build                         # Build
```

---

## 12. Design Philosophies

### 1. Simplicity First

Every choice defaults to the simplest option that solves the problem:
- pgvector over Pinecone (same database, no extra service)
- ARQ over Celery (lighter, async-native)
- React hooks over Redux (sufficient for this state complexity)
- SlowAPI over custom middleware (battle-tested, less code)

### 2. Security by Default

Auth tokens in httpOnly cookies (not localStorage). Ownership checks on every query. CSRF protection on mutating endpoints. Rate limiting on every endpoint. Input validation through Pydantic. File content validation (not just extension). Timing-safe comparisons.

### 3. Async Throughout

The entire backend is async: endpoints, database operations, external API calls. CPU-bound work (PDF extraction) runs in a process pool with timeout protection. Background jobs run in an async worker. The frontend polls asynchronously with adaptive backoff.

### 4. Separation of Concerns

Routes are thin (validate → delegate → respond). Services contain all business logic. Models define data. Schemas define contracts. Workers are thin wrappers around service functions. The API client centralizes all frontend HTTP concerns.

### 5. Fail Fast, Recover Gracefully

Documents transition to FAILED with an error message on any processing failure. The startup reconciliation resets stale PROCESSING documents. The frontend handles 401s with automatic token refresh. Rate limit errors are communicated to the user.

### 6. Design for the Current Scale

No premature optimization. Single database for relational + vector data. Single process for API + worker. Simple polling instead of WebSockets. These choices are correct at portfolio-project scale and have clear migration paths when scale demands it.

---

## 13. Key Tradeoffs & Interview Q&A

### Q: Why pgvector instead of a dedicated vector database?

**Answer:** At this scale (hundreds to thousands of chunks per user), pgvector provides vector similarity search with zero additional infrastructure. The chunks live alongside their relational metadata (document ownership, status, content) in the same database, enabling simple JOINs. A dedicated vector DB (Pinecone, Weaviate) would add a second data store, cross-service consistency concerns, and cost — all for capabilities this project doesn't need yet.

**When to switch:** If search latency or throughput became a bottleneck at millions of chunks, or if approximate nearest neighbor algorithms beyond pgvector's ivfflat were needed.

### Q: Why httpOnly cookies instead of localStorage for auth tokens?

**Answer:** localStorage is accessible to any JavaScript on the page. A single XSS vulnerability — a compromised npm dependency, an injected script, a DOM-based XSS — could exfiltrate tokens from localStorage. httpOnly cookies are never accessible to JavaScript; they're sent automatically by the browser. This moves the attack surface from "any script on the page" to "CSRF attacks," which are mitigated by the double-submit pattern.

**Tradeoff:** Cross-domain cookie handling is more complex. The CSRF token must be delivered via JSON body (ADR-001) because the frontend can't read cookies from the backend's domain. This adds implementation complexity but provides stronger security.

### Q: Why a queue (ARQ + Redis) instead of FastAPI BackgroundTasks?

**Answer:** `BackgroundTasks` runs in the same process. If the process restarts (Render free-tier sleep, deployment), the task is lost. With ARQ + Redis, the job is durably queued. If the worker crashes, the job remains in Redis and is picked up when the worker restarts. Additionally, `BackgroundTasks` doesn't provide job deduplication, timeout handling, or status tracking.

**Tradeoff:** Redis is an additional service (Upstash), and the worker adds operational complexity. For a system where losing a background task is acceptable, `BackgroundTasks` would be simpler.

### Q: Why polling instead of WebSockets for document status?

**Answer:** The status updates are infrequent (every 3-10 seconds) and unidirectional (server → client). WebSockets would require connection management, reconnection logic, heartbeats, and server-side pub/sub — all for a feature that works fine with a lightweight GET endpoint. The polling endpoint returns only `{id, status, error_message}` (minimal payload).

**When to switch:** If the app added real-time features (collaborative editing, live chat between users), WebSockets would be justified. For status polling alone, they're over-engineering.

### Q: Why all client components (no server components)?

**Answer:** Every page needs authenticated data fetching, which requires httpOnly cookies. Server components in Next.js would need to forward cookies from the incoming request to the backend API, adding complexity for cookie management, CSRF handling, and error flows. Since the app is fully interactive (forms, chat, drag-drop, polling), `"use client"` everywhere is simpler and the SSR/streaming benefits of server components aren't significant for this use case.

**Tradeoff:** No server-side rendering means worse SEO and slower initial paint. For an authenticated dashboard app (not a content site), this tradeoff is acceptable.

### Q: Why Argon2 instead of bcrypt?

**Answer:** Argon2 won the Password Hashing Competition in 2015. It's memory-hard (resistant to GPU/ASIC attacks), while bcrypt is only compute-hard. Argon2id (the variant used) combines resistance to both side-channel and GPU attacks. It's the modern recommendation from OWASP.

### Q: Why INTEGER primary keys instead of BIGINT or UUID?

**Answer:** This is a portfolio project with bounded scale. INTEGER (4 bytes, max 2.1 billion) is sufficient and more storage-efficient than BIGINT (8 bytes) or UUID (16 bytes). For a production system expecting high insert rates, BIGINT would be safer.

### Q: Why 1000-character chunks with 50-character overlap?

**Answer:** Started with 500 characters but found it lost context for complex passages. 1000 characters preserves enough context for the RAG model to generate coherent answers. The 50-character overlap ensures that sentences split at chunk boundaries are still captured in at least one chunk. Word-boundary preservation prevents mid-word splits.

**Tradeoff:** Larger chunks mean fewer chunks per document (faster search) but potentially less precise retrieval. Smaller chunks give better precision but may lack context. 1000/50 is a common balance point.

### Q: How does the system handle document deletion?

**Answer:** DELETE cascade: deleting a document cascades to delete all chunks and messages. The file is removed from disk. The database operation is atomic. If the document was being processed, the worker will encounter a missing document and the job will fail gracefully.

### Q: What happens if the OpenAI or Anthropic API is down?

**Answer:** The document processing catches all exceptions and sets the document status to FAILED with the error message. The user can retry later via the "Process" button. For queries, the error is returned to the frontend as an API error and displayed in the chat. The Anthropic service specifically handles 529 (overloaded) status codes gracefully.

### Q: How do you prevent duplicate processing?

**Answer:** Deterministic ARQ job IDs. Every enqueue call uses `doc:{document_id}` as the job ID. ARQ deduplicates — if a job with that ID already exists in the queue, the enqueue is a no-op.

---

## 14. Future Roadmap & Known Gaps

### Current Limitations

| Limitation | Impact | Difficulty to Fix |
|-----------|--------|-------------------|
| **Ephemeral file storage** | Files lost on Render restart/deploy | Medium (add S3/R2 integration) |
| **No server-side pagination** | Document list returns all docs | Low (add cursor-based pagination) |
| **Single-document queries** | Can't query across multiple docs | High (cross-document embedding search) |
| **No frontend tests** | UI regressions not caught | Medium (add Playwright E2E) |
| **Cold starts (30-60s)** | Poor first-load experience | Low (paid tier or keep-alive cron) |
| **No token expiration** | Access tokens never expire | Low (set `access_token_expire_minutes > 0`) |
| **Cookie auth not tested** | Cookie path untested in CI | Low (add cookie-based test fixtures) |
| **No file type support beyond PDF** | Limited to PDFs only | Medium (add DOCX/TXT extractors) |

### Unresolved Design Questions (from TESTPLAN.md)

- How should scanned PDFs (images, no extractable text) be handled?
- Should documents be deletable while in PROCESSING state?
- What's the timeout behavior for very large PDFs (100+ pages)?
- Should usernames be trimmed of whitespace on registration?

### Natural Evolution Path

**Phase 1: Reliability**
- Move file storage to S3/Cloudflare R2
- Add frontend E2E tests (Playwright)
- Enable token expiration with proper refresh flow
- Add server-side pagination for documents

**Phase 2: Features**
- Multi-document queries (search across all user documents)
- Support more file types (DOCX, TXT, markdown)
- Conversation memory (multi-turn context in RAG prompts)
- Document metadata extraction (title, author, date)

**Phase 3: Scale**
- Separate API and worker into independent services
- Add WebSocket for real-time status (if justified by usage)
- Evaluate dedicated vector DB (if chunk count exceeds millions)
- Add caching layer (Redis for frequent queries)

---

## Architecture Decision Records (ADRs)

| ADR | Title | Status | Key Decision |
|-----|-------|--------|--------------|
| 001 | Cross-Domain CSRF — Split Token Delivery | Accepted | Return CSRF token in JSON body; store in localStorage |
| 002 | Alembic Autogenerate Phantom Diffs | Applied | Dedicated engine with `search_path=public` for Alembic |
| 003 | Refresh Token Security Hardening | Applied | Fix CORS, atomic rotation, timezone handling, error handling |
| 004 | ARQ + Upstash Background Processing | Applied | Durable async jobs with startup reconciliation |

---

*This document reflects the state of the codebase as of February 2026.*
