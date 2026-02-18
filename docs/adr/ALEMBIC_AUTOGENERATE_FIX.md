# Fix: Alembic Autogenerate Phantom Diffs (quaero schema)

## Problem

Running `alembic revision --autogenerate` produces phantom diffs — false-positive drop+create operations for foreign keys and indexes that already exist in the database. Example output:

```
Detected removed foreign key (document_id)(id) on table chunks
Detected added foreign key (document_id)(id) on table quaero.chunks
Detected removed foreign key (document_id)(id) on table messages
Detected added foreign key (document_id)(id) on table quaero.messages
Detected removed table 'alembic_version'
```

The generated migration contains matching `drop_constraint` / `create_foreign_key` pairs and spurious `drop_table('alembic_version')`. These are not real schema changes — the DB is already correct.

## Root Cause

Three interacting issues, all stemming from using `MetaData(schema="quaero")` with `include_schemas=True`:

### 1. search_path makes quaero the "default" schema

The sync engine URL includes `?options=-c%20search_path=quaero,public`, so when Alembic connects, `quaero` is the default schema (`SELECT current_schema()` returns `quaero`). SQLAlchemy caches this as `dialect.default_schema_name = "quaero"`.

When Alembic reflects the database with `include_schemas=True`, it enumerates schemas. But because `quaero` IS the default, it's enumerated as `None` (the default schema), not as the named schema `"quaero"`. The `include_object` filter then sees reflected objects with `schema=None` while the metadata objects have `schema="quaero"` — they don't match, causing phantom drop+create pairs.

### 2. include_object vs include_name

The current `env.py` uses `include_object`, which filters at the object level after reflection. The newer `include_name` callback filters at the name level during reflection and is better suited for schema filtering because it receives the schema name directly.

### 3. No naming convention (not causing phantom diffs yet, but a latent issue)

The `MetaData` has no `naming_convention`, so the default convention includes the schema prefix in auto-generated index names (e.g., `ix_quaero_users_id`). The existing migrations already use these schema-prefixed names, so there's no mismatch *today*. But this is inconsistent with best practice and would cause issues if the naming convention were changed later.

## Fix (3 parts)

### Part 1: Dedicated Alembic engine with overridden search_path

In `env.py`, create a sync engine that sets `search_path=public` via `connect_args`. This forces SQLAlchemy's `default_schema_name` to be `public`, so Alembic discovers `quaero` as a named (non-default) schema during reflection.

**Why `connect_args` instead of `SET search_path` after connecting?** SQLAlchemy caches `default_schema_name` at dialect initialization (first connection). A `SET` after connecting is too late — the cached value won't change. `connect_args={"options": "-csearch_path=public"}` sets search_path at the libpq protocol level *before* dialect initialization.

**Pooler fallback:** If using a transaction pooler (PgBouncer/Supabase), it may reject the `options` startup parameter. Wrap the engine creation in try/except and fall back to a plain engine. The fallback may produce phantom diffs in autogenerate, but `upgrade`/`downgrade` still works because all migration operations use explicit `schema="quaero"`.

### Part 2: Replace include_object with include_name

Switch from `include_object` to `include_name`. The callback should accept `schema == "quaero"` and reject everything else when `type_ == "schema"`.

### Part 3: Align model indexes with DB (audit)

After Parts 1-2, run `alembic check` or `alembic revision --autogenerate -m "test"` and inspect the output. Any remaining diffs are *real* discrepancies between models and the database. Fix these by either:
- Adding missing `Index(...)` objects to model `__table_args__` (if the index exists in DB but not in the model)
- Removing `index=True` from columns where the index is redundant (e.g., primary keys)

## Implementation

### Step 1: Edit `backend/alembic/env.py`

Replace the current file with:

