# PATTERNS.md

Established code conventions in this project. Follow these patterns when adding new code. Do not deviate without discussion.

---

## Backend Patterns

### SQLAlchemy Models (2.0 style)

All models use `Mapped` type hints and `mapped_column`. Never use SQLAlchemy 1.x `Column()` style.

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, ForeignKey

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "quaero"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
```

Every model sets `__table_args__ = {"schema": "quaero"}` for schema isolation.

### SQLAlchemy Queries (2.0 async style)

Use `select()` statements with `await`, not `db.query()`.

```python
from sqlalchemy import select

# Single result
stmt = select(User).where(User.username == username)
user = await db.scalar(stmt)

# Multiple results — note the parentheses around await
stmt = select(Document).where(Document.user_id == user_id)
documents = (await db.scalars(stmt)).all()

# Eager loading to avoid MissingGreenlet on lazy relationships
from sqlalchemy.orm import selectinload

stmt = (
    select(Document)
    .options(selectinload(Document.chunks))
    .where(Document.id == document_id)
)
document = await db.scalar(stmt)
```

### Pydantic Schemas (v2)

Use `model_config = ConfigDict(from_attributes=True)` for ORM compatibility. Use `model_validate()` not `from_orm()`.

```python
from pydantic import BaseModel, ConfigDict

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
```

### Router Structure

Routers are thin — validate input, call service, return response. Business logic lives in `services/`.

```python
@router.post("/upload", status_code=201, response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate → delegate to service → return
```

### Service Layer

Services receive an `AsyncSession` and validated data. They perform business logic and return results or raise `HTTPException`.

```python
async def process_document_text(document_id: int, db: AsyncSession) -> None:
    document = await db.scalar(
        select(Document).where(Document.id == document_id)
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    # ... business logic
```

### Backend Boundary Model

Enforce explicit backend layer direction:

- `api -> services -> repositories`
- `services -> integration services` (storage, queue, embeddings, LLM)
- no cross-layer shortcuts

### Service-Value Rule

Public service functions must add value (orchestration, validation, transaction ownership, policy checks).

- Do not keep pass-through-only public service wrappers in final state.
- For document flows, endpoint orchestration belongs in command service / query service modules.
- `document_service.py` stays worker-focused for background processing.

### Structured Lightweight Comment Policy

Use comments sparingly and only where they add non-obvious context:

- transactional boundaries and rollback intent
- ordering/invariant guarantees
- external API contract assumptions

Do not add comments that only repeat what the next line already says.

### Background Job Queueing

HTTP routes should enqueue background work via a service helper, not import ARQ pool logic directly.

```python
from app.services.queue_service import enqueue_document_processing

enqueued = await enqueue_document_processing(document.id)
```

Use deterministic ARQ job IDs (`doc:{document_id}`) so duplicate enqueue requests do not create duplicate jobs.

### Worker Task Boundaries

Worker tasks create their own `AsyncSession` and call existing service functions. Keep task wrappers thin and focused on orchestration/retry semantics.

```python
async def process_document_task(ctx: dict, document_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await process_document_text(document_id=document_id, db=db)
```

### Document Processing Transactions

Document processing retries use `delete-all-then-rebuild` semantics for chunks.

- At processing start: set `status=PROCESSING`, clear stale failure fields, delete existing chunks for the document, and commit.
- During processing: create chunks and call `flush()` before embedding assignment when IDs/order are needed.
- On failure after `flush()`: call `rollback()` before persisting failure metadata so partial chunk rows are not committed.
- After rollback: re-fetch the document in the same session, set `status=FAILED` + `error_message`, commit, and re-raise.

### Rate Limiting

Use `@limiter.limit()` decorator with appropriate key function:
- Public endpoints (auth): `key_func=get_ip_key`
- Authenticated endpoints: `key_func=get_user_or_ip_key`

```python
@router.post("/login")
@limiter.limit("5/minute", key_func=get_ip_key)
def login(request: Request, ...):
```

Proxy-aware identity rule:
- Trust `X-Forwarded-For` only when the direct peer IP is in `settings.trusted_proxy_ips` (IP/CIDR list).
- Resolve client IP by stripping trusted hops right-to-left in the forwarded chain.
- Ignore forwarded headers from untrusted peers.

### Error Responses

Always use `HTTPException` with `detail` string. Never return raw error objects.

```python
raise HTTPException(status_code=404, detail="Document not found")
raise HTTPException(status_code=400, detail="Only PDF files are allowed")
```

### Query Logging Redaction

In query/search/LLM paths, INFO logs must not include raw user query text.
Log metadata only (for example `document_id`, `user_id`, `query_chars`, `chunk_count`, `top_k`) and keep detailed exception context in error logs.

### Refresh Token Rotation

The refresh endpoint consumes tokens with a single SQL statement (`DELETE ... RETURNING`) and commits exactly once after staging the replacement token.

- Prevents read-then-delete races under concurrent refresh attempts.
- Keeps transaction ownership at the route level.
- Security helpers (`create_refresh_token`, `validate_refresh_token`, consume helpers) must not call `commit()`.

### Document Ownership

Every query for user-specific data filters by `current_user.id`. Never trust the client.

```python
stmt = select(Document).where(
    Document.id == document_id,
    Document.user_id == current_user.id
)
```

### File Storage Backend

Do not read/write document files directly from routes/services. Use `app.services.storage_service` so local and production storage can be switched by config.

```python
from app.services.storage_service import write_file_from_path, read_file_bytes, delete_file

await write_file_from_path(
    "uploads/example.pdf",
    "/tmp/example.pdf",
    content_type="application/pdf",
)
pdf_bytes = await read_file_bytes(document.file_path)
await delete_file(document.file_path)
```

`STORAGE_BACKEND` controls backend selection:
- `local` (default): filesystem in `backend/uploads/`
- `gcs`: Google Cloud Storage bucket (`GCS_BUCKET_NAME`)

### Constants

Magic numbers live in `app/constants.py`, not scattered in code.

```python
MAX_FILE_SIZE_BYTES = 10_485_760  # 10MB
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 50
PDF_MAGIC_BYTES = b"%PDF-"
```

---

## Frontend Patterns

### Client Components

All pages use `"use client"` directive. No server components or server-side data fetching.

### API Client

All API calls go through `lib/api.ts`. Components never use raw `fetch()`.

```typescript
import { api } from "@/lib/api";

const documents = await api.getDocuments();
```

### Auth Token

Stored in httpOnly cookies set by the backend on login/refresh. JS cannot read the `access_token` or `refresh_token` cookies directly.
Login/refresh JSON bodies must not include `access_token` or `refresh_token`; they return only browser-safe fields (`csrf_token`, `token_type`).

Because frontend and backend are on different domains, the frontend reads `csrf_token` from login/refresh JSON responses and stores it in `localStorage`. `getCsrfToken()` in `lib/api.ts` reads this value and echoes it as `X-CSRF-Token` on mutating requests (double-submit CSRF pattern). `isLoggedIn()` checks for the presence of this `localStorage` value as a fast client-side session indicator.

All `fetch` calls use `credentials: "include"` so httpOnly cookies are sent cross-origin. The API client handles 401s by attempting a silent token refresh (POST `/api/auth/refresh` — no body required, cookie is the credential). If refresh fails, the API client throws `SessionExpiredError` and route/page-level UI boundaries perform the redirect to `/login`.

### TypeScript Types

All API response types live in `lib/api.types.ts`. Components import from there.

```typescript
import type { Document, QueryResponse } from "@/lib/api.types";
```

### Component Organization

Dashboard components live in `app/components/dashboard/`. Each component is a single file with its props interface defined inline.

```typescript
interface UploadZoneProps {
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
}

export default function UploadZone({ onUpload, disabled }: UploadZoneProps) {
```

### Styling

- Tailwind CSS utility classes for all styling
- Custom theme tokens in `globals.css` (lapis color palette)
- Semantic CSS classes for typography (`.text-meta`, `.text-section`, `.text-error`, etc.)
- No inline `style` objects
- Dark theme by default (zinc backgrounds, light text)

### Path Aliases

Use `@/` prefix for imports from the project root.

```typescript
import { api } from "@/lib/api";
import ChatWindow from "@/app/components/dashboard/ChatWindow";
```

### Error Handling

API errors are caught and displayed in component state. Use `ApiError` class from `lib/api.types.ts`.

```typescript
try {
  await api.uploadDocument(file);
} catch (err) {
  if (err instanceof ApiError) {
    setError(err.detail);
  }
}
```

### Dashboard Polling

Use the lightweight status endpoint for frequent updates while documents are in `pending` or `processing`. Stop polling when all documents reach terminal states (`completed` or `failed`).

### Citation Highlight Heuristics

PDF citation text highlighting uses a three-stage strategy:

1. Start-anchored phrase matching against text-layer spans
2. Broader phrase-window matching on the cited page
3. Token-overlap fallback with confidence gates

Fallback text highlight is applied only when overlap confidence is sufficient (minimum per-span overlap score, run score, and unique matched token count). If confidence is low, the UI falls back to page-level highlight only.

---

## Database Patterns

### Schema Isolation

All tables use the `quaero` schema. Alembic env.py filters to only this schema during autogenerate.

### Migrations

- One migration file per schema change
- Never edit a migration after it's been applied
- Alembic version table lives in `quaero` schema
- Initial migration is idempotent (checks if tables exist)

### Autogenerate Hardening

`alembic/env.py` includes controls to make `alembic check` and `alembic revision --autogenerate` deterministic for the `quaero` schema:

**search_path override:** The migration engine is created with `connect_args={"options": "-csearch_path=public"}` so that `default_schema_name` is `public`, not `quaero`. Without this, Alembic maps `quaero` → `None` internally, causing reflected tables to have `schema=None` while models declare `schema='quaero'` — producing phantom FK diffs.

**include_name filter:** Only the `quaero` schema is reflected. Public-schema objects (extension tables, other apps) are never loaded.

**include_object filter:** Secondary guard that rejects any reflected object outside `quaero` and filters the `alembic_version` infrastructure table.

**compare_type hook:** Suppresses false-positive ENUM type diffs where reflected PG ENUMs have `schema='quaero'` but model Enums do not.

**Review policy for autogenerated migrations:**
- Always run `alembic check` before committing — it must exit clean
- Always inspect autogenerated revision files before committing

### Foreign Keys

Specify ON DELETE behavior explicitly on relationships that warrant cascades:
- `messages.document_id` → CASCADE (delete messages when document deleted)
- `messages.user_id` → CASCADE (delete messages when user deleted)

---

_Updated as new conventions are established. If you introduce a new pattern, add it here._
