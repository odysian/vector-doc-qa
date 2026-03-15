TUTORING SESSION CONTEXT (do not modify)

I am a junior developer learning through code review. You are a
senior dev explaining this to me as your intern.

My stack: FastAPI, PostgreSQL + pgvector, SQLAlchemy async,
Next.js/TypeScript, Redis, ARQ, OpenAI embeddings, Anthropic API.
My projects: Quaero (RAG/document Q&A), Rostra (real-time chat),
FAROS (task manager/AWS).

How to explain: go block by block, 5-15 lines at a time. For each
block give me WHAT, WHY, TRADEOFF, and PATTERN. Stop after each
block and ask if I want to go deeper or move on. Do not proceed
until I respond.

If a concept connects to Rostra, FAROS, or another part of Quaero,
say so explicitly. If there is a security implication, flag it
with [SECURITY]. If I ask "why not X", give me a real answer.

Depth signals: "keep going" = next block, "go deeper" = expand
current block, "how would I explain this in an interview" = give
me a 2-sentence out-loud answer.
---

## What Was Built

Two small but precise database improvements were merged in one PR. First, `remove_workspace_document` was rewritten to delete a row and confirm its existence in a single SQL round trip using `DELETE ... RETURNING`, replacing a prior SELECT-then-DELETE pattern. Second, a standalone index on `messages.user_id` was added via migration so PostgreSQL can efficiently find all messages for a user when a user is deleted (CASCADE).

## Top 3 Decisions and Why

1. **`DELETE ... RETURNING` instead of SELECT + DELETE** — The old code did two database round trips: one SELECT to check the row existed, then a DELETE. Between those two statements there's a tiny window where another request could delete the same row (TOCTOU — time-of-check to time-of-use). Collapsing it into one statement closes that window and saves a round trip. SQLAlchemy's `.returning()` on a `delete()` statement returns the deleted row's `id` (or `None` if nothing matched), so the True/False return value is preserved with no behavior change.

2. **Declare the new index in `Message.__table_args__` as well as in the migration** — If you create an index via raw SQL in a migration but never tell SQLAlchemy's model metadata about it, `alembic check` will report it as a pending removal every time it runs, because autogenerate sees the index in the live DB but not in the Python model. Adding `Index("ix_quaero_messages_user_id", user_id)` to `__table_args__` makes both match, so `alembic check` stays clean.

3. **Standalone index on `messages.user_id` rather than relying on the existing compound index** — There was already a composite index on `(document_id, user_id, created_at DESC, id DESC)`. In PostgreSQL, a composite index can only accelerate queries that filter on the *leading* column first. A bare `WHERE user_id = ?` scan (which is what a CASCADE delete triggers) cannot use that index — it has to scan the whole table. A dedicated single-column index on `user_id` fixes this.

## Non-Obvious Patterns Used

- **`DELETE ... RETURNING` for existence-check-and-delete in one shot.** Most junior devs reach for SELECT then DELETE. The RETURNING clause on a DELETE lets the database tell you what it deleted. If zero rows matched, `db.scalar()` returns `None` and you know the row wasn't there — no prior read needed. The same pattern is used in `refresh_token_repository.py` for token consumption.

- **`alembic check` as a model-vs-DB drift detector.** `alembic check` runs autogenerate internally and errors if it finds any pending changes. It's how you know your SQLAlchemy models and your live database are in sync. If you add an index to the DB via a migration but forget to declare it in the model, autogenerate will propose removing it. The fix is always to declare the index in both places.

- **`MetaData(schema="quaero")` as the schema source of truth.** The `Base` class in `database.py` uses `metadata = MetaData(schema="quaero")`. This means every model that inherits `Base` automatically lives in the `quaero` schema — you don't need `{"schema": "quaero"}` in every model's `__table_args__`. The `Index` declaration in `__table_args__` inherits the schema from the table it's attached to.

## Tradeoffs Evaluated

- **`op.create_index` vs `op.execute` with raw SQL in the migration.** Both work. `op.create_index` is the "proper" Alembic API and generates the SQL for you. `op.execute` with a raw `CREATE INDEX IF NOT EXISTS` string is what the existing migrations in this repo use, so we matched that convention. The `IF NOT EXISTS` clause makes it idempotent — safe to run twice. Either way, the index must also be declared in the model to keep `alembic check` clean.

- **Single-column index vs adding `user_id` as a leading column to the existing compound index.** Adding `user_id` as the leading column of the compound index would have required dropping and recreating it (a non-trivial migration on a table with data in production). A separate standalone index is cheaper to add and serves exactly the one use case (CASCADE scan) without touching the existing index that the chat history query relies on.

## What I'm Uncertain About

- The `op.drop_index` in the downgrade has no `IF EXISTS` guard. If someone manually drops the index between `alembic upgrade` and `alembic downgrade`, the downgrade will fail with "index does not exist". This affects all migrations in the repo equally and isn't something Alembic's `drop_index` API exposes cleanly — you'd need raw SQL to add `IF EXISTS`. It's a minor edge case but worth knowing.

- There are no tests that verify the index is actually used by the query planner. `alembic check` confirms it exists, but whether PostgreSQL actually switches from a seq-scan to an index scan on a large `messages` table is only visible in `EXPLAIN ANALYZE` output — something the test suite doesn't cover.

## Relevant Code Pointers

- `backend/app/repositories/workspace_repository.py` > line 139 — `remove_workspace_document` rewrite with `DELETE ... RETURNING`
- `backend/app/repositories/refresh_token_repository.py` — prior example of the `DELETE ... RETURNING` pattern (the reference implementation)
- `backend/alembic/versions/e1a2b3c4d5e6_add_messages_user_id_index.py` > line 22 — migration upgrade/downgrade for the new index
- `backend/app/models/message.py` > line 62 — `Index("ix_quaero_messages_user_id", user_id)` in `__table_args__`
- `backend/app/database.py` > line 57 — `MetaData(schema="quaero")` explaining why per-model schema dicts are not needed
