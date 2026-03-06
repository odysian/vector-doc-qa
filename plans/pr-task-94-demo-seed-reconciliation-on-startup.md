## Summary
- reconcile demo documents on every startup when the demo account already exists
- keep a fast-path no-op when fixture filename set matches existing demo documents
- extract document seeding into a shared helper used by both initial create and reconcile paths
- add tests for no-op match, mismatch reconciliation, and cascade cleanup of stale chunks/messages

## Verification
- `make backend-verify`

Closes #94
