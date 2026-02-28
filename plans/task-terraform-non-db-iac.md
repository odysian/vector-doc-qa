## Goal
Create Terraform IaC for GCP resources excluding Cloud SQL, and import existing production resources into state.

## Scope
**In:**
- Terraform project structure under `infra/terraform/`
- Providers and variables
- Resources (non-DB):
  - Compute static IP
  - Compute VM instance
  - Firewall rules (80/443 and optionally SSH)
  - Service account + IAM bindings needed for app/storage
  - Cloud Storage bucket + IAM (for document objects and/or TF state if chosen)
- Import scripts/commands for existing infra
- Plan/apply/destroy runbook

**Out:**
- Cloud SQL Terraform management/import
- Re-platforming runtime from VM

## Implementation notes
Approach:
1. Create Terraform config that matches existing infra.
2. Use `terraform import` for existing resources.
3. Run `terraform plan` and reduce drift to expected level.
4. Document destroy safety guardrails (never destroy prod blindly).

Recommended modules/files:
- `infra/terraform/main.tf`
- `infra/terraform/variables.tf`
- `infra/terraform/outputs.tf`
- `infra/terraform/providers.tf`
- `infra/terraform/envs/prod.tfvars`
- `infra/terraform/README.md`

## Decision locks (backend-coupled only)
- [x] Locked: Cloud SQL excluded from Terraform scope
- [x] Locked: import existing resources first (no recreate)
- [x] Locked: keep manual approval before `apply` in production

## Acceptance criteria
- [ ] Terraform config covers all non-DB production resources.
- [ ] Existing resources imported into state successfully.
- [ ] `terraform plan` is reviewed and explainable.
- [ ] Runbook includes plan/apply/destroy and recovery notes.

## Verification
```bash
cd infra/terraform
terraform init
terraform fmt -check
terraform validate
terraform plan -var-file=envs/prod.tfvars
```

## PR checklist
- [ ] PR references this issue (`Closes #...`)
- [ ] Import commands documented (not destructive)
- [ ] Docs/runbook updated
