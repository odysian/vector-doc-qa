# Issues Workflow

This repository uses GitHub issues as the execution control plane.

## Workflow Loop

1. Whiteboard feature ideas in `plans/*.md` or spec docs (scratch planning).
2. Document work as issues using one of the execution modes below.
3. Implement and close Task issues via PRs (`Closes #...`).
4. Finalize by updating required docs and closing related Spec/tracker issues.

## Objects

- **Task** (`type:task`): PR-sized implementation unit and default feature issue.
- **Spec** (`type:spec`): feature-set/spec umbrella with decision locks and child Task links.
- **Decision** (`type:decision`): short-term decision lock with rationale when discussion is non-trivial.

## Core Rules

1. GitHub Issues are the source of truth for execution. `TASKS.md` is scratchpad only.
2. The default execution path is **1 feature -> 1 Task -> 1 PR**.
3. PRs close Task issues (`Closes #...`), not Specs.
4. Specs close only when all child Tasks are done or explicitly deferred.
5. Tasks are PR-sized; in this workflow PR-sized usually means end-to-end feature delivery.
6. Backend-coupled work requires Decision Locks checked before implementation begins.
7. After major refactors, open one docs-only Task for readability hardening (comments + `docs/PATTERNS.md` updates), with no behavior changes.
8. For `single` and `gated` modes, create a dedicated branch for the Task issue before implementation (for example: `task-123-short-name`).

## Execution Modes (Choose Before Opening Issues)

### `single` (Default)

Use one Task issue per feature, then one PR that closes it.

- Best for most feature work.
- Task includes mini-spec content: summary/scope/acceptance criteria/verification.
- Decision Locks live in the Task for backend-coupled work.

### `gated` (Spec + Tasks)

Use one Spec issue plus child Task issue(s).

- Use when working a feature set (for example a phase roadmap) or higher-risk work.
- Decision Locks live in the Spec.
- Child Tasks should stay PR-sized (default one Task per feature).

### `fast` (Quick Fix)

For this project, a direct quick-fix path is allowed without mandatory issue creation when all are true:

- the change is small and low-risk (single logical fix)
- no schema/API/background-processing contract change
- no auth/security model change
- no migration/dependency changes
- no ADR-worthy architectural decision

When using Fast Lane:

- run relevant verification for touched areas
- commit with a clear quick-fix message
- follow this repo's normal branch/merge policy
- if scope grows, switch to `single` or `gated`

## When to Split Into Multiple Tasks

Split only when it clearly improves delivery or risk control:

- change is too large for one PR (guideline: ~600+ LOC or hard to review)
- backend contract should land before frontend integration
- migrations or API/background-processing contract changes increase risk
- parallel work or staged rollout is needed

## Definition of Ready (Task)

A Task can move to `status:ready` when:

- acceptance criteria are written
- verification commands are listed
- dependencies and links are included
- for backend-coupled work: Decision Locks are checked in the controlling issue (Task in `single`, Spec in `gated`)

## Definition of Done (Task)

A Task can be closed when:

- PR is merged
- verification commands pass
- tests and docs for the feature are included in the same Task by default
- docs are updated if required
- follow-ups are created

## Decisions Policy (Locks, Issues, ADRs)

- Default: Decision Locks live in the controlling issue (Task in `single`, Spec in `gated`).
- Use a separate Decision issue only when discussion is non-trivial or reused across Specs.
- If a decision has lasting architecture/security/performance impact, create an ADR and link it from the Spec or Task (ADR convention: `docs/adr/NNN-kebab-case-title.md`, see `AGENTS.md`).

## Verification Command Source of Truth

Use the Verification section in `AGENTS.md` as the canonical command set.  
Task and PR issue bodies should copy commands from there.
Prefer repo-level verify entrypoints when available (`make backend-verify`, `make frontend-verify`).

## Codex + GitHub CLI Playbook

If using Codex in VS Code with GitHub CLI, follow `skills/spec-workflow-gh.md`.

- `mode=single` (default): generate one Task issue body + `gh issue create` command
- `mode=gated`: generate Spec + Task issue body + commands
- `mode=fast`: generate quick-fix checklist (no issue commands by default)

### Standard Kickoff Prompt (Single Line)

Use this canonical kickoff prompt:

`Run kickoff for feature <feature-id> from <filename> mode=<single|gated|fast>.`

Rules:

- If `mode` is omitted, default to `single`.
- Output should include: issue body file(s), `gh issue create` command(s), created issue link(s), and a 3-5 step implementation plan.
- Keep chatter minimal; ask follow-up questions only for hard blockers (auth/permissions/missing required labels).

### Resiliency Checkpoints (Lightweight)

Before implementation in `single`/`gated` modes, restate:

- Goal and non-goals
- Files in scope and files explicitly out of scope
- Acceptance criteria and verification commands

Before completion, restate:

- What changed
- What did not change (contracts/behavior)
- Verification results and follow-ups (if any)

## Common GitHub CLI Commands

```bash
gh issue create --title "Task: <feature> end-to-end" --label "type:task,area:frontend" --body-file task-<feature>-01.md
gh issue create --title "Spec: <feature set>" --label "type:spec" --body-file spec-<feature-set>.md
gh issue list --label type:task
gh issue view <id>
```

## Manual GitHub Setup

Recommended labels:

- `type:spec`, `type:task`, `type:decision`, `type:docs`, `type:bug`
- `status:ready`, `status:blocked`, `status:in-progress`, `status:review`, `status:done`
- `area:frontend`, `area:backend`, `area:db`, `area:workers`, `area:tests`, `area:docs`

Recommended board columns:

- Backlog -> Ready -> In Progress -> In Review -> Done

## New Project Bootstrap

1. Create issue labels and board columns from this document.
2. Define stack constraints and canonical verification commands in `AGENTS.md`.
3. Whiteboard initial feature ideas in `plans/*.md` or spec docs.
4. Choose execution mode per feature (`single` default, `gated` for feature sets/risk, `fast` for tiny fixes).
5. Create issues, implement, and close Task issues with PRs.
6. Close Specs only after child Tasks are done or deferred.
7. Keep `TASKS.md` optional and non-authoritative (or omit it entirely).
8. Record lasting architecture/security/performance decisions as ADRs.

## Optional Later

MCP is out of scope for v1. Add it later only to automate issue creation, labeling, or CI summaries.
