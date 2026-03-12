# GCP Deployment Runbook (Quaero)

This runbook is the operational reference for Quaero backend on GCP.

Use this for:

- standard deploys
- rollback
- post-deploy validation
- common production debugging

The implementation plan lives in `GCP-plan.md`. This runbook is command-first and incident-focused.
For full VM reprovision/reset steps, use `docs/GCP_VM_REBUILD_TERRAFORM_PLAN.md`.

---

## 1. Ownership Split

## Codex-owned (repo changes)

- `backend/Dockerfile`
- `backend/.dockerignore`
- `.github/workflows/backend-test.yml`
- `.github/workflows/backend-deploy.yml`
- `ops/deploy_backend.sh`
- docs updates in this runbook

## User-owned (manual infra actions)

- GCP VM, static IP, firewall
- DNS (`api.quaero.odysian.dev`)
- GitHub secrets
- Vercel `NEXT_PUBLIC_API_URL` update
- Cloud Storage bucket/IAM setup

Terraform startup bootstrap now handles Docker + NGINX + Certbot + env file stub creation + Ops Agent install/config on VM rebuild.

---

## 2. Required Secrets and Files

## GitHub repository secrets

- `GCP_VM_HOST`
- `GCP_VM_USER`
- `GCP_VM_SSH_KEY`
- `GHCR_USERNAME`
- `GHCR_TOKEN`
- `BACKEND_ENV_B64` (base64-encoded contents of production `backend.env`)

## Backend env source of truth

Canonical source: GitHub secret `BACKEND_ENV_B64`.
Deploy workflow writes it to VM path `/opt/quaero/env/backend.env` on every deploy.

Required values:

```bash
DATABASE_URL=postgresql://quaero_app:<password>@<cloud-sql-ip>:5432/postgres?options=-c%20search_path=quaero,public
APP_ENV=production
SECRET_KEY=<strong-random-secret>
OPENAI_API_KEY=<...>
ANTHROPIC_API_KEY=<...>
REDIS_URL=<upstash-redis-url>
FRONTEND_URL=https://quaero.odysian.dev
PORT=8000
```

For list-type settings in this file (for example `TRUSTED_PROXY_IPS`,
`WHITELISTED_IPS`), use raw JSON arrays with no outer shell quotes because
deploys use Docker `--env-file`:

```bash
TRUSTED_PROXY_IPS=["172.17.0.1/32"]
```

Do **not** write:

```bash
TRUSTED_PROXY_IPS='["172.17.0.1/32"]'
```

Set/update secret from your local env file:

```bash
base64 -w 0 /path/to/backend.env | gh secret set BACKEND_ENV_B64
```

Cloud SQL role grants for `quaero_app` (run in Cloud SQL Query Editor as admin):

```sql
GRANT CONNECT, CREATE ON DATABASE postgres TO quaero_app;
GRANT USAGE, CREATE ON SCHEMA quaero TO quaero_app;
GRANT USAGE ON SCHEMA public TO quaero_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA quaero TO quaero_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA quaero TO quaero_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA quaero
  GRANT ALL PRIVILEGES ON TABLES TO quaero_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA quaero
  GRANT ALL PRIVILEGES ON SEQUENCES TO quaero_app;
```

---

## 3. Deployment Flow (Normal)

1. CI validation runs on:
   - every `pull_request` (`Backend CI`)
   - direct `push` to non-`main` branches (`Backend CI`)
2. Production deploy runs on:
   - `push` to `main` (`Deploy Backend`)
   - manual `workflow_dispatch` from `main` only (`Deploy Backend`)
3. `Deploy Backend` runs `backend-tests` first. If tests fail, deploy stops.
4. If tests pass, CI builds and pushes image to GHCR.
5. CI renders `backend.env` from `BACKEND_ENV_B64` and uploads it to VM.
6. CI uploads `ops/deploy_backend.sh` to VM.
7. CI executes deploy script on VM:
   - pulls image
   - runs migrations
   - restarts container
   - health-checks
   - rolls back on failure

