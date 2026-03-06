# Issues Workflow

This repository uses GitHub issues as the execution control plane.

Workflow template baseline in this repository: `agentic-workflow-template v0.2.0` (adopted 2026-03-06).

## Workflow Loop

1. Whiteboard feature ideas in `plans/*.md` or spec docs (scratch planning).
2. Document work as issues using one of the execution modes below.
3. Implement and close Task issues via PRs (`Closes #...`).
4. Finalize by updating docs only when behavior/contracts changed and close related Spec/tracker issues.

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
9. After Task PR creation, run a lean reviewer follow-up pass and return `APPROVED` or `ACTIONABLE`.

## Execution Modes (Choose Before Opening Issues)

Use `single` by default. Use `gated` or `fast` only when explicitly requested.

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
- tests for the feature are included in the same Task by default
- docs are updated when behavior/contracts changed
- follow-ups are created
- reviewer follow-up is completed with verdict and actionable findings addressed or deferred explicitly

## Decisions Policy (Locks, Issues, ADRs)

- Default: Decision Locks live in the controlling issue (Task in `single`, Spec in `gated`).
- Use a separate Decision issue only when discussion is non-trivial or reused across Specs.
- If a decision has lasting architecture/security/performance impact, create an ADR and link it from the Spec or Task (ADR convention: `docs/adr/NNN-kebab-case-title.md`, see `AGENTS.md`).

## Verification Command Source of Truth

Use the Verification section in `AGENTS.md` as the canonical command set.  
Task and PR issue bodies should copy commands from there.
Prefer repo-level verify entrypoints when available (`make backend-verify`, `make frontend-verify`).

## GH Reliability (Supervised Fail-Fast Default)

Use resilient wrappers:

```bash
scripts/create_pr.sh --title "Task #<id>: <short-title>" --body-file <pr-body.md> --base main --head <task-branch> --task-id <id>
```

Required order for GH writes:

1. Run preflight (`scripts/gh_preflight.sh`).
2. Try the exact GH command once (interactive default: `scripts/create_pr.sh --max-attempts=1`).
3. If it fails, request elevated approval for the exact GH command.
4. If elevated execution still fails, provide exact manual one-liner + URL.

## Codex + GitHub CLI Playbook

If using Codex in VS Code with GitHub CLI, follow `skills/spec-workflow-gh.md`.

- `mode=single` (default): generate one Task issue body + `gh issue create` command
- `mode=gated`: generate Spec + Task issue body + commands (only when explicitly requested)
- `mode=fast`: generate quick-fix checklist (only when explicitly requested)
- before GH write commands, run `scripts/gh_preflight.sh`

### Standard Kickoff Prompt (Single Line)

Use this canonical kickoff prompt:

`Run kickoff for feature <feature-id> from <filename> mode=<single|gated|fast>.`

Rules:

- If `mode` is omitted, default to `single`.
- Do not switch to `gated` or `fast` unless explicitly requested.
- Output should include: issue body file(s), `gh issue create` command(s), created issue link(s), and a 3-5 step implementation plan.
- Keep chatter minimal; ask follow-up questions only for hard blockers (auth/permissions/missing required labels).

## Lean Reviewer Follow-Up (Default)

This review step is intentionally narrow and fast.

Flow:

1. Implementation agent opens PR and provides reviewer prompt.
2. Reviewer inspects major correctness/regression risks and missing tests/docs.
3. Reviewer returns:
   - `APPROVED`, or
   - `ACTIONABLE` with concrete fixes.
4. If `ACTIONABLE`, implementation agent patches and reruns relevant verification only.
5. Run second review pass only if explicitly requested.

Reviewer constraints:

- use local diff/repo context first
- no environment triage loops by default
- no worktree setup by default
- no broad verification reruns already reported green
- no command transcript unless a command failed

Required reviewer output:

1. Verdict: `APPROVED` or `ACTIONABLE`
2. Findings (if actionable): severity, file/path:line, issue, required fix
3. Residual risk/testing gaps (up to 3 bullets)

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
