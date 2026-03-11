# GCP VM Rebuild + SSH Standardization Plan

**Date:** 2026-02-28  
**Owner:** odys  
**Related issue:** [#12](https://github.com/odysian/vector-doc-qa/issues/12)

---

## Goal

Rebuild the backend VM from a clean state, standardize SSH access around one Linux user (`odys`), and eliminate key drift by provisioning access via Terraform.

This plan intentionally replaces the current VM instance due to accumulated manual SSH/config drift.

---

## Decision Update for Issue #12

Current lock in #12 says import-first/no recreate.  
This plan changes that for VM access stability:

- Keep Cloud SQL out of Terraform scope.
- Recreate **VM-only** as a controlled reset.
- Continue Terraform ownership for non-DB infra.

Update #12 lock text to:

- [x] Locked: Cloud SQL excluded from Terraform scope
- [x] Locked: VM recreate allowed once for SSH/deploy drift reset
- [x] Locked: manual approval required before production apply/destroy

---

## Target End State

- One permanent VM user: `odys`
- Two SSH keypairs mapped to the same VM user:
  - personal key (local terminal only)
  - GitHub deploy key (GitHub secret only)
- VM/network/storage/IAM managed in `infra/terraform/`
- Ops Agent install/config/version pin managed in Terraform bootstrap (no manual SSH-only setup)
- GitHub Actions deploy uses `odys@<static_ip>` with `IdentitiesOnly=yes`
- No manual key edits via GCP console for routine operations

---

## Phase 0: Grant Codex Access to GCP Commands (Terminal Auth)

Run these in the repo terminal so this session can execute `gcloud`/Terraform commands:

```bash
# 1) Login interactively (browser flow)
gcloud auth login

# 2) Set project
gcloud config set project portfolio-488721

# 3) (Recommended) Application Default Credentials for Terraform/provider tooling
gcloud auth application-default login

# 4) Verify active account and project
gcloud auth list
gcloud config list --format='text(core.account,core.project)'
```

Quick verification:

```bash
gcloud compute instances list
gcloud compute addresses list
```

Notes:

- Do not use long-lived JSON service-account keys unless required.
- User OAuth auth is sufficient for interactive infra work.

---

## Phase 1: Pre-Reset Safety Snapshot

Capture current state before destruction:

```bash
gcloud compute instances describe quaero-backend --zone us-east1-b > /tmp/quaero-backend-before.txt
gcloud compute addresses list --filter='name=quaero-backend-ip'
gcloud compute firewall-rules list --filter='name~quaero'
```

Optional runtime backup on VM (if needed):

- `/opt/quaero/env/backend.env`
- `/opt/quaero/deploy/last_successful_image`
- NGINX site config and cert metadata

---

## Phase 2: Generate Fresh SSH Keys (Local)

Create two new keys:

```bash
# Personal operator key
ssh-keygen -t ed25519 -f ~/.ssh/quaero_odys_personal -C odys-personal -N ""

# GitHub Actions deploy key
ssh-keygen -t ed25519 -f ~/.ssh/quaero_odys_deploy -C gha-deploy -N ""
```

Collect public keys:

```bash
cat ~/.ssh/quaero_odys_personal.pub
cat ~/.ssh/quaero_odys_deploy.pub
```

---

## Phase 3: Terraform Implementation (Non-DB Infra)

Create:

- `infra/terraform/providers.tf`
- `infra/terraform/variables.tf`
- `infra/terraform/main.tf`
- `infra/terraform/outputs.tf`
- `infra/terraform/envs/prod.tfvars`
- `infra/terraform/README.md`

Resources in scope:

- Compute instance (backend VM)
- Static external IP
- Firewall rules (`80`, `443`, constrained `22`)
- Service account for VM runtime
- IAM bindings needed for GCS access
- GCS bucket + IAM

VM metadata must include both keys for user `odys`:

```text
ssh-keys = <<EOT
odys:ssh-ed25519 AAAA... odys-personal
odys:ssh-ed25519 BBBB... gha-deploy
EOT
```

Also include startup script to initialize:

- `/opt/quaero/deploy`
- `/opt/quaero/env`
- `/opt/quaero/logs`
- Docker prerequisites and permissions for `odys`
- NGINX reverse proxy for `api.quaero.odysian.dev`
- Certbot TLS bootstrap + renewal timer
- Ops Agent install/version reconciliation + config render at `/etc/google-cloud-ops-agent/config.yaml`
- `backend.env` stub file with placeholders for secrets

---

## Phase 4: Apply Rebuild (Controlled)

From repo root:

```bash
cd infra/terraform
terraform init
terraform fmt -check
terraform validate
terraform plan -var-file=envs/prod.tfvars
```

Review plan manually, then apply:

```bash
terraform apply -var-file=envs/prod.tfvars
```

If old VM exists outside state and must be replaced:

- destroy old VM explicitly (only after snapshot)
- apply clean VM from Terraform

---

## Phase 5: Post-Provision SSH Validation

Test personal key:

```bash
ssh -i ~/.ssh/quaero_odys_personal -o IdentitiesOnly=yes -o StrictHostKeyChecking=no odys@<VM_IP> "whoami && hostname"
```

Test deploy key equivalence:

```bash
ssh -i ~/.ssh/quaero_odys_deploy -o IdentitiesOnly=yes -o StrictHostKeyChecking=no odys@<VM_IP> "echo deploy-key-ok"
```

If both pass, SSH identity is correctly standardized.

---

## Phase 6: GitHub Actions Secret Alignment

Set repository secrets:

- `GCP_VM_USER=odys`
- `GCP_VM_HOST=<VM_IP>`
- `GCP_VM_SSH_KEY=<contents of ~/.ssh/quaero_odys_deploy>`

Get deploy private key:

```bash
cat ~/.ssh/quaero_odys_deploy
```

Do not store personal private key in GitHub.

---

## Phase 7: Workflow Hardening

Patch `.github/workflows/backend-deploy.yml` SSH/SCP commands to include:

```text
-o IdentitiesOnly=yes
```

This ensures Actions uses only `vm_key.pem` and avoids agent/default-key interference.

---

## Phase 8: Deploy + Smoke Verification

1. Trigger backend deploy workflow (`workflow_dispatch`).
2. Validate:
   - container running (`quaero-backend`)
   - VM health: `curl -f http://127.0.0.1:8000/health`
   - public health: `curl -f https://api.quaero.odysian.dev/health`
   - Ops Agent health: `systemctl status google-cloud-ops-agent --no-pager`
3. Run app smoke flow:
   - login
   - upload/process/query/delete document

---

## Rollback / Recovery

If rebuild fails:

1. Re-apply previous known-good infra settings.
2. Reuse static IP and DNS mapping.
3. Restore env/deploy script from backup snapshot.
4. Re-run deploy with last successful image.

---

## Execution Log (Fill During Run)

- [x] Phase 0 complete (gcloud auth/project configured)
- [x] Phase 1 complete (snapshot captured)
- [x] Phase 2 complete (2 new keys created)
- [x] Phase 3 complete (Terraform files created)
- [x] Phase 4 complete (VM rebuilt)
- [x] Phase 5 complete (SSH verified with both keys)
- [x] Phase 6 complete (GitHub secrets updated)
- [x] Phase 7 complete (workflow hardened with IdentitiesOnly)
- [x] Phase 8 complete (deploy + smoke checks passed)

Evidence notes:

- gcloud auth/account: `colosimocj3@gmail.com`
- gcloud project: `portfolio-488721`
- Current VM: `quaero-backend` (`us-east1-b`, `e2-micro`, external IP `34.26.82.138`)
- Snapshot files: `/tmp/quaero-snapshot/instance-before.txt`, `/tmp/quaero-snapshot/address-before.txt`, `/tmp/quaero-snapshot/firewall-before.txt`
- Terraform validate: success (`infra/terraform`)
- Terraform imports completed: static IP, HTTP firewall, HTTPS firewall, VM instance, bucket
- Terraform plan summary (post-import): `6 to add, 0 to change, 1 to destroy`
- New VM IP: `34.26.82.138` (static IP preserved)
- GitHub deploy run URL: workflow run completed successfully (user-verified)
- Health check outputs: VM and public health checks green (user-verified)
