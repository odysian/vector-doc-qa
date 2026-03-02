## Goal
Enforce strict 1:1 embedding output alignment with input chunk order to prevent silent retrieval corruption.
Default: this Task should represent the entire feature end-to-end unless split criteria apply.

## Scope
**In:**
- Remove/replace batch filtering behavior that can desynchronize embedding order.
- Add explicit input validation for empty/whitespace texts.
- Add tests validating length/order invariants and failure behavior.

**Out:**
- Model provider changes.
- Search scoring algorithm changes.

## Implementation notes
- Parent Spec: #19
- Contract: returned embeddings count/order must always match input `texts`.
- Prefer callee-level contract enforcement in `generate_embeddings_batch` (validate and fail fast) rather than relying on callers to sanitize silently.

## Decision locks (backend-coupled only)
- [ ] Locked: Input policy is callee-enforced fail-fast for invalid/empty text (no silent filtering).
- [ ] Locked: Whether to enforce invariant at caller, callee, or both layers.

## Acceptance criteria
- [ ] `generate_embeddings_batch` no longer silently drops input items.
- [ ] Invalid/empty text input is handled explicitly and predictably.
- [ ] Batch API function documents and enforces its input contract.
- [ ] Embedding assignment to chunks is order-safe and deterministic.
- [ ] Tests cover invariant success path and invalid-input path.

## Verification
```bash
make backend-verify
cd backend && .venv/bin/pytest -v tests/test_documents.py tests/test_query.py
```

## PR checklist
- [ ] PR references this issue (`Closes #...`)
- [ ] Docs updated if needed (`docs/ARCHITECTURE.md`, `docs/PATTERNS.md`, `docs/REVIEW_CHECKLIST.md`, `docs/ISSUES_WORKFLOW.md`, `TESTPLAN.md`, `docs/adr/`)
- [ ] Tests added/updated where needed
