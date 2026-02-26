# Playbook: Spec Workflow (Codex + GitHub CLI)

Use this when starting a new feature and you want issue bodies + `gh` commands in one run.

## Invocation Shortcut

Example request:

`Run skills/spec-workflow-gh.md for 3.1 New Messages Divider mode=single. Produce issue body files + gh issue create commands.`

Default shorthand request:

`Create an issue workflow for feature <feature-id> in <filename>.`

Interpret this shorthand as:

- `mode=single`
- source from `<filename>` (feature section)
- create/update one Task body file under `plans/`
- run `gh issue create` directly
- return terse summary only

## Inputs

- Feature identifier/title (example: `3.1 New Messages Divider`)
- Mode: `single` (default), `gated`, or `fast`
- Spec link/section (optional)
- Area labels (optional)

## Output Requirements

1. `mode=single` (default):
- one Task markdown body for end-to-end implementation
- one `gh issue create` command for the Task
2. `mode=gated`:
- one Spec markdown body + one default Task body
- optional 0-2 extra Task bodies only when split criteria apply, with rationale
- `gh issue create` commands for Spec + Task issue(s)
3. `mode=fast`:
- quick-fix checklist (scope, verify commands, commit message)
- no issue commands by default
4. Task bodies include:
- suggested labels
- acceptance criteria with backend/frontend/tests/docs checkboxes
- `Parent Spec: (placeholder)` only in `mode=gated`
5. Final execution step for issue modes:
- start Task `#<id>` in a new branch and open PR with `Closes #<id>`

## Procedure

### Single-Mode Automation Defaults (No-Chatter)

When the shorthand request is used, default to this non-interactive behavior:

1. Use the current branch. Do not switch branches unless explicitly asked.
2. Do not run preflight discovery commands by default (`gh auth status`, `gh label list`, broad repo scans).
3. Write one Task issue body file under `plans/`:
- `plans/task-<feature-slug>-01.md`
4. Run `gh issue create` directly with the labels inferred from scope.
5. Only ask follow-up questions on hard failures (auth, permissions, missing required labels).
6. Output only:
- issue number + URL
- file written
- 3-5 bullet implementation plan
- exact `gh issue create` command used

### A) Draft issue body content (text generation)

Ask Codex to:

- choose mode from criteria in `docs/ISSUES_WORKFLOW.md`
- for `single`: generate one end-to-end Task body
- for `gated`: generate Spec + one default Task body
- add optional split Tasks only when split criteria are met
- include labels and acceptance criteria
- include `Parent Spec: (placeholder)` only for gated child Tasks

### B) Generate GitHub CLI commands

Ask Codex to output:

- mode-specific filenames to save locally:
  - `task-<feature>-01.md` (`single`)
  - `spec-<feature>.md` + `task-<feature>-01.md` (`gated`)
- mode-specific `gh issue create` commands using `--body-file` and `--label`

You run those commands in the repo terminal.

### C) Execute a Task

Ask Codex to:

- start Task `#<id>` in a new branch
- implement and verify
- open PR containing `Closes #<id>`

## Common GitHub CLI Snippets

```bash
gh issue create --title "Task: <feature> end-to-end" --label "type:task,area:frontend" --body-file task-<feature>-01.md
gh issue create --title "Spec: <feature set>" --label "type:spec" --body-file spec-<feature-set>.md
gh issue list --label type:task
gh issue view <id>
```
