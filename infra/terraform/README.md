# Terraform: GCP Non-DB Infrastructure

This directory manages Quaero's GCP infrastructure excluding Cloud SQL:

- backend VM (`quaero-backend`)
- static external IP (`quaero-backend-ip`)
- firewall rules (`80`, `443`, `22`)
- VM service account and IAM bindings
- GCS bucket for documents (`quaero-pdf-storage`)

VM bootstrap via startup script also configures:

- Docker engine
- NGINX reverse proxy (`server_name = api.quaero.odysian.dev`)
- Certbot TLS issuance/renewal (when enabled)
- `/opt/quaero/env/backend.env` stub with placeholders
- `/opt/quaero/{deploy,env,logs}` directories

## Prerequisites

```bash
gcloud auth login
gcloud config set project portfolio-488721
gcloud auth application-default login
```

## Environment tfvars

`envs/prod.tfvars` is local-only and gitignored. Start from the committed
template:

```bash
cd infra/terraform
cp envs/prod.tfvars.example envs/prod.tfvars
```

## Validate

```bash
cd infra/terraform
terraform init
terraform fmt -check
terraform validate
terraform plan -var-file=envs/prod.tfvars
```

## Security Defaults and Rollout

- `ssh_source_ranges` is now explicit and must be provided.
- `0.0.0.0/0` is blocked by default. Use
  `allow_insecure_ssh_from_anywhere=true` only as a temporary rollout exception.
- Shielded VM secure boot is enabled by default (`enable_secure_boot=true`).
- VM service account defaults to least privilege for current runtime:
  - Bucket IAM: `roles/storage.objectUser`
  - OAuth scope: `https://www.googleapis.com/auth/devstorage.read_write`

### Existing Environment Rollout

1. Keep current SSH access temporarily by setting both:
   - `ssh_source_ranges = ["0.0.0.0/0"]`
   - `allow_insecure_ssh_from_anywhere = true`
2. Run plan/apply and confirm infra health.
3. Replace `ssh_source_ranges` with fixed admin CIDR(s) (for example `x.x.x.x/32`).
4. Set `allow_insecure_ssh_from_anywhere = false`.
5. Run plan/apply again to remove world-open SSH.

### Rollback Notes

- If SSH access is lost, temporarily re-enable:
  - `ssh_source_ranges = ["0.0.0.0/0"]`
  - `allow_insecure_ssh_from_anywhere = true`
  then apply and re-lock after recovery.
- If secure boot causes boot/runtime issues, set `enable_secure_boot = false`,
  apply, investigate startup logs, and re-enable once fixed.
- If workload expands beyond GCS object access, add only required IAM role(s)
  and scope(s) instead of restoring broad `cloud-platform`.

## Import Existing Resources (If Already Present)

Run these before `apply` when resources already exist in production:

```bash
cd infra/terraform

terraform import -var-file=envs/prod.tfvars google_compute_address.backend \
  "projects/portfolio-488721/regions/us-east1/addresses/quaero-backend-ip"

terraform import -var-file=envs/prod.tfvars google_compute_firewall.allow_http \
  "projects/portfolio-488721/global/firewalls/quaero-allow-http"

terraform import -var-file=envs/prod.tfvars google_compute_firewall.allow_https \
  "projects/portfolio-488721/global/firewalls/quaero-allow-https"

terraform import -var-file=envs/prod.tfvars google_compute_instance.backend \
  "projects/portfolio-488721/zones/us-east1-b/instances/quaero-backend"

terraform import -var-file=envs/prod.tfvars google_storage_bucket.documents \
  "quaero-pdf-storage"
```

Notes:

- `google_service_account.backend_vm` and `google_compute_firewall.allow_ssh` may be new resources and not require import.
- If import shows drift that should be accepted, update configuration before apply.

## Controlled VM Recreate

To recreate VM while keeping Terraform ownership:

```bash
cd infra/terraform
terraform apply -var-file=envs/prod.tfvars -replace=google_compute_instance.backend
```

## Apply

```bash
cd infra/terraform
terraform apply -var-file=envs/prod.tfvars
```

## After Apply (Required Before First Deploy)

1. SSH to VM and fill real secrets in `/opt/quaero/env/backend.env` (replace placeholders).
   - For list env vars (for example `TRUSTED_PROXY_IPS`), use JSON array syntax
     without outer shell quotes since deployment uses Docker `--env-file`.
   - Example: `TRUSTED_PROXY_IPS=["172.17.0.1/32"]` (correct),
     `TRUSTED_PROXY_IPS='["172.17.0.1/32"]'` (incorrect).
2. Confirm NGINX/TLS status:

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
sudo systemctl status certbot.timer --no-pager
```

3. Trigger GitHub Actions `Deploy Backend`.

## Outputs

```bash
cd infra/terraform
terraform output
```
