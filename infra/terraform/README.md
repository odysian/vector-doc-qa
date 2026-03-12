# Terraform: GCP Non-DB Infrastructure

This directory manages Quaero's GCP infrastructure excluding Cloud SQL:

- backend VM (`quaero-backend`)
- static external IP (`quaero-backend-ip`)
- firewall rules (`80`, `443`, `22`)
- VM service account and IAM bindings
- GitHub OIDC trust and golden-image builder service account
- GCS bucket for documents (`quaero-pdf-storage`)

VM bootstrap via startup script also configures:

- Docker engine
- NGINX reverse proxy (`server_name = api.quaero.odysian.dev`)
- Certbot TLS issuance/renewal (when enabled)
- Google Cloud Ops Agent install/config (when enabled)
- `/opt/quaero/env/backend.env` directory/path (file is provisioned by deploy workflow secret)
- `/opt/quaero/{deploy,env,logs}` directories

## Prerequisites

```bash
gcloud auth login
gcloud config set project portfolio-488721
gcloud auth application-default login
```

## Environment tfvars

Start from the committed template:

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
- Include `35.235.240.0/20` in `ssh_source_ranges` if you want IAP/Console SSH as a backup path.
- `0.0.0.0/0` is blocked by default. Use
  `allow_insecure_ssh_from_anywhere=true` only as a temporary rollout exception.
- Shielded VM secure boot is enabled by default (`enable_secure_boot=true`).
- VM service account defaults to least privilege for current runtime:
  - Bucket IAM: `roles/storage.objectUser`
  - Project IAM (Ops Agent writes): `roles/logging.logWriter`, `roles/monitoring.metricWriter`
  - OAuth scopes (additive): `devstorage.read_write`, `logging.write`, `monitoring.write`
- Golden-image pipeline auth is OIDC-only (no static cloud key):
  - Workload Identity Pool + Provider trust `token.actions.githubusercontent.com`
  - Repository scope is locked to `github_repository` (`owner/repo`) via provider condition
  - Builder service account has only image-build roles:
    - `roles/compute.instanceAdmin.v1`
    - `roles/compute.imageAdmin`
    - `roles/compute.networkUser`
    - `roles/iam.serviceAccountUser` only on the project default Compute SA

## Golden Image Pipeline

- Workflow: `.github/workflows/golden-image-build.yml`
- Trigger policy: weekly schedule (`cron`) + manual `workflow_dispatch` (emergency only)
- Naming pattern: `quaero-backend-golden-YYYYMMDD-HHMM-<sha7>`
- Family: `golden_image_family` (default `quaero-backend-golden`)
- Provenance labels on each image:
  - `quaero_role=backend-golden`
  - `quaero_repo=<owner-repo>`
  - `quaero_commit=<sha7>`
  - `quaero_build_time=<UTC yyyymmddhhmm>`
  - `quaero_run_id=<github run id>`
- Retention policy: keep latest `golden_image_retention_count` images (default `5`) and delete older images in the family.

### Required GitHub Repository Variables

Set these before running golden-image workflow:

- `GCP_PROJECT_ID`: target GCP project ID.
- `GCP_GOLDEN_IMAGE_WIF_PROVIDER`: output `github_actions_workload_identity_provider`.
- `GCP_GOLDEN_IMAGE_SERVICE_ACCOUNT`: output `golden_image_builder_service_account_email`.
- Optional: `GCP_GOLDEN_IMAGE_BUILD_ZONE` (default `us-east1-b`).
- Optional: `GCP_GOLDEN_IMAGE_FAMILY` (default `quaero-backend-golden`).
- Optional: `GCP_GOLDEN_IMAGE_RETENTION_COUNT` (default `5`).

## Ops Agent Controls

Set these in `envs/prod.tfvars`:

- `enable_ops_agent` (bool): enables/disables Ops Agent bootstrap path.
- `ops_agent_version` (string): required pinned version; use upstream `X.Y.Z` (recommended) or exact apt package version. Empty/unset or `latest` fails validation.
- `ops_agent_collect_docker_logs` (bool): when false, Docker log receiver/pipeline is omitted.
- `ops_agent_collect_host_metrics` (bool): when false, hostmetrics receiver/pipeline is omitted.

Behavior details:

- Startup script reconciles Ops Agent install/version independently from `/opt/quaero/.bootstrap_v2_done`.
- Version reconciliation resolves upstream pins (for example `2.51.0`) to matching distro-qualified apt builds (for example `2.51.0~debian12`) when needed.
- Config is rendered from `scripts/ops-agent-config.yaml.tftpl` and written atomically to `/etc/google-cloud-ops-agent/config.yaml`.
- Agent restart is gated on config hash drift; no restart occurs when config is unchanged.
- `enable_ops_agent=false` is safe even if package/service is absent.
- Docker log parsing includes nested JSON parse from container `log` content; if logs are mixed-format, envelope fields still ingest and non-JSON message lines remain as plain text.

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
- If Ops Agent rollout causes observability noise or instability, set
  `enable_ops_agent = false` and apply to stop/disable the service without
  requiring manual SSH edits.

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

terraform import -var-file=envs/prod.tfvars google_project_iam_member.backend_vm_log_writer \
  "portfolio-488721 roles/logging.logWriter serviceAccount:quaero-backend-sa@portfolio-488721.iam.gserviceaccount.com"

terraform import -var-file=envs/prod.tfvars google_project_iam_member.backend_vm_metric_writer \
  "portfolio-488721 roles/monitoring.metricWriter serviceAccount:quaero-backend-sa@portfolio-488721.iam.gserviceaccount.com"
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

1. Set GitHub repo secret `BACKEND_ENV_B64` from your production env file contents.
   - Generate a base64 payload from your local env file:

```bash
base64 -w 0 /path/to/backend.env
```

   - Add it as repository secret `BACKEND_ENV_B64`.
2. Confirm NGINX/TLS status:

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
sudo systemctl status certbot.timer --no-pager
```

3. Confirm Ops Agent status (when enabled):

```bash
sudo systemctl status google-cloud-ops-agent --no-pager
sudo cat /etc/google-cloud-ops-agent/config.yaml
```

4. Trigger GitHub Actions `Deploy Backend` (it now uploads `/opt/quaero/env/backend.env` from `BACKEND_ENV_B64` on every deploy).

## Outputs

```bash
cd infra/terraform
terraform output
```
