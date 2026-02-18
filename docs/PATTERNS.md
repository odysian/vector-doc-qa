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

### Rate Limiting

Use `@limiter.limit()` decorator with appropriate key function:
- Public endpoints (auth): `key_func=get_ip_key`
- Authenticated endpoints: `key_func=get_user_or_ip_key`

```python
@router.post("/login")
@limiter.limit("5/minute", key_func=get_ip_key)
def login(request: Request, ...):
```

### Error Responses

Always use `HTTPException` with `detail` string. Never return raw error objects.

```python
raise HTTPException(status_code=404, detail="Document not found")
raise HTTPException(status_code=400, detail="Only PDF files are allowed")
```

### Document Ownership

Every query for user-specific data filters by `current_user.id`. Never trust the client.

```python
stmt = select(Document).where(
    Document.id == document_id,
    Document.user_id == current_user.id
)
```

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

The frontend reads the non-httpOnly `csrf_token` cookie via `getCsrfToken()` in `lib/api.ts` and echoes it as the `X-CSRF-Token` header on every mutating request (double-submit CSRF pattern). `isLoggedIn()` checks for the presence of this cookie as a fast, client-side session indicator.

All `fetch` calls use `credentials: "include"` so httpOnly cookies are sent cross-origin. The API client handles 401s by attempting a silent token refresh (POST `/api/auth/refresh` — no body required, cookie is the credential) before redirecting to `/login`.

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

---

## Database Patterns

### Schema Isolation

All tables use the `quaero` schema. Alembic env.py filters to only this schema during autogenerate.

### Migrations

- One migration file per schema change
- Never edit a migration after it's been applied
- Alembic version table lives in `quaero` schema
- Initial migration is idempotent (checks if tables exist)

### Foreign Keys

Specify ON DELETE behavior explicitly on relationships that warrant cascades:
- `messages.document_id` → CASCADE (delete messages when document deleted)
- `messages.user_id` → CASCADE (delete messages when user deleted)

---

_Updated as new conventions are established. If you introduce a new pattern, add it here._
