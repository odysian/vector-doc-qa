# ARCHITECTURE.md

## System Overview

Quaero is a document intelligence platform that allows users to upload PDF documents, processes them into vector embeddings, and provides AI-powered question-answering with source citations using Retrieval Augmented Generation (RAG). Built for a portfolio project demonstrating full-stack development, AI integration, and production deployment.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Next.js 16 + React 19 + TypeScript | App Router, type safety, Vercel deployment |
| Styling | Tailwind CSS 4 | Utility-first, custom theme tokens |
| Backend | FastAPI (Python 3.12+) | Auto-docs, Pydantic validation, lightweight |
| ORM | SQLAlchemy 2.0 (sync) | Type-safe models, mapped_column, select() |
| Database | PostgreSQL + pgvector | Relational + vector similarity search |
| Embeddings | OpenAI text-embedding-3-small | 1536 dimensions, cost-effective |
| RAG | Anthropic Claude (claude-3-haiku) | Fast, accurate answers with citations |
| Auth | JWT (HS256) + Argon2 | Stateless auth, secure password hashing |
| Rate Limiting | SlowAPI | Per-endpoint cost control |
| PDF Processing | pdfplumber | Reliable text extraction |
| Deployment | Vercel (FE) + Render (BE + DB) | Free tier, auto-deploy from main |

---

## System Diagram

```
[Browser]
    |
    v
[Next.js Frontend (Vercel)]
    |  (REST API — Authorization: Bearer <JWT>)
    v
[FastAPI Backend (Render)]
    |
    ├──> [PostgreSQL + pgvector (Render)]
    |         quaero schema
    |         tables: users, documents, chunks, messages
    |
    ├──> [OpenAI API]
    |         text-embedding-3-small (1536 dims)
    |         generates embeddings for chunks + queries
    |
    └──> [Anthropic API]
              claude-3-haiku
              generates RAG answers from retrieved chunks
```

### Data Flow: Upload → Query

```
1. Upload:   User → PDF file → Backend validates (magic bytes, size)
                              → Saves to disk (backend/uploads/)
                              → Creates Document record (status: PENDING)

2. Process:  User triggers → Backend extracts text (pdfplumber)
                           → Chunks text (1000 chars, 50 overlap, word boundaries)
                           → Generates embeddings (OpenAI batch API)
                           → Stores chunks + embeddings in PostgreSQL
                           → Updates Document (status: COMPLETED)

3. Query:    User asks question → Backend generates query embedding (OpenAI)
                                → Cosine similarity search in pgvector (top 5 chunks)
                                → Sends chunks + question to Claude
                                → Claude returns answer with source citations
                                → Saves user message + assistant response to messages table
```

---

## Database Schema

All tables live in the `quaero` schema for isolation on shared PostgreSQL.

### users

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| username | VARCHAR(50) | UNIQUE, NOT NULL, indexed |
| email | VARCHAR(100) | UNIQUE, NOT NULL, indexed |
| hashed_password | VARCHAR(255) | NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT now() |

### documents

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| filename | VARCHAR(255) | NOT NULL |
| file_path | VARCHAR(500) | NOT NULL |
| file_size | INTEGER | NOT NULL |
| status | documentstatus (ENUM) | NOT NULL (PENDING, PROCESSING, COMPLETED, FAILED) |
| user_id | INTEGER | FK → users.id, NOT NULL |
| uploaded_at | TIMESTAMP | NOT NULL |
| processed_at | TIMESTAMP | nullable |
| error_message | TEXT | nullable |

### chunks

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| document_id | INTEGER | FK → documents.id, NOT NULL |
| content | TEXT | NOT NULL |
| chunk_index | INTEGER | NOT NULL |
| embedding | VECTOR(1536) | nullable (populated during processing) |
| created_at | TIMESTAMP | NOT NULL |

### messages

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| document_id | INTEGER | FK → documents.id, ON DELETE CASCADE |
| user_id | INTEGER | FK → users.id, ON DELETE CASCADE |
| role | VARCHAR(20) | NOT NULL, CHECK IN ('user', 'assistant') |
| content | TEXT | NOT NULL |
| sources | JSONB | nullable (search results for assistant messages) |
| created_at | TIMESTAMP | DEFAULT now(), NOT NULL |

### Relationships

