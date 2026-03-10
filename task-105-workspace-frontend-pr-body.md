## Summary

Implements Task #105 workspace frontend UI end-to-end:

- Adds dashboard workspace mode with a `Documents | Workspaces` sidebar toggle and workspace list/create flow.
- Adds workspace sidebar navigation with document add/remove actions.
- Adds workspace document switcher above the PDF pane.
- Adds document picker modal for adding completed documents not already in a workspace.
- Extends chat window + chat state for workspace context (`/api/workspaces/{id}/query` and `/api/workspaces/{id}/messages`) while preserving existing streaming document chat behavior.
- Extends citation payloads with optional `documentId` so workspace citations switch the PDF viewer to the cited source document.
- Adds workspace API types/services and extends the stable API facade with workspace methods.
- Adds/updates frontend tests for workspace service methods, workspace chat path usage, citation payloads, and API contract surface.

## Acceptance criteria

- [x] Sidebar toggle switches between Documents and Workspaces modes.
- [x] Users can create and open workspaces.
- [x] Users can add/remove documents from a workspace via picker/sidebar actions.
- [x] Workspace view shows PDF viewer + chat side by side with document switcher.
- [x] Workspace chat uses workspace query + message endpoints.
- [x] Workspace citations include source document context and can switch viewer document.
- [x] Single-document chat mode remains functional.
- [x] Frontend verification passed.

## Verification

- `make frontend-verify`

Closes #105
