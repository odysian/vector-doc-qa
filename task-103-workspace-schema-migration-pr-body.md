## Summary

Implements Task #103 database schema foundation for workspaces:

- Adds `Workspace` and `WorkspaceDocument` SQLAlchemy models with relationships.
- Updates `Message` model to support document-or-workspace context via nullable `workspace_id` and XOR `document_id`/`workspace_id` check constraint.
- Adds `MAX_DOCUMENTS_PER_WORKSPACE = 20` constant.
- Adds Alembic migration for schema changes and reversible downgrade.
- Updates `docs/ARCHITECTURE.md` schema and relationship sections.

## Acceptance criteria

- [x] `Workspace` and `WorkspaceDocument` models are present.
- [x] `messages.document_id` is nullable and `messages.workspace_id` exists with FK to `workspaces`.
- [x] `Message.workspace` and `Workspace.messages` relationships are wired.
- [x] `Message` check constraint enforces `document_id` XOR `workspace_id`.
- [x] `Workspaces` and `workspace_documents` migration includes reverse-compatible downgrade.
- [x] `MAX_DOCUMENTS_PER_WORKSPACE` is defined.
- [x] Schema docs updated for new tables and relationships.

## Verification

- `make backend-verify`
- `cd backend && .venv/bin/alembic upgrade head && .venv/bin/alembic check && .venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head`

Closes #103
