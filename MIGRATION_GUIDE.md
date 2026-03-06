# Migration Guide

This guide documents workflow-template adoption for this repository.

## Current Adoption Metadata

- Source template: `agentic-workflow-template v0.2.0`
- Repository: `odysian/vector-doc-qa`
- Adoption date: `2026-03-06`

## v0.2.0 Lean Workflow Contract (Adopted)

- Default execution mode is `single` (1 feature -> 1 Task -> 1 PR).
- Use `gated` or `fast` only when explicitly requested.
- GitHub writes use supervised fail-fast order:
  1. run `scripts/gh_preflight.sh`
  2. run the exact GH command once
  3. if failure, request elevated approval for the exact command
  4. if elevated execution still fails, provide exact manual one-liner + URL
- PR creation uses `scripts/create_pr.sh` with `--body-file`.
- Review follow-up is prompt-based (no scripted review loop required):
  - implementation agent provides reviewer prompt after PR creation
  - reviewer returns only `APPROVED` or `ACTIONABLE`
  - reviewer focuses on major bugs/regressions and missing tests/docs
  - no environment triage loops, worktree setup, or broad verification reruns by default
- Default is one review pass; run a second pass only when explicitly requested.
- Decision brief and docs updates are conditional (only when behavior/contracts/architecture changed).

## Required Local Assets

- `scripts/gh_preflight.sh`
- `scripts/create_pr.sh`

## Notes for Future Template Upgrades

When adopting a newer template version:

1. Keep project-specific policies in `AGENTS.md` intact.
2. Update metadata lines in:
   - `AGENTS.md`
   - `WORKFLOW.md`
   - `docs/ISSUES_WORKFLOW.md`
   - this file (`MIGRATION_GUIDE.md`)
3. Re-verify playbooks and command wrappers together.
