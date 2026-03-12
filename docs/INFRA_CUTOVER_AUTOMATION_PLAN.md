# Infra Cutover Automation Plan (Archived)

**Status:** Deprecated on 2026-03-12  
**Reason:** Manual-first rollout is now the default operating model for production infra.

---

## Purpose of this file

This document is retained for historical context only. It no longer defines active rollout procedure.

Retired automation approach referenced here included:
- `.github/workflows/infra-prod-cutover.yml`
- `.github/workflows/infra-terraform-plan.yml`
- workflow-coupled risk label taxonomy

Those controls were removed from active infra process to reduce operator overhead for a solo-maintainer workflow.

## Current source of truth

Use these documents for active production rollout and rollback:
- `docs/GCP_RUNBOOK.md` section 10 (manual-first cutover + rollback)
- `infra/terraform/README.md` (manual-first Terraform execution path)

## Manual helper status

`scripts/infra_cutover.sh` remains in-repo as an optional manual helper.
It is not the default control plane.
