## Summary

Add a pgvector ANN index for chunk embeddings to reduce vector retrieval latency as corpus size grows (P2-10).

Roadmap source: `plans/high-visibility-features/high-visibility-features.md` (Remaining P2 audit item P2-10).

## What this delivers

1. Alembic revision that adds an HNSW index on `quaero.chunks.embedding` for cosine distance search
2. Reversible migration (downgrade drops ANN index)
3. No API contract changes and no query response-shape changes
4. Operational notes for when ANN is expected to help and how to verify planner usage

## Scope

- Add ANN index migration (Alembic-managed):
  - index type: `hnsw`
  - operator class: `vector_cosine_ops`
  - partial predicate: `WHERE embedding IS NOT NULL`
- Keep existing query/search endpoint contracts unchanged
- Update docs with a short verification note (`docs/ARCHITECTURE.md` or runbook section)

## Non-goals

- No schema redesign or table partitioning
- No multi-document/global retrieval redesign
- No forced planner hints or unsafe query hacks
- No frontend changes

## Decision Locks

- **Index strategy:** HNSW over `chunks.embedding` with cosine operator class (`vector_cosine_ops`) because current retrieval uses cosine distance.
- **Safety:** Keep current retrieval logic behaviorally unchanged; this task introduces indexing only.
- **Rollout:** Do not introduce new API fields or endpoint behavior changes in this task.

## Acceptance Criteria

- [ ] Alembic migration creates `ix_quaero_chunks_embedding_hnsw` on `quaero.chunks` using `hnsw (embedding vector_cosine_ops)` with `WHERE embedding IS NOT NULL`
- [ ] Migration downgrade removes `ix_quaero_chunks_embedding_hnsw`
- [ ] Existing `/search`, `/query`, and `/query/stream` behavior remains unchanged
- [ ] Documentation includes ANN verification commands and caveat about planner behavior under document-level filtering
- [ ] `make backend-verify` passes
- [ ] `cd backend && .venv/bin/alembic check` passes

## Implementation Notes

- Use an Alembic revision file and execute static DDL inside that revision for clarity, for example:

```sql
CREATE INDEX IF NOT EXISTS ix_quaero_chunks_embedding_hnsw
ON quaero.chunks
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;
```

- Keep migration idempotent style consistent with existing migration patterns where practical.
- ANN is approximate; retrieval quality should be monitored after rollout.
- Because current queries filter by `document_id`, planner usage may vary by data size/selectivity. Include a short runbook note on expected behavior and how to inspect plans.

## Security Notes

- This task does **not** add runtime raw SQL paths in application code.
- SQL is static migration DDL only, stored in versioned Alembic revision files.
- Do not interpolate user input into migration SQL.
- Keep changes limited to index creation/removal; no permission or auth model changes.

## Verification

```bash
make backend-verify

cd backend
.venv/bin/alembic check

# After applying migration in target env:
# Confirm ANN index exists
psql "$DATABASE_URL" -c "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'quaero' AND tablename = 'chunks' AND indexname = 'ix_quaero_chunks_embedding_hnsw';"

# Inspect planner behavior on representative vector query
psql "$DATABASE_URL" -c "EXPLAIN (ANALYZE, BUFFERS) SELECT id FROM quaero.chunks WHERE embedding IS NOT NULL ORDER BY embedding <=> (SELECT embedding FROM quaero.chunks WHERE embedding IS NOT NULL LIMIT 1) LIMIT 5;"
```

## Files in scope

- `backend/alembic/versions/<new_revision>_add_hnsw_index_on_chunks_embedding.py`
- `docs/ARCHITECTURE.md` (or `docs/GCP_RUNBOOK.md`) for ANN verification notes

## Files explicitly out of scope

- `frontend/**`
- API schema files
- Query endpoint contracts

## Labels

`type:task`, `area:backend`, `area:db`
