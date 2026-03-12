# Infra Cutover Automation Plan (Solo Dev Friendly)

**Date:** 2026-03-12  
**Audience:** Solo developer, new contributors, interns  
**Goal:** Make infra rollout/cutover predictable and low-friction without losing rollback safety.

---

## 1) TL;DR

You are not wrong: this got complicated fast.

Today, the project is in a **hybrid state**:
- Build path is automated (golden images are built by workflow).
- Production promotion/cutover still expects operator-driven steps (with safety gates).
- New helper commands reduce command juggling, but policy still requires explicit cutover control.

Best solo-dev direction:
1. Keep strict rollback safety rules.
2. Move repetitive steps into CI workflows.
3. Keep exactly one manual approval step for production apply.

Review note:
- Before workflow implementation starts, create/confirm the label set used by automation (`area:infra`, `deploy:terraform`, `risk:terraform-safe`, `risk:terraform-gated`, `gate:prod-approval-required`).

---

## 2) What Is Going On (Plain English)

The backend VM now has two moving parts:

1. **Base VM image (`vm_image`)**
   - Think of this as the pre-baked operating system + baseline tools.
   - Changing this usually means VM replacement.

2. **Runtime reconcile release (`reconcile_release_id`)**
   - Think of this as the runtime "fixup script" version.
   - Changing this should usually avoid full VM replacement.

To make rollback deterministic, production records also pin:
- `infra_commit_sha` (exact repo commit used during apply)
- `reconcile_sha256` (hash expected in metadata/plan)

So rollout identity is:
- Main tuple: (`vm_image`, `reconcile_release_id`)
- Determinism pins: (`infra_commit_sha`, `reconcile_sha256`)

---

## 3) Why It Feels Messy

Three different concerns got merged together:

1. **Infra architecture change**
   - Golden image + launcher/reconcile split.

2. **Operational safety requirements**
   - Snapshot, health gates, rollback rehearsal, evidence logging.

3. **Tooling ergonomics**
   - Too many manual commands before helpers were added.

Result: technically sound model, but heavy operator cognitive load.

---

## 4) What Is Automated vs Manual Right Now

| Area | Current State |
|---|---|
| Golden image build | Automated (workflow) |
| Terraform format/validate/plan for cutover | Automated via `make infra-cutover-prepare` |
| Snapshot checkpoint | Automated inside `infra-cutover-prepare` |
| Health gate loops | Automated via `make infra-cutover-postcheck` |
| Bootstrap target calculation | Automated via `infra-cutover-postcheck` flags |
| Production `terraform apply` | Still manual/operator-triggered |
| Evidence section completion | Still manual (copy concrete values/links) |
| Rollback run | Still manual/operator-triggered |

---

## 5) Tradeoffs

### Option A: Keep fully manual

Pros:
- Maximum operator control.
- Easier to pause if something looks wrong.

Cons:
- High cognitive load.
- Easy to forget one step.
- Slow and inconsistent under stress.

### Option B: Fully automatic apply on every Terraform merge

Pros:
- Minimal human effort.
- Fastest feedback cycle.

Cons:
- Higher blast radius for bad Terraform changes.
- Risky for single-instance production infrastructure.

### Option C: Hybrid (Recommended)

Pros:
- Repetitive steps automated.
- Single manual approval gate for prod.
- Good safety/velocity balance for solo dev.

Cons:
- Slightly more workflow setup.
- Still one deliberate human click for prod.

---

## 6) Recommended Solo-Dev Approach

Use **Hybrid** with one explicit production approval.

### Policy

1. Every Terraform PR gets plan automation and a risk label.
2. Production apply runs only through a dedicated workflow with environment approval.
3. Rollback uses the same workflow path with previous pinned tuple.

### Daily Operator Experience (Target)

1. Merge PR.
2. Open "Infra Prod Apply" workflow.
3. Confirm inputs (`vm_image`, `reconcile_release_id`, optional rollback mode).
4. Approve environment.
5. Workflow runs snapshot -> plan -> apply -> postchecks -> evidence artifact.

No command chain copying needed in normal cases.

---

## 7) Phased Implementation Plan

### Phase 0 (Now, already started)

- Helper commands exist:
  - `make infra-cutover-prepare`
  - `make infra-cutover-postcheck`
- Runbook documents deterministic pins and evidence contract.
- Label readiness gate for next agent review:
  - verify existing labels
  - create missing labels before Phase 1 workflow wiring

### Phase 1 (Next)

Add PR/CI control-plane automation:

1. `terraform fmt -check`, `validate`, `plan` on PR.
2. Post plan summary to PR.
3. Detect risky actions (`destroy`, `replace`) and mark the PR clearly.
4. Upload plan/evidence draft artifacts.

### Phase 2

Add production apply workflow (manual dispatch + environment approval):

1. Inputs:
   - `vm_image`
   - `reconcile_release_id`
   - `expected_infra_commit_sha` (optional strict check)
2. Steps:
   - checkpoint snapshot
   - plan
   - apply
   - postchecks
   - evidence artifact output

### Phase 3

Add rollback workflow:

1. Inputs:
   - previous `vm_image`
   - previous `reconcile_release_id`
   - previous `infra_commit_sha`
2. Same gated flow as apply.
3. Same postchecks and artifacts.

### Phase 4

Quality-of-life + guardrails:

1. Script/workflow check that `vm_image` is not family-based for production.
2. Consistency check for tuple docs/ADR/runbook.
3. Optional auto-fill patch for runbook evidence block from workflow artifacts.

---

## 8) "If I Changed X, What Do I Do?" Cheat Sheet

| Change Type | Use Full Cutover Flow? | Notes |
|---|---|---|
| App code only | No | Normal backend/frontend deploy path |
| `vm_image` change | Yes | Treat as production cutover event |
| `reconcile_release_id` only | Usually yes (lighter) | Still requires plan/apply and pin discipline |
| Startup launcher behavior | Yes | Can impact boot and rollback safety |
| Docs-only changes | No | No infra rollout needed |

---

## 9) Intern Glossary

- **Golden image:** Pre-baked VM disk image with baseline software installed.
- **Reconcile:** Script that makes runtime config/state match expected config.
- **Tuple:** The key version pair that identifies a rollout (`vm_image`, `reconcile_release_id`).
- **Determinism pins:** Extra values proving exactly what was applied (`infra_commit_sha`, `reconcile_sha256`).
- **Cutover:** Moving production from old rollout state to new rollout state.
- **Rollback:** Returning production to previous known-good rollout state.

---

## 10) Recommended Next Two Weeks

1. Land helper-script changes and docs update.
2. Implement Phase 1 PR plan automation.
3. Implement Phase 2 environment-gated prod apply workflow.
4. Trial one non-prod rollout entirely via workflow.
5. After one clean trial, switch prod process to workflow-first.

This gives you automation where it helps most, while keeping the one control point that prevents accidental outages.
