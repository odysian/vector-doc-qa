# ADR-004: Background Document Processing with ARQ + Upstash

**Date:** 2026-02-19
**Status:** Applied
**Branch:** local-working-tree

---

## Context

### Background
Document upload and processing currently use FastAPI endpoints backed by async SQLAlchemy and external AI APIs (OpenAI for embeddings, Anthropic for answers). Processing includes PDF extraction, chunking, and batch embedding generation.

### Problem
`POST /api/documents/{id}/process` performed processing inline. Large documents blocked request handlers and delayed user responses. This also increased request timeout risk on Render free-tier instances.

### Root Cause (if a bug or production incident)
Long-running CPU/network work (PDF parsing + embedding API calls) ran in the HTTP request lifecycle instead of an asynchronous job worker.

---

## Options Considered

### Option A: FastAPI BackgroundTasks
Rejected. Simple to wire, but work is tied to web process lifetime and can be lost on restart/sleep. This is risky on Render free tier where instances spin down.

### Option B: Celery + Redis
Rejected. Durable and widely used, but heavier operational surface area than needed for current project scope.

### Option C: ARQ + Upstash Redis
Accepted. ARQ is async-native, integrates cleanly with existing async services, supports durable queued jobs, and keeps implementation small enough for the current codebase.

---

## Decision

1. Add ARQ + Redis dependencies and queue settings in application config.
2. Add `enqueue_document_processing(document_id)` service with deterministic job IDs (`doc:{id}`) for deduplication.
3. Add ARQ worker modules:
   - `process_document_task` wrapper that creates its own `AsyncSession`
   - worker settings for Redis connection, queue name, timeouts, and low concurrency
4. Update `POST /api/documents/upload` to enqueue processing after creating the document record, while keeping `201 Created`.
5. Update `POST /api/documents/{id}/process` to be enqueue-only (`202 Accepted`) for retries/non-blocking behavior.
6. Add `GET /api/documents/{id}/status` for lightweight polling.
7. Add startup reconciliation in the worker to reset stale `processing` rows back to `pending`.
8. Update frontend dashboard polling to query status while any docs are `pending`/`processing` and stop once all are terminal.

---

## Consequences

- Upload responses return quickly and no longer block on PDF processing/embedding generation.
- Processing jobs survive web process restarts because queue state lives in Redis.
- Duplicate enqueue requests do not create duplicate jobs for the same document.
- Worker restart recovery reduces permanently stuck `processing` statuses.
- Operational complexity increases slightly (Redis + worker lifecycle + poll tuning).
- Polling and queue configuration must be tuned to stay within Upstash free-tier limits.