Expected running container name:

- `quaero-backend`

---

## 4. Branch Protection (Required)

Protect `main` and require status check:

- `Backend CI / backend-verify`

This ensures PR merges are blocked until backend checks pass. Deploy still runs its own `backend-tests` gate on `main` pushes for fail-closed production safety.

---

## 5. Manual Commands

## Check running container

```bash
docker ps --filter "name=quaero-backend"
docker logs quaero-backend --tail 200
```

## Check health

From VM:

```bash
curl -f http://127.0.0.1:8000/health
```

Externally:

```bash
curl -f https://api.quaero.odysian.dev/health
```

## Run deploy script manually on VM

```bash
GHCR_USERNAME="<ghcr-user>" \
GHCR_TOKEN="<ghcr-token>" \
/opt/quaero/deploy/deploy_backend.sh "ghcr.io/<owner>/<repo>/quaero-backend:sha-<tag>"
```

## Force rollback manually

```bash
LAST_GOOD="$(cat /opt/quaero/deploy/last_successful_image)"
GHCR_USERNAME="<ghcr-user>" \
GHCR_TOKEN="<ghcr-token>" \
/opt/quaero/deploy/deploy_backend.sh "$LAST_GOOD"
```

---

## 6. Demo Readiness Checklist + Smoke Script

Run this flow before live demos. It is designed for staging/prod safety:

- no upload/process/delete endpoints are called
- only auth + read paths are exercised, plus query endpoints (which append chat history rows)

### Required environment variables

```bash
export API_BASE_URL="https://api.quaero.odysian.dev"
export DEMO_USERNAME="<demo-username>"
export DEMO_PASSWORD="<demo-password>"
```

Optional:

```bash
export SMOKE_DOCUMENT_ID="<completed-document-id>"  # if omitted, auto-picks first completed doc
export SMOKE_QUERY="What is the main topic of this document?"
export STREAM_SMOKE_QUERY="Give a concise one-sentence summary with one source citation."
```

### One-command smoke run

```bash
bash scripts/demo_smoke.sh
```

The script validates these endpoints/behaviors with step-level pass/fail output:

1. `GET /health` is healthy.
2. Auth flow:
   - `POST /api/auth/login`
   - `GET /api/auth/me`
   - `POST /api/auth/refresh`
3. Document readiness:
   - `GET /api/documents/`
   - `GET /api/documents/{id}/status` is `completed`
4. Query readiness:
   - `POST /api/documents/{id}/query` returns non-empty answer + sources
5. Stream readiness:
   - `POST /api/documents/{id}/query/stream` returns SSE with `sources`, `token`, `meta`, and `done` events
6. Citation prerequisites:
   - query sources include at least one `page_start`/`page_end`
7. PDF endpoint:
   - `GET /api/documents/{id}/file` returns `application/pdf`
   - response payload starts with `%PDF-`

Failures include the exact step and endpoint, and the script exits non-zero.

### Manual UI checklist (post-script)

1. Login in frontend with demo account.
2. Open the same document used by smoke script.
3. Ask a question and confirm token-by-token stream rendering in chat.
4. Click a citation source chip/card in the response.
5. Verify PDF panel jumps to the cited page and displays the relevant section.
6. Confirm the PDF viewer remains responsive on desktop and mobile viewport sizes.

---

## 7. NGINX and TLS Checks

## NGINX status and config test

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
```

## SSE proxy checks

```bash
# Confirm stream endpoint has anti-buffering directives
sudo nginx -T | grep -E "query/stream|proxy_buffering off|X-Accel-Buffering|gzip off|proxy_read_timeout"

