# Playbook: Plan/Spec -> Issues

This is a portable procedural playbook. It is not runtime-loaded unless your tooling explicitly loads it.

Given a feature plan (from `plans/*.md`, specs, or a Spec):

1. Choose execution mode first:
- `single` (default): one end-to-end Task issue, one PR closes it.
- `gated`: one Spec issue + child Task issue(s).
- `fast`: quick-fix checklist only (no issue creation by default).
2. In `single` mode, the Task should include mini-spec sections:
- summary/goal
- scope in/out
- acceptance criteria
- verification commands
- decision locks when backend-coupled
3. In `gated` mode:
- Spec holds decision locks and feature-set context
- child Tasks stay PR-sized (default one Task per feature)
- each Task includes `Parent Spec: (placeholder)` until real Spec issue ID exists
4. Split into additional Tasks only when split criteria apply (size/risk/dependency/parallelization), and explain why.
5. Task acceptance criteria should include checkboxes for:
- backend work (if applicable)
- frontend work (if applicable)
- tests
- docs
6. Output format must clearly show:
- `Mode selected: single|gated|fast`
- `Default plan: single Task` (or gated structure)
- `Optional split plan (only if needed): ...`

## Single-Mode Quick Command Defaults

If the request is phrased as:

`Create an issue workflow for feature <feature-id> in <filename>.`

apply these defaults automatically:

- select `mode=single`
- extract only the requested feature section from `<filename>`
- generate one Task issue body at `plans/task-<feature-slug>-01.md`
- run `gh issue create` without extra discovery chatter
- return a terse completion summary (issue URL, file path, concise implementation plan, command used)
