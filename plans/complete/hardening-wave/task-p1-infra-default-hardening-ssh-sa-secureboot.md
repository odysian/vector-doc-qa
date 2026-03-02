## Goal
Harden Terraform defaults to reduce attack surface and privilege blast radius in production infrastructure.
Default: this Task should represent the entire feature end-to-end unless split criteria apply.

## Scope
**In:**
- Remove permissive SSH default CIDR (`0.0.0.0/0`) and require explicit restricted ranges.
- Revisit/limit VM service account scope/roles toward least privilege.
- Enable secure boot by default unless explicitly and documentedly disabled.
- Update infra docs with migration notes and rollback guidance.

**Out:**
- Full network segmentation redesign.
- Unrelated Terraform module refactoring.

## Implementation notes
- Parent Spec: #19
- Treat any breaking default changes as controlled rollout with clear operator instructions.

## Decision locks (backend-coupled only)
- [ ] Locked: Backward-compatible rollout path for existing environments.
- [ ] Locked: Final least-privilege role/scope set required for current VM duties.

## Acceptance criteria
- [ ] Terraform no longer defaults SSH ingress to world-open CIDR.
- [ ] VM service account permissions/scopes are reduced to required minimum.
- [ ] Secure boot default is enabled (or exception is explicitly documented and approved).
- [ ] Terraform/docs verification steps are updated and reproducible.

## Verification
```bash
cd infra/terraform
terraform init
terraform validate
terraform plan -var-file=envs/prod.tfvars
```

## PR checklist
- [ ] PR references this issue (`Closes #...`)
- [ ] Docs updated if needed (`docs/ARCHITECTURE.md`, `docs/PATTERNS.md`, `docs/REVIEW_CHECKLIST.md`, `docs/ISSUES_WORKFLOW.md`, `TESTPLAN.md`, `docs/adr/`)
- [ ] Tests added/updated where needed
