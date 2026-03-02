## Summary
Harden the highest-risk findings from the 2026-02-28 audit by addressing token confidentiality, auth refresh correctness, processing data integrity, rate-limit correctness behind proxying, and insecure runtime/infra defaults.

## Status Snapshot (2026-02-28)
- Parent Spec issue: [#19](https://github.com/odysian/vector-doc-qa/issues/19) (`OPEN`)
- Child Task [#20](https://github.com/odysian/vector-doc-qa/issues/20) completed and merged via PR [#27](https://github.com/odysian/vector-doc-qa/pull/27).
- Remaining child tasks are still pending implementation.

## Value / User Impact
- Reduces immediate account-takeover risk from token exfiltration.
- Prevents subtle auth/session correctness bugs under concurrency.
- Prevents retrieval-quality regressions caused by chunk/embedding data corruption.
- Improves production resilience and operational safety defaults.

## Scope
**In scope:**
- P0 token response hardening for cookie-auth flows.
- P1 refresh rotation atomicity.
- P1 processing retry idempotency and embedding-order correctness.
- P1 proxy-aware rate-limiting key derivation.
- P1 runtime config guardrails for sensitive defaults.
- P1 Terraform hardening defaults (SSH CIDR, secure boot, least privilege scope/role).

**Out of scope:**
- P2/P3 cleanup items from audit unless directly required.
- Broad frontend redesign/refactor.
- Unrelated infra modernization outside identified hardening controls.

## How it works (expected behavior)
1. Login/refresh set cookies and return only browser-safe auth payload fields.
2. Refresh-token rotation is atomic and race-safe under concurrent requests.
3. Failed processing does not persist partial chunk state; retries produce one canonical chunk set.
4. Embedding generation preserves strict 1:1 order/length mapping with source chunks.
5. Rate limits key on the real client identity when deployed behind trusted proxy layers.
6. Production boot/config/infra fail closed or require explicit secure overrides.

## Backend plan (if applicable)
- API changes:
  - Auth response contract update for browser flow.
  - Potential transitional compatibility mechanism for legacy clients.
- Schema changes:
  - None expected for auth.
  - Optional migration only if processing/state model requires additional timestamp fields.
- Background jobs / realtime events:
  - Document processing transaction and retry semantics updated.
- Guardrails (authz, rate limits, compat, pagination):
  - Atomic refresh rotation.
  - Proxy-aware rate-limit identity derivation.
  - Startup validation for unsafe production defaults.

## Frontend plan
- State model:
  - Consume reduced auth payload without access/refresh token fields.
- UI components touched:
  - Auth/API client types and login/refresh handling only.
- Edge cases:
  - Session refresh and logout behavior remain stable.

## Files expected
- Backend:
  - `backend/app/api/auth.py`
  - `backend/app/core/security.py`
  - `backend/app/services/document_service.py`
  - `backend/app/services/embedding_service.py`
  - `backend/app/utils/rate_limit.py`
  - `backend/app/config.py`
  - tests under `backend/tests/`
- Frontend:
  - `frontend/lib/api.ts`
  - `frontend/lib/api.types.ts`
- Infra:
  - `infra/terraform/variables.tf`
  - `infra/terraform/main.tf`
  - `infra/terraform/README.md` (if behavior/inputs change)
- Docs:
  - `plans/codebase-audit-2026-02-28.md` (cross-link issue IDs)
  - `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`, `TESTPLAN.md` as needed

## Tests
- Backend:
  - Auth refresh concurrency and rotation correctness tests.
  - Processing failure/retry chunk integrity tests.
  - Embedding batch contract tests.
  - Rate limit identity derivation tests where practical.
- Frontend:
  - Type-level contract alignment for auth payload.
- Regression:
  - Existing auth/document/query flows remain green.

## Decision locks (must be Locked before backend-coupled implementation)
- [ ] Locked: Legacy-client compatibility strategy for auth response body token removal.
- [ ] Locked: Refresh atomicity implementation choice (`FOR UPDATE` vs `DELETE ... RETURNING`).
- [ ] Locked: Infra hardening rollout strategy (breaking defaults vs staged migration).

## ADR links (if lasting architecture/security/perf decision)
- ADR: TBD (likely required for auth response contract + infra hardening policy)

## Acceptance criteria
- [ ] Child tasks created for each scoped P0/P1 fix area.
- [ ] Each task has explicit acceptance criteria and verification commands.
- [ ] Decision locks resolved before backend/infra implementation begins.

## Verification
```bash
make backend-verify
make frontend-verify
cd backend && alembic check
```

## Notes
- Source audit: `plans/codebase-audit-2026-02-28.md`
- Related planning doc: `plans/backend-fixes-spec.md`
- External review validation: P0/P1 findings were independently re-verified as 7/7 accurate; implementation clarifications captured in Tasks #21, #22, and #23.
