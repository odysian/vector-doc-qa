# Quaero — Document Intelligence Platform

AI-powered PDF question-answering using Retrieval Augmented Generation (RAG). Upload documents, ask questions in plain language, and get grounded answers with cited source excerpts.

**Live Demo:** https://quaero.odysian.dev

## What It Does

- Upload PDF documents (up to 10 MB each)
- Background processing: text extraction, chunking, and embedding generation via OpenAI
- Ask natural language questions against a single document or across a workspace of documents
- Get accurate answers from Claude with inline source citations that link back to the exact PDF page
- Stream answers token-by-token so you see output as it arrives
- Organize documents into workspaces for cross-document RAG queries
- Persistent chat history per document and per workspace
- Demo mode: try the app instantly without registering
- Secure authentication with CSRF protection, httpOnly cookies, and refresh token rotation

## Tech Stack

**Backend:**
- FastAPI (Python 3.12+) with async SQLAlchemy 2.0
- PostgreSQL + pgvector (HNSW index for approximate nearest-neighbor search)
- OpenAI API (`text-embedding-3-small`, 1536 dimensions)
- Anthropic API (Claude 3 Haiku for RAG responses)
- ARQ + Redis (Upstash in production) for durable background document processing
- Google Cloud Storage for uploaded PDF files in production
- JWT authentication (HS256) with Argon2 password hashing
- Refresh token rotation with server-side revocation
- Double-submit CSRF protection
- SlowAPI rate limiting (per-endpoint, per-user/IP)
- Structured JSON logging with request correlation IDs and external provider observability events
- Deployed on a GCP Compute Engine VM behind NGINX with TLS

**Frontend:**
- Next.js 16 + React 19 + TypeScript
- Tailwind CSS v4 with a custom lapis color theme and shared UI primitives
- Inline PDF viewer with page navigation, zoom, and citation highlighting
- Responsive layout: split PDF + chat pane on desktop, tab-switch on mobile
- Deployed on Vercel

**Infrastructure & CI/CD:**
- Terraform-managed GCP infrastructure (VM, static IP, firewall, GCS bucket, IAM)
- GitHub Actions: backend CI (ruff, mypy, pytest, bandit), frontend CI (tsc, ESLint, vitest, next build)
- Manual-dispatch Terraform ops workflow for plan/apply/destroy with typed confirmation gate
- Google Workload Identity Federation (OIDC) for keyless GitHub Actions → GCP auth

**Database:**
- Cloud SQL PostgreSQL with pgvector extension
- Schema-isolated under `quaero` for multi-project sharing on a shared instance
- Alembic migrations (reversible, autogenerate-safe)

## How It Works

```
1. Upload   → PDF validated (magic bytes + size) → saved to GCS → Document row created (PENDING)
             → job enqueued to Redis

2. Process  → ARQ worker picks up job
             → extracts text with pdfplumber
             → chunks into 1000-char segments with 50-char overlap at word boundaries
             → generates embeddings in batch (OpenAI)
             → stores chunks + embeddings in PostgreSQL
             → Document marked COMPLETED

3. Query    → query embedded (OpenAI)
             → cosine similarity search against HNSW index (top 5 chunks)
             → chunks + chat history sent to Claude
             → answer streamed token-by-token to browser
             → message and sources saved to database
```

## Workspaces

Workspaces let you group multiple documents and ask questions across all of them in a single query. Each workspace query embeds your question, searches chunks from every document in the workspace, and passes the top results to Claude — so you can ask "which document mentions X?" or "summarize the differences between these two papers" with a single prompt.

## Deployment

- **Frontend:** Vercel (auto-deploy from `main` branch)
- **Backend:** GCP Compute Engine VM (Docker container, NGINX reverse proxy, TLS via Certbot)
- **Database:** Cloud SQL PostgreSQL with pgvector (shared instance, `quaero` schema isolation)
- **File storage:** Google Cloud Storage bucket
- **Queue:** Upstash Redis
- **CI:** GitHub Actions — backend (ruff + mypy + pytest + bandit) and frontend (tsc + ESLint + vitest + next build) run on every PR; deploy is gated on passing backend tests


## Contact

**Chris**
- GitHub: [@odysian](https://github.com/odysian)
- Website: https://odysian.dev
- Email: c.colosimo@odysian.dev

## License

MIT License
