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
8. Provide a lean reviewer follow-up prompt for a separate review pass.
9. If reviewer returns `ACTIONABLE`, patch findings and rerun relevant verification only.
10. Run a follow-up review pass only if explicitly requested.
11. Update docs and ADR links when applicable.

Reviewer prompt should require:

1. Verdict: `APPROVED` or `ACTIONABLE`
2. Findings (if actionable): severity, file/path:line, issue, required fix
3. Residual risk/testing gaps (max 3 bullets)

Reviewer constraints:

- no environment triage loops
- no worktree setup
- no broad verification reruns already reported green
- no command transcript unless a command failed
