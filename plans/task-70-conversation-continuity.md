# Task 70 Kickoff Backfill: Conversation Continuity

- Task issue: #70
- Parent spec: #69
- Mode: single
- Branch: task-70-conversation-continuity
- Date: 2026-03-05

## Goal
Implement bounded conversation continuity for document chat follow-ups by including recent in-thread turns in prompt construction for both `/query` and `/query/stream`.

## Non-goals
- Cross-document memory
- Global/session memory outside a document thread
- Schema changes
- UI redesign

## Acceptance Criteria
1. Include a bounded history window (last N turns) in prompt construction for both non-streaming and streaming query paths.
2. Preserve current source/citation behavior.
3. Avoid DB schema changes.
4. Keep history ordering correct (oldest -> newest).
5. Keep user/assistant role formatting explicit in prompt assembly.

## Scope
In scope:
- `backend/app/services/anthropic_service.py`
- `backend/app/api/documents.py`
- backend tests for history window and ordering behavior
- docs updates required by repo workflow (`TESTPLAN.md`, `docs/ARCHITECTURE.md`)

Out of scope:
- frontend behavioral changes
- migrations and schema changes

## Verification Commands
- `make backend-verify`
- `make frontend-verify` only if frontend is touched (not expected)