- users (1) → documents (N): user uploads documents
- documents (1) → chunks (N): document is split into chunks
- documents (1) → messages (N): chat history per document (CASCADE delete)
- users (1) → messages (N): user's chat messages (CASCADE delete)

### Indexes

| Table | Column(s) | Type | Why |
|-------|-----------|------|-----|
| users | username | UNIQUE | Login lookup |
| users | email | UNIQUE | Registration uniqueness |
| documents | status | BTREE | Filter by processing state |
| documents | user_id | BTREE | User's document list |
| chunks | document_id | BTREE | Chunk retrieval for a document |

---

## API Contracts

### System

#### GET /
- **Auth:** None
- **Response (200):** `{ "message": "Quaero API", "docs": "/docs" }`

#### GET /health
- **Auth:** None
- **Response (200):** `{ "status": "healthy", "database": "connected" }`
- **Response (503):** `{ "status": "unhealthy", "database": "disconnected", "error": "..." }`

### Authentication

#### POST /api/auth/register
- **Auth:** None
- **Rate Limit:** 3/hour per IP
- **Request Body:** `{ "username": "string", "email": "string", "password": "string" }`
- **Success (201):** `{ "id": 1, "username": "chris", "email": "chris@example.com", "created_at": "..." }`
- **Errors:**
  - 422: Validation error (missing/invalid fields)
  - 400: Username or email already registered

#### POST /api/auth/login
- **Auth:** None
- **Rate Limit:** 5/minute per IP
- **Request Body:** `{ "username": "string", "password": "string" }`
- **Success (200):** `{ "access_token": "jwt...", "token_type": "bearer" }`
- **Errors:**
  - 401: Invalid username or password

#### GET /api/auth/me
- **Auth:** Required (Bearer token)
- **Success (200):** `{ "id": 1, "username": "chris", "email": "chris@example.com", "created_at": "..." }`
- **Errors:**
  - 401: Invalid or missing token

### Documents

#### POST /api/documents/upload
- **Auth:** Required
- **Rate Limit:** 5/hour per user/IP
- **Request Body:** multipart/form-data with `file` field (PDF, max 10MB)
- **Success (201):** Document object (status: PENDING)
- **Errors:**
  - 400: Not a PDF, file too large, invalid magic bytes
  - 401: Not authenticated

#### GET /api/documents/
- **Auth:** Required
- **Rate Limit:** 20/hour per user/IP
- **Success (200):** `{ "documents": [...], "total": N }`
- **Notes:** Returns only the authenticated user's documents

#### GET /api/documents/{document_id}
- **Auth:** Required
- **Rate Limit:** 30/hour per user/IP
- **Success (200):** Document object
- **Errors:**
  - 404: Document not found or belongs to another user

#### DELETE /api/documents/{document_id}
- **Auth:** Required
- **Rate Limit:** 10/hour per user/IP
- **Success (200):** `{ "message": "Document deleted successfully" }`
- **Errors:**
  - 404: Document not found or belongs to another user

#### POST /api/documents/{document_id}/process
- **Auth:** Required
- **Rate Limit:** 5/hour per user/IP
- **Success (200):** `{ "message": "Document processing started" }`
- **Notes:** Processes synchronously (blocking). Only works on PENDING or FAILED documents.
- **Errors:**
  - 404: Document not found
  - 400: Document already processed or processing

#### POST /api/documents/{document_id}/search
- **Auth:** Required
- **Rate Limit:** 15/hour per user/IP
- **Request Body:** `{ "query": "string", "top_k": 5 }`
- **Success (200):** `{ "query": "...", "results": [{ "chunk_id": 1, "content": "...", "similarity": 0.85, "chunk_index": 3 }] }`
- **Errors:**
  - 404: Document not found

#### POST /api/documents/{document_id}/query
- **Auth:** Required
- **Rate Limit:** 10/hour per user/IP
- **Request Body:** `{ "query": "string" }`
- **Success (200):** `{ "query": "...", "answer": "...", "sources": [...] }`
- **Notes:** Full RAG pipeline — embeds query, searches chunks, sends to Claude, saves messages
- **Errors:**
  - 404: Document not found

#### GET /api/documents/{document_id}/messages
- **Auth:** Required
- **Rate Limit:** 30/hour per user/IP
- **Success (200):** `{ "messages": [{ "id": 1, "role": "user", "content": "...", "sources": [...], "created_at": "..." }] }`
- **Notes:** Returns chat history for a specific document

---

## Key Decisions

