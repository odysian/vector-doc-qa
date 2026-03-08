## Summary

Refactors `POST /api/documents/upload` and `POST /api/documents/{id}/process` into a ports/adapters vertical slice while preserving endpoint behavior parity.

Closes #114

## Why This Approach

1. Chosen: thin route handlers + explicit upload/process use cases + minimal adapters.
Alternative rejected: keep orchestration in route handlers and only extract helper functions.
Reason: helper extraction improves file size but does not create testable architectural boundaries.
2. Chosen: minimal ports scoped to this slice (`storage`, `document commands`, `queue`).
Alternative rejected: broad unit-of-work/domain service framework now.
Reason: adds abstraction cost before proving value on the first teaching slice.
3. Chosen: preserve current HTTP contracts and queue-failure semantics exactly.
Alternative rejected: normalize error messages/statuses during refactor.
Reason: parity-first refactor avoids hidden behavior regressions.

## Flow (Before -> After)

Before:
- Route performed validation/storage/DB writes/queue calls and HTTP mapping in one function.

After:
- Route maps HTTP request/response and domain errors only.
- Use case orchestrates flow/state transitions.
- Adapters wrap FastAPI upload utils, SQLAlchemy persistence, and queue enqueue service.

## Changes

1. Added application-layer ports and use cases for upload/process orchestration.
2. Added infrastructure adapters for file handling, document persistence, and queue enqueue.
3. Rewired `upload` and `process` endpoints to call use cases and map domain errors to existing HTTP responses.
4. Added use-case tests with fake ports; kept route regression tests for status/message parity.

## Verification

`make backend-verify`

- `ruff check .` passed
- `mypy . --ignore-missing-imports` passed
- `pytest -v` passed (172 tests)
- `bandit -r app/ -ll` passed

## Mentoring Checkpoints

1. Checkpoint 1 (boundaries): learner paraphrases what belongs in route vs use case vs adapter.
2. Checkpoint 2 (upload path): learner paraphrases upload success/failure transitions and retry intent.
3. Checkpoint 3 (process path): learner paraphrases status guardrails and queue-failure behavior parity.
4. Checkpoint 4 (review): learner paraphrases tradeoffs and when to widen this pattern beyond the slice.
