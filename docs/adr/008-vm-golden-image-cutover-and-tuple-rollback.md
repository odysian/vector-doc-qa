# ADR-008: VM Golden-Image Cutover and Tuple Rollback

**Date:** 2026-03-12
**Status:** Accepted
**Branch:** task-186-golden-image-production-cutover-validation-gates-and-rollback-runbook

---

## Context

### Background

The infrastructure now has a golden-image pipeline and a stable startup launcher with external reconcile artifacts. Production still required explicit cutover policy and rollback validation gates.

### Problem

Without a formal cutover contract, production rollouts could drift between image updates and reconcile updates, and rollback evidence could be incomplete during incidents.

### Root Cause (if a bug or production incident)

Prior rollout docs did not define one mandatory release identity across image promotion and reconcile rollout, and did not enforce post-cutover gate evidence in one place.

---

## Options Considered

### Option A: Keep image source implicit and rely on ad-hoc rollback notes

Rejected. This keeps operational ambiguity around what exact runtime tuple is being promoted or reverted.

### Option B: Pin rollout to explicit tuple with required cutover/rollback gates

Accepted. This keeps release identity explicit and makes rollback rehearsals and post-cutover checks auditable.

---

## Decision

1. Define production rollout identity as a tuple: `vm_image` (`image_version`) + `reconcile_release_id`.
2. Pin production Terraform config to the golden-image path by setting `vm_image` in `infra/terraform/envs/prod.tfvars`.
3. Add a required cutover evidence section to `docs/GCP_RUNBOOK.md` covering:
   - non-prod rollback rehearsal
   - pre-cutover checkpoint + named owner signoff
   - post-cutover `/health` gate (15 checks, 10s interval)
   - Ops Agent 10-minute no-restart gate
   - bootstrap target evaluation (`<= 6 minutes` or `>= 40%` improvement, whichever is stricter)
4. Require rollback drills and production rollback to re-pin the previous known-good tuple and re-run the same health gates.

---

## Consequences

- Rollout and rollback now share one explicit release contract and are easier to audit.
- Production cutover evidence is standardized in the runbook instead of spread across chat/notes.
- Terraform plans now clearly show image-source intent through `vm_image` configuration.
- Family-based image references remain operationally simple, but teams should use exact image pins when tighter deterministic rollback is needed.