# Apply config changes safely
sudo nginx -t && sudo systemctl reload nginx
```

## Certbot status

```bash
sudo systemctl status certbot.timer --no-pager
sudo certbot renew --dry-run
```

## Ops Agent status (Terraform-managed)

```bash
sudo systemctl status google-cloud-ops-agent --no-pager
sudo journalctl -u google-cloud-ops-agent -n 200 --no-pager
sudo cat /etc/google-cloud-ops-agent/config.yaml
```

Toggle notes:

- `enable_ops_agent=false` in Terraform cleanly disables collection and is safe when the package is absent.
- Docker receiver reads `/var/lib/docker/containers/*/*-json.log`; nested app JSON parsing is best-effort and mixed-format lines remain queryable as plain message text.

---

## 8. Common Failure Scenarios

## Deploy fails before container restart

Symptoms:

- migration step fails
- CI job exits before restart

Actions:

1. Inspect CI logs for migration error.
2. SSH to VM and run:
   - `docker run --rm --env-file /opt/quaero/env/backend.env <image> alembic upgrade head`
3. Fix root cause (DB connectivity, credentials, migration conflict).
4. Re-run workflow.

## Migration fails with `permission denied for database postgres`

Symptoms:

- deploy reaches `Running migrations`
- Alembic fails on `CREATE SCHEMA IF NOT EXISTS quaero`
- error contains `psycopg2.errors.InsufficientPrivilege`

Actions:

1. Ensure deploy is using `DATABASE_URL` with `quaero_app`.
2. Run the `quaero_app` grant block from section 2 (must include `CREATE ON DATABASE postgres`).
3. Re-run deploy.

## New container fails health check

Symptoms:

- CI deploy step reports failed health checks
- rollback attempted

Actions:

1. Check logs:
   - `docker logs quaero-backend --tail 300`
2. Verify env file values (`DATABASE_URL`, `REDIS_URL`, API keys).
3. Validate upstream dependencies:
   - DB reachable
   - Redis reachable
4. Confirm rollback image:
   - `cat /opt/quaero/deploy/last_successful_image`
5. Re-run deploy after fix.

## Frontend auth suddenly fails after cutover

Symptoms:

- login or mutating requests fail due to CORS/CSRF

Actions:

1. Verify `FRONTEND_URL` in `/opt/quaero/env/backend.env` exactly matches `https://quaero.odysian.dev`.
2. Confirm TLS is valid and API is served over HTTPS.
3. Check browser network tab for:
   - `Access-Control-Allow-Origin`
   - cookie presence on auth responses
4. Restart container after env fix.

## Worker appears down but API is up

Symptoms:

- uploads accepted but documents remain pending

Actions:

1. Check container logs for ARQ errors.
2. Confirm Redis URL and connectivity.
3. Verify `run-web-and-worker.sh` is startup command in running image.
4. Restart container and retest upload.

## Streaming answer arrives as one full block (no incremental tokens)

Symptoms:

- Frontend shows final answer all at once in production
- Local streaming works token-by-token
- `/query/stream` succeeds with `200` but cadence is lost

Actions:

1. Check NGINX stream-path directives are present:
   - `proxy_buffering off`
   - `proxy_cache off`
   - `gzip off`
   - `proxy_read_timeout 3600s`
   - `add_header X-Accel-Buffering "no" always`
2. Reload NGINX:
   - `sudo nginx -t && sudo systemctl reload nginx`
3. Re-run streaming query and inspect response headers in browser network tab:
   - `content-type: text/event-stream`
   - `x-accel-buffering: no`
4. If still buffered, capture:
   - `/var/log/nginx/error.log`
   - `/var/log/nginx/access.log`
   - browser request/response headers for `/api/documents/{id}/query/stream`

---

## 9. Observability Pointers

Prerequisite infra task: [Task #180](https://github.com/odysian/vector-doc-qa/issues/180) (Terraform-persistent Ops Agent bootstrap).

Minimum diagnostics during incidents:

1. Ops Agent health:
   - `sudo systemctl status google-cloud-ops-agent --no-pager`
   - `sudo journalctl -u google-cloud-ops-agent -n 200 --no-pager`
2. VM resource pressure:
   - `free -h`
   - `top`
3. Container lifecycle:
   - `docker ps -a --filter "name=quaero-backend"`
   - `docker inspect quaero-backend --format '{{.State.Restarting}} {{.State.ExitCode}}'`
4. App logs:
   - `docker logs quaero-backend --tail 500`
5. NGINX logs:
   - `/var/log/nginx/access.log`
   - `/var/log/nginx/error.log`

### Token Usage Dashboard Definitions

Create Cloud Logging charts (or a custom dashboard) backed by these filters:

1. `external.call_completed` volume by provider/model
   - `jsonPayload.event="external.call_completed"`
   - Group by `jsonPayload.provider`, `jsonPayload.model`
2. Embedding token trend
   - `jsonPayload.event="external.call_completed" AND jsonPayload.embedding_tokens:*`
   - Plot sum of `jsonPayload.embedding_tokens`
3. LLM token trend
   - `jsonPayload.event="query.completed" AND jsonPayload.llm_input_tokens:*`
   - Plot sum of `jsonPayload.llm_input_tokens` and `jsonPayload.llm_output_tokens`
4. External call failure rate
   - `jsonPayload.event="external.call_failed"`
   - Group by `jsonPayload.provider`, `jsonPayload.model`, `jsonPayload.error_class`

### Alert Definitions

Configure alerting policies from log-based metrics:

1. `external_call_failed_count` spike:
   - condition: failures > baseline for 5 minutes
   - labels: provider/model/error_class
2. Missing token usage on completed queries:
   - condition: `query.completed` logs with no `llm_input_tokens` for a sustained window after deploy
   - use as a canary for usage propagation regressions
3. Embedding token anomaly:
   - condition: large jump/drop in summed `embedding_tokens` vs trailing average

### Runtime Validation Checklist (Post-Deploy)

Run after each production deploy once traffic is live:

1. Confirm external call completion logs include provider/model/duration:
   ```bash
   gcloud logging read 'jsonPayload.event="external.call_completed"' --limit=20 --format=json
   ```
2. Confirm query completion logs include timing/retrieval/token top-level keys:
   ```bash
   gcloud logging read 'jsonPayload.event="query.completed"' --limit=20 --format=json
   ```
3. Confirm failure path emits `external.call_failed` with `error_class`.
4. Trigger one controlled query and verify:
   - `embedding_tokens` present when embedding usage is returned
   - `llm_input_tokens` / `llm_output_tokens` present when LLM usage is returned
5. Validate alert notification routing by forcing one non-prod test alert.

---

## 10. Golden Image Cutover + Rollback Evidence (Task #186)

Use this section for the production cutover from stock image path to golden image path.
Decision record: `docs/adr/008-vm-golden-image-cutover-and-tuple-rollback.md`.
This section is an execution log template. Do not close Task #186 until placeholder fields are replaced with concrete values/links.

Release tuple mapping:

- `image_version` -> Terraform variable `vm_image`
- `reconcile_release_id` -> Terraform variable `reconcile_release_id`
- Determinism pins (required for reproducible rollback):
  - `infra_commit_sha` -> exact repo commit used for Terraform apply
  - `reconcile_sha256` -> expected metadata hash from Terraform plan at that commit

### 10.0 Manual-first execution path (default)

Use terminal-driven Terraform as the default control plane for production rollout.

1. Gather pre-cutover records (section 10.1) and confirm target tuple/pins.
2. Checkout the exact `infra_commit_sha` for the target tuple.
3. Run plan/apply manually (section 10.2).
4. Run required post-cutover health gates (section 10.3).
5. For rollback, use the same tuple/pin discipline described in section 10.5.

High-overhead workflow-based cutover automation is retired from active process in this repo.
For optional web-based Terraform operations, use the minimal manual-dispatch workflow documented in section 10.6.

### 10.1 Pre-cutover record (required)

Record these before any production apply:

- UTC window: `<required>`
- Named owner signoff: `<required>`
- Baseline bootstrap time (minutes): `<required>`
- Previous rollback tuple (`vm_image`, `reconcile_release_id`): `<required>`
- Previous determinism pins (`infra_commit_sha`, `reconcile_sha256`): `<required>`
- Target rollout tuple (`vm_image`, `reconcile_release_id`): `<required>`
- Target determinism pins (`infra_commit_sha`, `reconcile_sha256`): `<required>`
- Pre-cutover snapshot/checkpoint ID: `<required>`
- Non-prod rollback rehearsal evidence link: `<required>`

Production pin rules:

- `vm_image` must be an exact image self-link (not an image family reference).
- Terraform apply must run from the exact `infra_commit_sha` recorded for that tuple.
- `reconcile_sha256` from Terraform plan must match the recorded value before apply.

Capture a checkpoint snapshot:

```bash
VM_DISK="$(gcloud compute instances describe quaero-backend --zone us-east1-b --format='value(disks[0].source.basename())')"
SNAPSHOT_ID="quaero-backend-pre-cutover-$(date -u +%Y%m%d-%H%M%S)"
gcloud compute disks snapshot "$VM_DISK" --zone us-east1-b --snapshot-names "$SNAPSHOT_ID"
echo "checkpoint snapshot: $SNAPSHOT_ID"
```

### 10.2 Cutover apply (default manual path)

Optional helper wrapper from repo root (legacy helper, not required):

```bash
make infra-cutover-prepare CUTOVER_TFVARS=envs/prod.tfvars
```

If `vm_image` is still a family reference and you want the helper to pin it automatically:

```bash
make infra-cutover-prepare CUTOVER_TFVARS=envs/prod.tfvars CUTOVER_PIN_FAMILY=true
```

1. Checkout the exact infra commit for the target tuple:

```bash
git checkout <infra_commit_sha>
```

2. Set rollout tuple in `infra/terraform/envs/prod.tfvars`:
   - `vm_image` -> exact promoted image self-link (for example `projects/<project>/global/images/<image-name>`)
   - `reconcile_release_id` -> approved reconcile artifact release
3. Confirm planned metadata hash matches recorded `reconcile_sha256`.
4. Run Terraform plan/apply in approved window:

```bash
cd infra/terraform
terraform plan -var-file=envs/prod.tfvars
terraform apply -var-file=envs/prod.tfvars
```

### 10.3 Post-cutover health gates (required)

Optional automation wrapper from repo root:

```bash
make infra-cutover-postcheck CUTOVER_TFVARS=envs/prod.tfvars
```

`/health` must pass 15 consecutive checks at 10-second interval:

```bash
for i in $(seq 1 15); do
  curl -fsS https://api.quaero.odysian.dev/health >/dev/null || { echo "health gate failed at check ${i}"; exit 1; }
  echo "health gate ${i}/15 passed"
  sleep 10
done
```

Ops Agent must stay healthy for 10 minutes with no restart loop:

```bash
sudo systemctl is-active --quiet google-cloud-ops-agent
before="$(sudo systemctl show google-cloud-ops-agent -p NRestarts --value)"
sleep 600
after="$(sudo systemctl show google-cloud-ops-agent -p NRestarts --value)"
test "$before" = "$after"
sudo systemctl status google-cloud-ops-agent --no-pager
```

### 10.4 Bootstrap target calculation (required)

Compute stricter threshold from issue contract (`<= 6 minutes` or `>= 40%` improvement, whichever is stricter):

```bash
BASELINE_MIN="<baseline-minutes>"
POST_MIN="<post-cutover-minutes>"
STRICT_TARGET_MIN="$(awk -v b="$BASELINE_MIN" 'BEGIN { t=b*0.6; if (t < 6) printf "%.2f", t; else printf "6.00" }')"
awk -v post="$POST_MIN" -v target="$STRICT_TARGET_MIN" 'BEGIN { if (post <= target) { print "target_met=true"; exit 0 } print "target_met=false"; exit 1 }'
```

Record:

- Post-cutover bootstrap time (minutes):
- Strict target threshold (minutes):
- Improvement vs baseline (%):
- Target met: yes/no

### 10.5 Rollback drill (required)

In non-prod, rehearse rollback with the previous known-good tuple before relying on production rollback:

1. Checkout the exact `infra_commit_sha` for the previous known-good tuple.
2. Re-pin previous known-good tuple in `envs/prod.tfvars` (`vm_image` exact self-link + `reconcile_release_id`).
3. Run `terraform plan` and verify planned `reconcile_sha256` matches the recorded value.
4. Run apply and confirm health gates.
5. Document the tuple, determinism pins, and evidence link in this runbook.

If production rollback is required:

1. Checkout the exact `infra_commit_sha` for the previous known-good tuple.
2. Re-pin previous tuple in `envs/prod.tfvars` (`vm_image` exact self-link + `reconcile_release_id`).
3. Run `terraform plan` and confirm `reconcile_sha256` matches the recorded value.
4. Apply Terraform in controlled window.
5. Re-run the same health gates from section 10.3.

### 10.6 Manual-dispatch Terraform ops workflow (optional)

Use `.github/workflows/infra-terraform-ops.yml` for web-triggered Terraform operations (`plan`, `apply`, `destroy`) when terminal access is not preferred.

Required setup:

- Repository secret: `TFVARS_PROD_B64` (base64-encoded full `infra/terraform/envs/prod.tfvars` payload)
- Repository variables for OIDC auth:
  - `GCP_PROJECT_ID`
  - `GCP_TERRAFORM_WIF_PROVIDER` (or fallback `GCP_GOLDEN_IMAGE_WIF_PROVIDER`)
  - `GCP_TERRAFORM_SERVICE_ACCOUNT` (or fallback `GCP_GOLDEN_IMAGE_SERVICE_ACCOUNT`)
- GitHub environment: `infra-prod` with required reviewers (mutating runs only)

Set/update tfvars secret:

```bash
base64 -w 0 infra/terraform/envs/prod.tfvars | gh secret set TFVARS_PROD_B64
```

Dispatch inputs:

- `action`: `plan` | `apply` | `destroy`
- `target_ref`: git ref input (must be `main`)
- `tf_dir`: input is allowlisted to `infra/terraform`
- `tfvars_path`: input is allowlisted to `envs/prod.tfvars`
- `destroy_confirm`: must equal `DESTROY_PROD` for destroy

Safety gates:

- `plan` fails unless dispatched from protected `main` and `target_ref=main`
- `apply`/`destroy` fail unless dispatched from protected `main` and `target_ref=main`
- `apply`/`destroy` require `infra-prod` environment approval
- `destroy` fails unless `destroy_confirm=DESTROY_PROD`
- decoded tfvars and local plan binaries are removed in an `always()` cleanup step

## 11. Change Log

- Initial runbook created during Step 1 (container + CI/CD foundation).
- Update this file after each completed migration milestone.

---

## 12. Cloud Storage Setup (Production)

Use this after backend deployment is stable on GCP VM.

1. Create bucket (example):

```bash
gcloud storage buckets create gs://quaero-pdf-storage \
  --location=us-east1 \
  --uniform-bucket-level-access
```

2. Grant VM service account object permissions:

```bash
PROJECT_ID="$(gcloud config get-value project)"
VM_SA="$(gcloud compute instances describe quaero-backend --zone=us-east1-b --format='value(serviceAccounts[0].email)')"
gcloud storage buckets add-iam-policy-binding gs://quaero-pdf-storage \
  --member="serviceAccount:${VM_SA}" \
  --role="roles/storage.objectAdmin"
```

3. Update backend env file on VM:

```bash
sudo sed -i '/^STORAGE_BACKEND=/d;/^GCS_BUCKET_NAME=/d;/^GCP_PROJECT_ID=/d' /opt/quaero/env/backend.env
cat <<'EOF' | sudo tee -a /opt/quaero/env/backend.env
STORAGE_BACKEND=gcs
GCS_BUCKET_NAME=quaero-pdf-storage
GCP_PROJECT_ID=portfolio-488721
EOF
```

4. Redeploy backend with GitHub Actions.

5. Validate upload/process/delete against production.

Debug checks:

```bash
docker logs quaero-backend --tail 300
gcloud storage ls gs://quaero-pdf-storage/uploads/
```
