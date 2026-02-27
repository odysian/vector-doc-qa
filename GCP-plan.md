# Quaero Render -> GCP Migration Plan

## 1. Summary

Migrate Quaero backend infrastructure from Render to GCP while keeping frontend on Vercel and queueing on Upstash Redis. The migration will use an `e2-micro` VM, so deployments must avoid full blue/green overlap to reduce OOM risk.

The deploy strategy is:

1. Build and push backend container image in GitHub Actions.
2. SSH to VM and pull image.
3. Run Alembic migrations in one-shot container.
4. Replace running container quickly (single-slot rolling deploy).
5. Health check.
6. Auto-rollback to last known good image if health fails.

---

## 2. Current State (Validated)

Already completed:

- GCP project exists: `project-506ba7ba-0c8b-49fa-b11`
- Cloud SQL instance exists: `portfolio-db` (`us-east1`, PostgreSQL 15)
- `pgvector` extension enabled
- `quaero` schema created
- Alembic migrations applied
- VM exists: `quaero-backend` (`us-east1-b`, Debian 12, Docker installed)
- Cloud SQL authorized network restricted to VM external IP

Repository facts:

- Backend startup script for production process model exists:
  `backend/run-web-and-worker.sh` (API + ARQ worker in one container)
- No backend Dockerfile currently exists in this repo
- No `.github/workflows` currently exists in this repo
- File uploads are currently local disk based (`uploads/`)

---

## 3. Goals and Non-Goals

### Goals

1. Backend runtime on GCP VM behind NGINX and TLS.
2. Database on Cloud SQL.
3. Automated GitHub Actions deployment with rollback.
4. Durable PDF storage using Cloud Storage.
5. Minimal user-visible downtime during deploys.

### Non-Goals

1. Migrating frontend off Vercel.
2. Replacing Upstash Redis.
3. Splitting API and worker into separate services in this phase.
4. Introducing Kubernetes/Terraform in this phase.

---

## 4. Target Architecture

- Frontend: Vercel (`quaero.odysian.dev`)
- API domain: `api.quaero.odysian.dev`
- Backend runtime: Docker container on GCE VM (FastAPI + ARQ worker together)
- Reverse proxy: NGINX on VM (`80/443` -> `127.0.0.1:8000`)
- TLS: Let's Encrypt via Certbot
- DB: Cloud SQL PostgreSQL + `pgvector`
- Queue: Upstash Redis (unchanged)
- File storage: Cloud Storage bucket

---

## 5. Deployment Strategy Decision

### Chosen

Single-slot rolling deploy with automatic rollback.

### Why this over blue/green overlap

- On `e2-micro`, running two full containers (each with API + worker) concurrently is high OOM risk.
- Single-slot rolling keeps memory predictable while still allowing fast recovery.

### Rollback contract

- VM stores last known good image tag.
- If post-start health check fails, deploy script restarts previous image automatically.
- Deploy fails fast in GitHub Actions log.

---

## 6. Workstreams

## A. VM Foundation and Network

1. Reserve static external IP for `quaero-backend`.
2. Update DNS `api.quaero.odysian.dev` to static IP.
3. Configure firewall rules:
   - allow `80/tcp`, `443/tcp`
   - restrict SSH source ranges as much as practical
4. Install and configure NGINX reverse proxy.
5. Install Certbot and issue TLS cert.
6. Enable cert auto-renew and NGINX reload hook.
7. Create persistent deploy directories:
   - `/opt/quaero/env/`
   - `/opt/quaero/deploy/`
   - `/opt/quaero/logs/`

Acceptance checks:

- `curl -I https://api.quaero.odysian.dev/health` returns application response.
- `systemctl status certbot.timer` is active.

## B. Containerization

1. Add `backend/Dockerfile`.
2. Add `backend/.dockerignore`.
3. Ensure image startup command executes `run-web-and-worker.sh`.
4. Ensure script is executable in image.
5. Do not run migrations automatically in container startup.

Acceptance checks:

- Container boots with both API and worker processes.
- Container exits if one of the two subprocesses exits (expected fail-fast behavior).

## C. GitHub Actions CI/CD

1. Add `.github/workflows/backend-deploy.yml`.
2. Build job:
   - checkout
   - buildx setup
   - login GHCR
   - build and push tags:
     - `ghcr.io/<owner>/<repo>/quaero-backend:<sha>`
     - `ghcr.io/<owner>/<repo>/quaero-backend:latest`
3. Deploy job:
   - SSH to VM
   - docker login GHCR
   - pull image
   - run migrations (one-shot container)
   - restart runtime container
   - health check
   - rollback on failure
4. Trigger policy:
   - `workflow_dispatch` initially
   - enable `push` on `main` after one successful manual deployment

Acceptance checks:

- Manual dispatch deploys successfully.
- Forced bad image scenario rolls back automatically.

## D. VM Deploy Script

Create VM script: `/opt/quaero/deploy/deploy_backend.sh`

Responsibilities:

1. Read target image tag arg.
2. Pull target image.
3. Run `alembic upgrade head` in one-shot container with prod env file.
4. Capture current running image as rollback target.
5. Stop and remove current container.
6. Start new container:
   - name: `quaero-backend`
   - port mapping: `127.0.0.1:8000:8000`
   - restart policy: `unless-stopped`
   - env-file: `/opt/quaero/env/backend.env`
7. Poll `http://127.0.0.1:8000/health` with retry window.
8. On failure:
   - container logs dump
   - restart previous image
   - return non-zero
9. Persist last successful image tag.
10. Prune dangling images.

## E. Production App Configuration

Required env in `/opt/quaero/env/backend.env`:

