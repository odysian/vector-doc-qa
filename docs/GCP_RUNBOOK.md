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

Terraform startup bootstrap now handles Docker + NGINX + Certbot + env file stub creation on VM rebuild.

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
DATABASE_URL=postgresql://postgres:<password>@<cloud-sql-ip>:5432/postgres?options=-c%20search_path=quaero,public
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

## 6. Post-Deploy Smoke Checklist

1. Health endpoint:
   - `GET /health` returns healthy
2. Auth:
   - login succeeds
   - `/api/auth/me` succeeds
   - refresh succeeds
3. Document flow:
   - upload PDF
   - status transitions from `pending/processing` to `completed`
   - query returns answer with sources
   - delete succeeds
4. Worker:
   - background processing starts automatically after upload

---

## 7. NGINX and TLS Checks

## NGINX status and config test

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
```

## Certbot status

```bash
sudo systemctl status certbot.timer --no-pager
sudo certbot renew --dry-run
```

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

---

## 9. Observability Pointers

Minimum diagnostics during incidents:

1. VM resource pressure:
   - `free -h`
   - `top`
2. Container lifecycle:
   - `docker ps -a --filter "name=quaero-backend"`
   - `docker inspect quaero-backend --format '{{.State.Restarting}} {{.State.ExitCode}}'`
3. App logs:
   - `docker logs quaero-backend --tail 500`
4. NGINX logs:
   - `/var/log/nginx/access.log`
   - `/var/log/nginx/error.log`

---

## 10. Change Log

- Initial runbook created during Step 1 (container + CI/CD foundation).
- Update this file after each completed migration milestone.

---

## 11. Cloud Storage Setup (Production)

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
