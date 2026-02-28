## Goal
Set up CI checks on every push/PR and automatic backend deploy on `main` pushes after CI success.

## Scope
**In:**
- Add backend test workflow triggered by `push` + `pull_request`
- Optionally add frontend checks (or include in unified verify workflow)
- Update deploy workflow triggers to `push` on `main` and `workflow_dispatch`
- Ensure deploy job depends on successful test job(s)
- Document branch protection requirements

**Out:**
- Terraform changes
- Cloud SQL provisioning

## Implementation notes
Current state:
- `backend-deploy.yml` exists and works on `workflow_dispatch`.
- No test workflow currently exists in this repo.

Target state:
- `backend-test.yml` validates backend on every push/PR.
- Deploy runs automatically for `main` pushes.
- `workflow_dispatch` remains available.

## Decision locks (backend-coupled only)
- [x] Locked: deploy from `main` only
- [x] Locked: deploy requires prior test success
- [x] Locked: manual dispatch retained

## Acceptance criteria
- [ ] CI checks run for PRs and direct pushes.
- [ ] Deploy triggers on `main` push and succeeds on healthy commit.
- [ ] Failing CI blocks deploy on `main` push.
- [ ] Workflow docs/runbook updated.

## Verification
```bash
# Trigger paths to validate:
# 1) PR opens -> CI runs
# 2) merge to main -> CI then deploy
# 3) manual workflow_dispatch still deploys
```

## PR checklist
- [ ] PR references this issue (`Closes #...`)
- [ ] Docs updated if needed
- [ ] Validation evidence attached (workflow links)
