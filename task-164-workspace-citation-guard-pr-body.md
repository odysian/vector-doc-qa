## Summary

Implements Task #164 to prevent misleading workspace citation interactions when cited documents are no longer in the active workspace:

- Restricts workspace citation clickability in `ChatWindow` to sources whose `document_id` is present in the selected workspace document list.
- Adds disabled UI affordance (`aria-disabled`, non-interactive styling, no button role/tab index) for workspace source cards that reference missing documents.
- Adds a defensive guard in `useDashboardState.handleCitationClick` so missing-source workspace citations do not switch documents, switch tabs, or apply highlight state.
- Wires active workspace document IDs from dashboard into `ChatWindow`.
- Adds frontend regression tests for present-source clickable behavior, absent-source non-clickable behavior, and no highlight side effects in the absent-source case.

## Acceptance criteria

- [x] Workspace source cards are clickable only when `source.document_id` exists in `selectedWorkspace.documents`.
- [x] Clicking a citation for an absent source document does not switch viewer document and does not apply page/snippet highlights.
- [x] Single-document mode citation interaction remains unchanged.
- [x] Frontend tests cover both present-source and absent-source workspace citation cases.

## Verification

- `make frontend-verify`

Closes #164