```python
from collections.abc import MutableMapping
from logging.config import fileConfig
from typing import Literal

from sqlalchemy import create_engine, text

from alembic import context
from app.config import settings
from app.database import Base

# Import all models so Alembic can discover them
from app.models import base, message, refresh_token, user  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _create_alembic_engine():
    """Create sync engine for Alembic migrations.

    Overrides search_path to 'public' so Alembic discovers 'quaero'
    as a named schema (needed for clean autogenerate). If the connection
    fails — e.g. a transaction pooler rejects the 'options' startup
    parameter — falls back to a plain engine. Autogenerate may produce
    phantom diffs with the fallback, but upgrade/downgrade still works
    since all migration operations use explicit schema="quaero".
    """
    engine_with_override = create_engine(
        settings.database_url,
        connect_args={"options": "-csearch_path=public"},
    )
    try:
        with engine_with_override.connect():
            pass
        return engine_with_override
    except Exception:
        engine_with_override.dispose()
        return create_engine(settings.database_url)


sync_engine = _create_alembic_engine()


_NameType = Literal[
    "schema", "table", "column", "index", "unique_constraint", "foreign_key_constraint"
]
_ParentKey = Literal["schema_name", "table_name", "schema_qualified_table_name"]


def include_name(
    name: str | None, type_: _NameType, parent_names: MutableMapping[_ParentKey, str | None]
) -> bool:
    """Only process the 'quaero' schema during autogenerate.

    Without this filter, Alembic would also reflect 'public' and
    produce unwanted operations (like dropping alembic_version).
    """
    if type_ == "schema":
        return name == "quaero"
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.database_url

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema=target_metadata.schema,
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = sync_engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=target_metadata.schema,
            include_schemas=True,
            include_name=include_name,
        )

        with context.begin_transaction():
            connection.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {target_metadata.schema}")
            )

            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Key changes from the current env.py:**
- Dedicated `_create_alembic_engine()` with `connect_args={"options": "-csearch_path=public"}` + pooler fallback
- Replaced `include_object` with `include_name` (schema-level filter)
- Uses `sync_engine` directly instead of `engine_from_config`

**Important:** Check that the import paths match the project (`from app.config import settings`, `from app.database import Base`, model imports). Adjust if the project structure differs.

### Step 2: Audit model-DB alignment

After applying Step 1, run:

```bash
cd backend
alembic revision --autogenerate -m "test"
```

Inspect the generated migration. Any remaining operations are real discrepancies. Common ones to look for:

1. **Redundant PK indexes** — `index=True` on primary key columns generates an explicit index that duplicates the PK's implicit index. Remove `index=True` from PK columns:
   ```python
   # Before
   id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
   # After
   id: Mapped[int] = mapped_column(Integer, primary_key=True)
   ```

2. **Inconsistent FK references** — Some models use unqualified FKs (`"users.id"`) while `refresh_token.py` uses qualified (`"quaero.users.id"`). Both work at runtime, but pick one convention. With the search_path override in env.py, unqualified FKs should resolve correctly during autogenerate.

3. **Missing indexes** — If the DB has indexes created in migrations that aren't reflected in model definitions, add them to `__table_args__`.

Delete the test migration after inspection:
```bash
rm alembic/versions/<generated_file>.py
```

### Step 3: Verify

```bash
cd backend

# Should report "No new upgrade operations detected"
alembic check

# Or generate an empty migration (no operations in upgrade/downgrade)
alembic revision --autogenerate -m "verify-clean"

# Test migration round-trip
alembic downgrade -1
alembic upgrade head
```

## Gotchas

- **`connect_args` URL stripping:** The `settings.database_url` may include `?options=-c%20search_path=quaero,public`. The `connect_args={"options": "-csearch_path=public"}` in the engine creation *overrides* the URL-level options because `connect_args` takes precedence at the libpq level. However, if the URL uses a different format or the driver interprets it differently, you may need to strip the `?options=` from the URL before passing it to `create_engine`. Test by adding a temporary `print(sync_engine.url)` and verifying the connection works.

- **Transaction poolers (PgBouncer/Supabase):** The `options` startup parameter is a libpq feature. Transaction poolers that multiplex connections may reject it. The fallback engine handles this, but autogenerate won't be clean through the pooler. Run `alembic` commands against the direct connection URL (port 5432), not the pooler URL (port 6543).

- **Don't modify existing migrations.** Even if old migrations have schema-prefixed index names (`ix_quaero_users_id`), those are baked into the DB. Changing them requires a new migration with explicit rename operations. The fix prevents *new* phantom diffs — it doesn't retroactively clean up old naming.

- **`default_schema_name` caching:** If you try `SET search_path TO public` in an event listener or after connection instead of `connect_args`, it won't work. SQLAlchemy caches `default_schema_name` from the first `SELECT current_schema()` call during `engine.connect()`, before any post-connect hooks run.

## Reference

This fix was developed and verified on the Rostra project (`~/rostra-chat-app`) which uses the same pattern (`MetaData(schema="rostra")` + `include_schemas=True`) and had identical phantom FK diffs. The fix eliminated all phantom diffs and produced clean empty autogenerate output.
