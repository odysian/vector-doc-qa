# Playbook: Issue -> PR Execution

This is a portable procedural playbook. It is not runtime-loaded unless your tooling explicitly loads it.

Given a Task issue:

1. Restate goal and acceptance criteria.
2. Identify files to touch and verification commands.
3. Make minimal, surgical changes.
4. Add/update tests as required by scope.
5. Run verification commands.
6. Open PR with `Closes #<task-issue-number>`.
7. Update docs and ADR links when applicable.
