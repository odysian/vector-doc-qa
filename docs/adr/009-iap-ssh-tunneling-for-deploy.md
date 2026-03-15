# ADR-009: IAP SSH Tunneling for Deploy Workflow

**Date:** 2026-03-15
**Status:** Accepted
**Branch:** task-254-iap-ssh-tunneling-for-deploy

---

## Context

### Background

The `Deploy Backend` GitHub Actions workflow connects to the GCP VM to push the backend env file, upload the deploy script, and run it. It previously opened an SSH connection directly to port 22 using a static private key stored in the `GCP_VM_SSH_KEY` secret, with the VM's public IP in `GCP_VM_HOST`.

### Problem

Deploy jobs were failing with `Connection timed out` on port 22. GitHub Actions runners use 150+ dynamic Azure CIDR ranges that rotate frequently; adding all of them to `ssh_source_ranges` is not practical or maintainable. The only stable ingress range available is the Google IAP range (`35.235.240.0/20`), which was already in `ssh_source_ranges`.

### Root Cause

The firewall rule `quaero-allow-ssh` restricts SSH to declared `ssh_source_ranges`. GitHub Actions runners come from IP ranges outside that set, so TCP connections to port 22 time out before the SSH handshake begins.

---

## Options Considered

### Option A: Whitelist all GitHub Actions Azure CIDR ranges
Add all GitHub-published Azure CIDRs to `ssh_source_ranges`. Rejected: the ranges span `/18`–`/20` blocks, change with each release, and expanding them would effectively open SSH to a large fraction of Azure's address space.

### Option B: IAP TCP tunneling + OS Login (chosen)
Route SSH through Google Identity-Aware Proxy. The runner authenticates to GCP via Workload Identity Federation, impersonates a dedicated deploy service account, and `gcloud compute ssh --tunnel-through-iap` opens the tunnel over HTTPS. No direct port-22 exposure needed from the runner's IP. Accepted.

### Option C: Self-hosted runner on GCP
Run the deploy job on a self-hosted GCP runner with a fixed internal IP. Rejected: introduces a persistent runner VM to manage and monitor, increasing operational overhead. The project has no other need for a self-hosted runner.

---

## Decision

1. Enable `iap.googleapis.com` in the project via Terraform.
2. Create a dedicated `quaero-github-deploy-sa` service account (separation of duties from `terraform-ops-sa`).
3. Bind `roles/iap.tunnelResourceAccessor` to the deploy SA at project level so it can open IAP TCP tunnels to any VM in the project.
4. Bind `roles/compute.instanceAdmin.v1` to the deploy SA scoped to the specific VM instance (not project-wide). This grants `compute.instances.setMetadata`, which `gcloud compute ssh` uses to inject a temporary ephemeral SSH key for the connection. OS Login is intentionally not used — see Consequences.
5. Bind `roles/iam.workloadIdentityUser` on the deploy SA to the existing GitHub Actions OIDC principal set, reusing the existing WIF pool and provider from `github_actions_oidc.tf`.
6. In the deploy workflow, replace `ssh`/`scp` steps with `gcloud compute ssh --tunnel-through-iap` and `gcloud compute scp --tunnel-through-iap`, connecting as `odys@INSTANCE`. Use OIDC auth (`google-github-actions/auth@v2`) to obtain a short-lived credential for the deploy SA on each run.
7. Remove `GCP_VM_SSH_KEY` and `GCP_VM_HOST` from the workflow; add `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA_EMAIL`, `GCP_VM_NAME`, `GCP_PROJECT_ID`, `GCP_VM_ZONE`.

---

## Consequences

- **Port 22 no longer needs to be reachable from runner IPs.** The IAP range (`35.235.240.0/20`) already in `ssh_source_ranges` is sufficient. The personal admin CIDR can remain for manual access.
- **Static SSH key is eliminated.** No `GCP_VM_SSH_KEY` to rotate or leak. `gcloud compute ssh` generates a fresh ephemeral key pair per run, injects the public key into the VM's instance metadata, and removes it when the session ends.
- **Short-lived credentials only.** The deploy SA token is scoped to each workflow run and expires automatically; no long-lived credential stored in GitHub Secrets.
- **Separation of duties is maintained.** `quaero-github-deploy-sa` can only tunnel to VMs and write instance metadata; it has no Terraform state or project-wide IAM admin access.
- **OS Login not used — ephemeral key injection instead.** `deploy_backend.sh` calls `docker` directly (no `sudo` prefix). An OS Login SA user (`sa_<uid>`) has no docker group membership; even with `compute.osAdminLogin` granting passwordless sudo, bare `docker` calls fail. Using ephemeral key injection and connecting as `odys` (who is in the docker group) avoids this entirely with no script changes.
- **`compute.instanceAdmin.v1` scoped to instance, not project.** Broader than the minimum needed (`compute.instances.setMetadata` + `compute.instances.get`) but there is no predefined narrow role for just metadata writes. Scoping to the specific instance limits the blast radius.
- **Same WIF pool/provider reused.** No new OIDC infrastructure required; only a new IAM binding on the deploy SA.
- **ops/deploy_backend.sh is unchanged.** The deploy script runs inside the SSH session as before; only the transport layer changed.