| Decision | Choice | Alternatives Considered | Why |
|----------|--------|------------------------|-----|
| Vector database | pgvector extension | Pinecone, Weaviate | Simpler for this scale, no extra service |
| Embedding model | text-embedding-3-small | text-embedding-3-large, ada-002 | Cost-effective, 1536 dims is sufficient |
| RAG model | Claude 3 Haiku | GPT-4, Claude Sonnet | Fast response, cost-effective for Q&A |
| Password hashing | Argon2 | bcrypt | Modern, memory-hard, winner of PHC |
| PDF extraction | pdfplumber | PyPDF2, PyMuPDF | Best text quality, handles complex layouts |
| Chunk strategy | 1000 chars / 50 overlap | 500 chars, sentence-based | Balance between context and precision |
| Schema isolation | quaero schema | Separate database | Shares Render free-tier DB across projects |
| Auth token storage | localStorage | httpOnly cookies | Simpler implementation for SPA |
| DB driver | psycopg2 (sync) | asyncpg (async) | Simpler, sufficient for current load |
| Rate limiting | SlowAPI | Custom middleware | Battle-tested, per-endpoint configuration |

---

## Directory Structure

```
vector-doc-qa/
├── AGENTS.md
├── WORKFLOW.md
├── README.md
├── docker-compose.yml
├── .gitignore
│
├── docs/
│   ├── ARCHITECTURE.md          ← you are here
│   ├── PATTERNS.md
│   ├── REVIEW_CHECKLIST.md
│   ├── deployment.md
│   ├── delete-flow.md
│   ├── empty-and-loading-states.md
│   ├── custom-domain-cloudflare.md
│   ├── UX_IMPROVEMENTS.md
│   └── TIPS.md
│
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, middleware, lifespan
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── constants.py         # App-wide constants
│   │   ├── database.py          # Engine, SessionLocal, Base, init_db
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # Document, Chunk, DocumentStatus (enum)
│   │   │   ├── user.py          # User model
│   │   │   └── message.py       # Message model
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── document.py      # DocumentResponse, SearchRequest, QueryRequest, etc.
│   │   │   └── auth.py          # UserCreate, UserLogin, UserResponse, Token
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          # /api/auth/* routes
│   │   │   ├── documents.py     # /api/documents/* routes
│   │   │   └── dependencies.py  # get_db, get_current_user
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py   # PDF processing pipeline
│   │   │   ├── search_service.py     # Vector similarity search
│   │   │   ├── embedding_service.py  # OpenAI embedding generation
│   │   │   └── anthropic_service.py  # Claude RAG answer generation
│   │   │
│   │   ├── core/
│   │   │   └── security.py      # JWT create/decode, password hash/verify
│   │   │
│   │   └── utils/
│   │       ├── file_utils.py    # PDF validation, upload handling
│   │       ├── pdf_utils.py     # Text extraction, chunking
│   │       └── rate_limit.py    # SlowAPI limiter setup
│   │
│   ├── alembic/
│   │   ├── env.py               # Migration environment (quaero schema)
│   │   └── versions/
│   │       └── 49b4e1e72658_*.py  # Initial migration
│   │
│   ├── tests/
│   │   ├── conftest.py            # Test DB, fixtures, mocks
│   │   ├── test_auth.py           # Auth endpoint tests
│   │   ├── test_documents.py      # Document CRUD + processing tests
│   │   └── test_query.py          # Search, RAG query, messages tests
│   │
│   ├── alembic.ini
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── .env.example
│   └── test_setup.py            # Setup verification script
│
└── frontend/
    ├── app/
    │   ├── layout.tsx           # Root layout (fonts, metadata)
    │   ├── page.tsx             # Landing page
    │   ├── login/page.tsx       # Login form
    │   ├── register/page.tsx    # Registration form
    │   ├── dashboard/page.tsx   # Main app (protected)
    │   ├── globals.css          # Tailwind + lapis theme + typography
    │   └── components/
    │       └── dashboard/
    │           ├── ChatWindow.tsx
    │           ├── DocumentList.tsx
    │           ├── UploadZone.tsx
    │           └── DeleteDocumentModal.tsx
    │
    ├── lib/
    │   ├── api.ts               # Centralized API client
    │   └── api.types.ts         # TypeScript interfaces
    │
    ├── package.json
    ├── tsconfig.json
    ├── next.config.ts
    └── postcss.config.mjs
```
