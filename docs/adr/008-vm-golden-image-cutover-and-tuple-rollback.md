# ADR-008: VM Golden-Image Cutover and Tuple Rollback

**Date:** 2026-03-12
**Status:** Superseded (2026-03-12 incident rollback to pre-golden baseline)
**Branch:** task-186-golden-image-production-cutover-validation-gates-and-rollback-runbook

---

This ADR is retained for historical context only. The golden-image pipeline and reconcile-tuple rollout model described here are no longer active in production.

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
2. Require production `vm_image` to be an exact image self-link (not an image family reference) for deterministic rollback.
3. Add deterministic pins to rollout records: `infra_commit_sha` and expected `reconcile_sha256` from Terraform plan.
4. Require Terraform apply/rollback to run from the exact pinned `infra_commit_sha` so computed `reconcile_sha256` matches the intended reconcile artifact.
5. Pin production Terraform config to the golden-image path by setting `vm_image` in `infra/terraform/envs/prod.tfvars`.
6. Add a required cutover evidence section to `docs/GCP_RUNBOOK.md` covering:
   - non-prod rollback rehearsal
   - pre-cutover checkpoint + named owner signoff
   - post-cutover `/health` gate (15 checks, 10s interval)
   - Ops Agent 10-minute no-restart gate
   - bootstrap target evaluation (`<= 6 minutes` or `>= 40%` improvement, whichever is stricter)
7. Require rollback drills and production rollback to re-pin the previous known-good tuple and deterministic pins, then re-run the same health gates.

---

## Consequences

- Rollout and rollback now share one explicit release contract and are easier to audit.
- Production cutover evidence is standardized in the runbook instead of spread across chat/notes.
- Terraform plans now clearly show image-source intent through `vm_image` configuration.
- Production rollback determinism depends on preserving both tuple values and infra commit/hash pins.
