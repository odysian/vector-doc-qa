Run kickoff for feature task issue # in mode=single.

Then execute the full Task flow end-to-end:
1. Generate/create one Task issue with clear acceptance criteria and verification commands.
2. Create/switch to a new branch.
3. Implement minimally and surgically.
4. Run relevant verification once.
5. Open PR with `Closes #<task-id>` using `scripts/create_pr.sh --body-file ...`.
6. Return a lean reviewer follow-up prompt I can paste to a separate reviewer agent.

Constraints:
- Keep mode `single` unless I explicitly request otherwise.
- No environment triage loops, no worktree setup, no broad verification reruns.
- Keep output concise and findings-first.


=======================

Run kickoff for feature <feature-id> from <filename> mode=single, but planning-only (no code changes, no PR).

Deliver:
1. Problem framing (goal, non-goals, constraints).
2. Proposed implementation plan (3–7 steps, smallest viable path first).
3. Risks and edge cases.
4. Acceptance criteria draft.
5. Verification plan (exact commands to run later).
6. Recommended Task issue body markdown ready for `gh issue create --body-file`.

Constraints:
- Keep it lean and concrete.
- Default to one Task unless I explicitly ask for split/gated mode.
- No speculative architecture; focus on what we can implement next.
