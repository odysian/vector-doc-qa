## Goal
Prevent partial-chunk persistence on processing failure and guarantee clean, idempotent retries for document processing.
Default: this Task should represent the entire feature end-to-end unless split criteria apply.

## Scope
**In:**
- Ensure failed processing does not commit partial chunk rows.
- Ensure retries do not duplicate chunks.
- Add tests for failure-after-flush and retry behavior.

**Out:**
- New chunking strategy or search ranking changes.
- Broader worker architecture changes.

## Implementation notes
- Parent Spec: #19
- Use explicit rollback and document re-fetch strategy before marking failed status.
- Make failed-status persistence mechanics explicit: either
  - persist failure state in a fresh transaction/session after rollback, or
  - rollback and then re-fetch/persist in the same session with clear ordering and tests.
- Enforce cleanup/replace semantics for existing chunks at processing start.

## Decision locks (backend-coupled only)
- [ ] Locked: Retry semantics (delete-all-then-rebuild vs alternative reconciliation approach).
- [ ] Locked: Error-status persistence strategy after rollback (same session vs separate transaction/session).

## Acceptance criteria
- [ ] Failures after chunk `flush()` do not leave committed partial chunks.
- [ ] Retrying a failed document results in one canonical chunk set (no duplicates).
- [ ] Failed document status/error persistence remains reliable after rollback path.
- [ ] Existing success path remains unchanged from user perspective.
- [ ] Tests explicitly cover partial-failure + retry scenarios.

## Verification
```bash
make backend-verify
cd backend && .venv/bin/pytest -v tests/test_document_tasks.py tests/test_documents.py tests/test_query.py
```

## PR checklist
- [ ] PR references this issue (`Closes #...`)
- [ ] Docs updated if needed (`docs/ARCHITECTURE.md`, `docs/PATTERNS.md`, `docs/REVIEW_CHECKLIST.md`, `docs/ISSUES_WORKFLOW.md`, `TESTPLAN.md`, `docs/adr/`)
- [ ] Tests added/updated where needed
