## Summary

Implements Task #166 backend hardening around workspace/query constants and contract clarity:

- Moves workspace document-capacity enforcement to `MAX_DOCUMENTS_PER_WORKSPACE` in `app/constants.py`.
- Centralizes shared query tuning constants (history turns + similarity threshold) in `app/constants.py` and consumes them from both `documents.py` and `workspaces.py` routers.
- Adds a DB-level regression test asserting `check_message_context` prevents rows with both `document_id` and `workspace_id` from being inserted, independent of repository guard logic.
- Adds a regression test that `DELETE /api/workspaces/{workspace_id}/documents/{document_id}` returns `WorkspaceDetailResponse` shape for endpoint contract stability.

## Acceptance criteria

- [x] Workspace limit uses `app/constants.py` source of truth.
- [x] Document/workspace query endpoints share one constants source for similarity and history values.
- [x] Backend tests fail if `check_message_context` DB constraint is removed or weakened.
- [x] Workspace membership document-delete contract is locked to a canonical response shape.
- [x] Backend verification passes.

## Verification

- `make backend-verify`

Closes #166
