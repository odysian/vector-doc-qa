## Summary
Define and implement a production-grade CI/CD pipeline and Terraform-managed infrastructure (excluding Cloud SQL) for Quaero.

This spec covers:
- test-on-push/PR CI checks
- automatic backend deploy on `main` pushes after CI passes
- Terraform management for GCP resources except database
- import-first IaC flow for already-created resources

## Value / User Impact
- Faster feedback via automated CI checks on every push/PR
- Safer releases with test-gated automatic deploys
- Repeatable, reviewable infrastructure changes with Terraform
- Stronger portfolio narrative for CI/CD + IaC practices

## Scope
**In scope:**
- GitHub Actions test workflow(s) for backend and optional frontend
- Deploy workflow trigger updates (push to `main`, post-test gate)
- Manual dispatch fallback deploy path
- Terraform for non-DB resources
- State/import/runbook documentation

**Out of scope:**
- Cloud SQL provisioning/import into Terraform
- Migrating runtime from VM to Cloud Run/GKE
- Replacing current deployment strategy (single-slot rolling deploy)

## How it works (expected behavior)
1. Every push/PR runs CI checks.
2. Pushes to `main` that pass checks trigger automatic deploy.
3. Deploy continues to use VM SSH + `ops/deploy_backend.sh` rollback contract.
4. Terraform owns VM/network/storage/IAM resources via import-first workflow.

## Backend plan (if applicable)
- API changes: none.
- Schema changes: none.
- Background jobs: unchanged.
- Guardrails:
  - Deploy from `main` only
  - CI required before deploy
  - `workflow_dispatch` preserved for emergency manual deploys

## Frontend plan
- No feature changes.
- Optional: include frontend CI checks on push/PR (`make frontend-verify`) if desired.

## Files expected
- `.github/workflows/backend-test.yml` (new)
- `.github/workflows/backend-deploy.yml` (update)
- Optional `.github/workflows/frontend-test.yml` or unified verify workflow
- `infra/terraform/*` (new)
- `docs/GCP_RUNBOOK.md` updates for CI/CD + Terraform operations
- `GCP-plan.md` and/or `docs/ARCHITECTURE.md` updates as needed

## Tests
- CI workflow validation via test branch + PR + merge to main.
- Deploy validation on `main` push.
- Terraform `fmt`, `validate`, `plan` checks.

## Decision locks (must be Locked before backend-coupled implementation)
- [x] Locked: automatic deploys only from `main` after tests pass
- [x] Locked: keep `workflow_dispatch` for manual fallback
- [x] Locked: Terraform scope excludes Cloud SQL for now
- [x] Locked: import existing infra instead of recreate

## ADR links (if lasting architecture/security/perf decision)
- ADR: pending (CI/CD + IaC governance decision)

## Acceptance criteria
- [ ] CI runs on every push/PR and reports status checks.
- [ ] Deploy runs automatically on `main` push only after test job success.
- [ ] Terraform config exists for non-DB infra and imports current resources.
- [ ] Runbook documents CI/CD and Terraform workflows (plan/apply/destroy policy).

## Verification
```bash
# Backend
make backend-verify

# Frontend
make frontend-verify

# Terraform
terraform fmt -check
terraform validate
terraform plan
```

## Child tasks
- Task A: CI/CD hardening and automatic deploy on main
- Task B: Terraform IaC for non-DB GCP resources (import-first)

## Linked tasks
- #11 Task: CI checks on push/PR and main-only auto deploy
- #12 Task: Terraform IaC for GCP infra (excluding Cloud SQL)
