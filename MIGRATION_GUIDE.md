# Migration Guide

This guide documents workflow-template adoption for this repository.

Migration context: this repo moved from prior `v0.2.x` behavior to `v0.3.0` contracts.

## Current Adoption Metadata

- Source template: `agentic-workflow-template v0.3.0`
- Repository: `odysian/vector-doc-qa`
- Adoption date: `2026-03-05`

## v0.3.0 Workflow Contract (Adopted)

- GitHub writes are supervised fail-fast:
  1. run `scripts/gh_preflight.sh`
  2. run the exact GH command once
  3. if failure, request elevated approval for the exact command
  4. if elevated execution still fails, provide exact manual one-liner + URL
- Local PR automation uses `scripts/create_pr.sh` with `--body-file`.
- Local fresh review automation uses `scripts/fresh_review_loop.sh`.
- Review loop is bounded (`max_review_rounds=2`, `max_auto_patch_commits=2`).
- Queue/outbox fallback is removed from workflow conventions.

## Required Local Assets

- `scripts/gh_preflight.sh`
- `scripts/create_pr.sh`
- `scripts/fresh_review_loop.sh`
- `scripts/prompts/*`
- `scripts/schemas/*`
- `.codex/audit/.gitkeep`

## Local Artifact Rules

- Local fresh-review artifacts live under `.codex/audit/task-<id>-<utc-timestamp>/`.
- Track no outbox queue conventions in docs or scripts.

## Notes for Future Template Upgrades

When adopting a newer template version:

1. Keep project-specific policies in `AGENTS.md` intact.
2. Update metadata lines in:
   - `AGENTS.md`
   - `WORKFLOW.md`
   - `docs/ISSUES_WORKFLOW.md`
   - this file (`MIGRATION_GUIDE.md`)
3. Re-verify GH/fresh-review scripts and playbooks together.
