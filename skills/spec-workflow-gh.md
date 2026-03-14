# Playbook: Spec Workflow (Codex + GitHub CLI)

Use this when starting a new feature and you want issue bodies + `gh` commands in one run.

## Invocation Shortcut

Example request:

`Run kickoff for feature 3.1 New Messages Divider from docs/specs/frontend-design-audit.md mode=single.`

Default shorthand request:

`Run kickoff for feature <feature-id> from <filename> mode=<single|gated|fast>.`

Interpret this shorthand as:

- if `mode` omitted, use `mode=single`
- keep `mode=single` unless `gated` or `fast` is explicitly requested
- source from `<filename>` (feature section)
- create/update one Task body file under `plans/`
- run `gh issue create` directly
- return terse summary only

## Inputs

- Feature identifier/title (example: `3.1 New Messages Divider`)
- Mode: `single` (default); use `gated`/`fast` only when explicitly requested
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
- start Task `#<id>` in a dedicated branch (`task-<id>-<short-name>`) and open PR with `Closes #<id>` via `scripts/create_pr.sh`
- provide a lean reviewer follow-up prompt after PR creation

## Procedure

### Single-Mode Automation Defaults (No-Chatter)

When the shorthand request is used, default to this non-interactive behavior:

1. For issue drafting, use the current branch; before implementation, switch to a dedicated Task branch.
2. Run `scripts/gh_preflight.sh` before GH write commands; avoid broad GH discovery scans (`gh label list`, wide repo scans) unless needed.
3. Write one Task issue body file under `plans/`:
- `plans/YYYY-MM-DD-task-<feature-slug>-01.md`
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
  - `YYYY-MM-DD-task-<feature>-01.md` (`single`)
  - `YYYY-MM-DD-spec-<feature>.md` + `YYYY-MM-DD-task-<feature>-01.md` (`gated`)
- mode-specific `gh issue create` commands using `--body-file` and `--label`

You run those commands in the repo terminal.

### C) Execute a Task

Ask Codex to:

- start Task `#<id>` in a dedicated branch
- implement and verify
- open PR containing `Closes #<id>` via `scripts/create_pr.sh`
- if GH write fails: request elevated approval for the exact GH command first; if that still fails, paste the exact one-liner/manual URL
- provide reviewer follow-up prompt with explicit constraints:
  - major bugs/regressions + missing tests/docs only
  - no environment triage loops
  - no worktree setup
  - no broad verification reruns already reported green
  - output findings first, no command transcript unless a command failed
  - second review pass only if explicitly requested

Preferred PR create command:

```bash
scripts/create_pr.sh --title "Task #<id>: <short-title>" --body-file <path-to-pr-body-md> --base main --head <task-branch> --task-id <id>
```

## Common GitHub CLI Snippets

```bash
gh issue create --title "Task: <feature> end-to-end" --label "type:task,area:frontend" --body-file YYYY-MM-DD-task-<feature>-01.md
gh issue create --title "Spec: <feature set>" --label "type:spec" --body-file YYYY-MM-DD-spec-<feature-set>.md
gh issue list --label type:task
gh issue view <id>
```
