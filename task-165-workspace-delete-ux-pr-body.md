## Summary

Implements Task #165 workspace deletion UX in dashboard:

- Adds a workspace delete action to the selected workspace sidebar.
- Adds a dedicated workspace delete confirmation modal before destructive actions.
- Wires modal confirm/cancel flow in dashboard page and keeps modal open on API failure.
- Tightens workspace delete state updates in `useDashboardState` by removing closure-captured `selectedWorkspace` dependency and using explicit `clearSelection` behavior.
- Disables workspace delete action for demo users.
- Adds dashboard regression tests for workspace delete success, cancel, failure, and demo-user restriction.

## Acceptance criteria

- [x] Users can trigger workspace deletion from dashboard UI.
- [x] Deletion requires explicit confirmation.
- [x] UI state is updated correctly after delete (workspace list + selected workspace/viewer state).
- [x] Delete handler state update pattern avoids closure-staleness risk.
- [x] Demo users cannot delete workspaces from UI.
- [x] Frontend tests cover delete success, cancel, and failure behavior.

## Verification

- `make frontend-verify`

Closes #165