```bash
DATABASE_URL=postgresql://postgres:<password>@<cloud-sql-ip>:5432/postgres?options=-c%20search_path=quaero,public
SECRET_KEY=<strong-random>
OPENAI_API_KEY=<...>
ANTHROPIC_API_KEY=<...>
REDIS_URL=<upstash-redis-url>
FRONTEND_URL=https://quaero.odysian.dev
PORT=8000
```

Notes:

- `ENVIRONMENT=production` is optional and currently unused by code.
- `FRONTEND_URL` must exactly match frontend origin for CORS and cookies.

## F. Cloud Storage Migration

Current issue:

- Uploads are saved to local disk and referenced by `documents.file_path`.

Implementation plan:

1. Add storage abstraction service with two backends:
   - `local` backend (dev/test compatibility)
   - `gcs` backend (production)
2. Update upload flow to write file via storage backend and store object key in `file_path`.
3. Update processing flow to read PDF from storage backend.
4. Update delete flow to delete object via storage backend.
5. Keep response contracts unchanged.
6. Use VM service account permissions for GCS access (avoid static JSON key if possible).

Additional env for GCS:

```bash
STORAGE_BACKEND=gcs
GCS_BUCKET_NAME=<bucket-name>
GCP_PROJECT_ID=project-506ba7ba-0c8b-49fa-b11
```

Acceptance checks:

- Upload -> process -> query -> delete flow passes in production with GCS backend.
- Local development still works with `STORAGE_BACKEND=local`.

## G. Cutover Sequence

1. Complete VM + NGINX + TLS baseline.
2. Deploy first backend image manually via workflow.
3. Verify backend smoke tests on new domain.
4. Update Vercel `NEXT_PUBLIC_API_URL` to `https://api.quaero.odysian.dev`.
5. Run end-to-end smoke from frontend.
6. Observe for 24-48h.
7. Disable Render backend.
8. Decommission Render DB before expiry after final validation.

---

## 7. GitHub Secrets and Access Requirements

Required GitHub Actions secrets:

- `GCP_VM_HOST`
- `GCP_VM_USER`
- `GCP_VM_SSH_KEY`
- `GHCR_USERNAME`
- `GHCR_TOKEN`

VM host prerequisites:

- Docker installed and usable by deploy user
- NGINX configured
- Certbot configured
- `/opt/quaero/env/backend.env` present
- deploy user authorized for SSH key

---

## 8. Verification and Smoke Tests

## Infrastructure checks

1. `curl -f http://127.0.0.1:8000/health` on VM host
2. `curl -f https://api.quaero.odysian.dev/health` externally
3. `docker ps` shows `quaero-backend` healthy uptime
4. NGINX access/error logs clean of repeated upstream failures

## App checks

1. Auth flow:
   - login
   - `/api/auth/me`
   - refresh
   - logout
2. Document flow:
   - upload PDF
   - status transitions to `completed`
   - query returns answer with sources
   - delete removes document and file object
3. Worker check:
   - queue processing starts without manual intervention

## Rollback drill

1. Deploy intentionally broken image to staging-like run.
2. Confirm health failure.
3. Confirm automatic rollback to previous image.

---

## 9. Risks, Gotchas, and Mitigations

1. **No Dockerfile in repo yet**
   - Risk: cannot start CI/CD.
   - Mitigation: containerization is first implementation task.

2. **e2-micro memory constraints**
   - Risk: OOM and container kill.
   - Mitigation: single-slot rolling deploy, no full blue/green overlap, conservative worker settings.

3. **Cloud SQL authorized network tied to ephemeral VM IP**
   - Risk: DB outage if VM IP changes.
   - Mitigation: static IP reservation.

4. **Migration compatibility**
   - Risk: destructive migrations can break rolling deployments.
   - Mitigation: require backward-compatible migration discipline for automated deploy path.

5. **Single container runs API + worker**
   - Risk: coupled failure domain.
   - Mitigation: fail-fast supervisor script + `unless-stopped` restart + clear logs/alerts.

6. **CORS/cookie regression on domain cutover**
   - Risk: auth failures from frontend.
   - Mitigation: verify exact `FRONTEND_URL`, HTTPS-only production cookies, full login/refresh smoke.

7. **Cloud Storage IAM misconfiguration**
   - Risk: uploads fail at runtime.
   - Mitigation: least-privileged service account role and explicit write/read/delete preflight checks.

8. **Cert renewal drift**
   - Risk: TLS outage.
   - Mitigation: check `certbot.timer` and periodic dry-run renewal.

9. **Rollback image not recorded**
   - Risk: failed deploy cannot auto-recover.
   - Mitigation: persist last successful image tag atomically in deploy script.

10. **Health endpoint may not reflect worker-specific failures**
    - Risk: false green.
    - Mitigation: include functional upload/process smoke check post-deploy.

---

## 10. Implementation Order (Recommended)

1. Create issue set (`gated` mode): spec + child tasks.
2. Add Dockerfile and `.dockerignore`.
3. Configure VM runtime, NGINX, TLS, static IP.
4. Add GitHub Actions deploy workflow + VM deploy script.
5. Perform first manual deployment and rollback test.
6. Update Vercel API URL and cut over traffic.
7. Implement Cloud Storage migration and deploy.
8. Run final validation window and decommission Render resources.

---

## 11. Decision Brief

- **Chosen approach:** GitHub Actions + VM SSH single-slot rolling deploy with automatic rollback, followed by Cloud Storage migration.
- **Alternative considered:** full blue/green overlap on same tiny VM.
- **Tradeoff:** slightly more cutover risk in exchange for materially lower memory pressure and lower deployment failure probability on `e2-micro`.
- **Revisit trigger:** move to larger VM or split API and worker into separate services where true overlap becomes safe.
