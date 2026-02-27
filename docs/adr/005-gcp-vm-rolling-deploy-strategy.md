# ADR-005: GCP VM Rolling Deploy Strategy on e2-micro

**Date:** 2026-02-27
**Status:** Applied
**Branch:** main

---

## Context

### Background
Quaero migrated backend runtime from Render to a GCP VM (`e2-micro`) with NGINX TLS termination, Cloud SQL PostgreSQL, and GitHub Actions deployment. The backend runtime contains two critical processes in one container:

1. FastAPI web server
2. ARQ worker for asynchronous document processing

The deployment pipeline builds a Docker image, runs Alembic migrations, and starts the runtime container.

### Problem
We needed a production-safe deployment strategy that supports automated releases and rollback without exhausting VM resources.

### Root Cause (if a bug or production incident)
Initial deployment design considered full blue/green overlap on the same VM. On `e2-micro`, running two full runtime containers in parallel creates high memory-pressure and OOM risk because each container runs both API and worker processes.

---

## Options Considered

### Option A: Full blue/green overlap on one VM
Rejected. This keeps old and new containers live simultaneously for zero downtime, but resource overhead is too high for `e2-micro` and increases deployment failure risk.

### Option B: Single-slot rolling deploy with automatic rollback
Accepted. Stop old container, start new container immediately, run health checks, and automatically restart previous image on failure. This minimizes overlap time and memory footprint.

---

## Decision

1. Use single-slot rolling deploy on the GCP VM for backend releases.
2. Keep automatic rollback contract in the VM deploy script:
   - record previous image
   - health-check new runtime
   - restart previous image if checks fail
3. Keep manual deploy fallback (`workflow_dispatch`) in GitHub Actions.
4. Keep API + ARQ worker in one runtime container for this phase.

---

## Consequences

- Deploys are resilient on small VM resources and avoid dual-container OOM risk.
- Downtime is near-zero but not strictly zero during container replacement.
- Rollback speed is fast because previous image reference is persisted on host.
- Architecture remains simple for portfolio scope; future scale can revisit split web/worker services or larger compute.
- This decision should be revisited if:
  - VM size increases enough to safely support blue/green overlap, or
  - API and worker are separated into independently scaled runtimes.
