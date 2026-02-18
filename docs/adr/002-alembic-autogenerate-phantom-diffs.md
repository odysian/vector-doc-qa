# ADR-002: Alembic Autogenerate Phantom Diffs (quaero schema)

**Date:** 2026-02-18
**Status:** Applied
**Branch:** main

---

## Context

### Background

All tables use `MetaData(schema="quaero")` with `include_schemas=True` for schema isolation on a shared Render PostgreSQL instance. Alembic's `autogenerate` feature is used to detect drift between ORM models and the live database.

### Problem

Running `alembic revision --autogenerate` produces phantom diffs — false-positive drop+create operations for foreign keys and indexes that already exist correctly in the database:

```
Detected removed foreign key (document_id)(id) on table chunks
Detected added foreign key (document_id)(id) on table quaero.chunks
Detected removed foreign key (document_id)(id) on table messages
Detected added foreign key (document_id)(id) on table quaero.messages
Detected removed table 'alembic_version'
```

These are not real schema changes — the database is already correct. Applying the generated migration would produce no-op operations at best and corrupted state at worst.

### Root Cause

Three interacting issues, all stemming from using `MetaData(schema="quaero")` with `include_schemas=True`:

**1. search_path makes `quaero` the default schema.**
The sync engine URL includes `?options=-c%20search_path=quaero,public`, so when Alembic connects, `quaero` is the default schema. SQLAlchemy caches this as `dialect.default_schema_name = "quaero"`. During reflection with `include_schemas=True`, objects in `quaero` are enumerated as `schema=None` (the default) rather than `schema="quaero"`. The ORM metadata objects have `schema="quaero"` explicitly — so Alembic sees a mismatch and generates phantom drop+create pairs.

**2. `include_object` vs `include_name`.**
The existing `env.py` used `include_object`, which filters reflected objects after they are fully enumerated. The `include_name` callback filters at the schema-name level during enumeration — it's better suited for schema filtering because it receives the schema name directly and prevents schema-level false-positives from ever entering the autogenerate comparison.

**3. No naming convention (latent issue).**
`MetaData` had no `naming_convention`, making auto-generated index names include the schema prefix (`ix_quaero_users_id`). Existing migrations already use these names so there's no active mismatch, but inconsistency with SQLAlchemy conventions is a latent drift risk.

---

## Options Considered

### Option A: Keep `include_object` with patched filtering

Adjust `include_object` to match schema-qualified and unqualified names. Fragile — it requires custom name normalization logic that must account for `dialect.default_schema_name` at runtime. Breaks again if the engine URL or `search_path` changes.

**Rejected.** Too brittle; doesn't address the root cause.

### Option B: Dedicated Alembic engine with `search_path=public` + `include_name` (Chosen)

Create a separate sync engine for Alembic with `connect_args={"options": "-csearch_path=public"}`, overriding the URL-level `search_path`. This forces `default_schema_name = "public"`, so `quaero` is discovered as a named (non-default) schema during reflection — matching the `schema="quaero"` in the ORM metadata. Replace `include_object` with `include_name`, which filters at schema enumeration time. Add a pooler fallback for environments where `options` startup parameters are rejected.

**Accepted.**

### Option C: Manual migrations only (no autogenerate)

Skip `autogenerate` entirely and write all migration operations by hand.

**Rejected.** Eliminates the main value of Alembic for catching schema drift. Error-prone on a team or over time.

---

## Decision

1. Create `_create_alembic_engine()` in `backend/alembic/env.py` that builds the sync engine with `connect_args={"options": "-csearch_path=public"}`. Wrap in a try/except to fall back to a plain engine if the connection fails (e.g. transaction pooler rejecting the `options` startup parameter).
2. Replace `include_object` with `include_name` — accept `schema == "quaero"`, reject everything else when `type_ == "schema"`.
3. Use `sync_engine` directly in `run_migrations_online` instead of `engine_from_config`.
4. Audit models for redundant PK indexes (`index=True` on primary key columns duplicates the PK's implicit index) and fix any found.

Implementation (`backend/alembic/env.py`):

```python
def _create_alembic_engine():
    """Dedicated Alembic engine.

    Overrides search_path to 'public' so Alembic discovers 'quaero' as a
    named (non-default) schema during reflection — eliminating phantom diffs.
    Falls back to plain engine if the pooler rejects the options parameter;
    upgrade/downgrade still works because all operations use explicit schema=.
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


def include_name(name, type_, parent_names):
    """Only process the 'quaero' schema during autogenerate."""
    if type_ == "schema":
        return name == "quaero"
    return True
```

---

## Consequences

- `alembic check` and `alembic revision --autogenerate` no longer produce phantom diffs against a correctly-migrated database.
- Environments using a transaction pooler (PgBouncer) that rejects `options` at startup will fall back to the plain engine — autogenerate may still show phantom diffs in those environments, but `upgrade`/`downgrade` still works because all migration operations use explicit `schema="quaero"`.
- `connect_args` takes precedence over `?options=` in the URL at the libpq protocol level, so the existing URL does not need to be modified.
- Attempting `SET search_path` after connection (e.g. in an event listener) does not work: SQLAlchemy caches `default_schema_name` from the first `SELECT current_schema()` call during engine connect, before post-connect hooks run. `connect_args` is the only reliable way.
- Verified on the Rostra project (`~/rostra-chat-app`), which uses the identical `MetaData(schema=...)` + `include_schemas=True` pattern and had the same phantom FK diffs. The fix eliminated all phantom diffs.
