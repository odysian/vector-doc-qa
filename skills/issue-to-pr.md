# Playbook: Issue -> PR Execution

This is a portable procedural playbook. It is not runtime-loaded unless your tooling explicitly loads it.

Given a Task issue:

1. Restate goal and acceptance criteria.
2. Identify files to touch and verification commands.
3. Make minimal, surgical changes.
4. Add/update tests as required by scope.
5. Run verification commands.
6. Commit implementation changes and open PR with `Closes #<task-issue-number>` using `scripts/create_pr.sh` + `--body-file` (fail-fast default).
7. If GH write fails in supervised Codex extension flow: request elevated approval for the exact GH command first; if that still fails, paste the exact one-liner/manual URL.
8. Trigger a fresh-context review agent/session on the PR branch.
9. Patch notable findings on the same branch, commit as `fix(review-r<round>): <finding title>`, and re-run verification.
10. Repeat review/patch at most one additional round (`max_review_rounds=2`, `max_auto_patch_commits=2`), then stop.
11. Document each round in the PR (findings, severity, disposition, commits/follow-ups) and update docs/ADR links when applicable.

Local automation shortcut (agent1 orchestration):

```bash
scripts/fresh_review_loop.sh --task-id <task-id> --base origin/main --verify-cmd "<verify-command>"
```
