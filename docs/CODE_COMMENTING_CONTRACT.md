# Code Commenting Contract — vector-doc-qa

Use this contract to keep in-code comments/docstrings consistent, useful, and low-noise.

## Intent

- Explain non-obvious behavior and contracts.
- Improve review speed and change safety.
- Avoid comment bloat and line-by-line narration.

## Scope

Apply this to changed code in backend, frontend, infra, and scripts.

## Rules

### 1) Module Context For Complex Touched Files

Add a short module header comment/docstring when a touched file is complex:

- file is `>300` LOC, or
- file has non-obvious orchestration/side effects

Header should briefly state:

- file responsibility
- important boundaries/dependencies
- major side effects or contract constraints

### 2) Function Docs For Public Side-Effecting Behavior

Touched public/exported hooks, services, and commands need concise docstrings/JSDoc when they perform side effects (DB writes, network calls, event/job emission, shared-state mutation).

### 3) Inline Rationale For Non-Obvious Logic

Add inline comments for touched logic that involves:

- transaction boundaries or rollback intent
- concurrency/cancellation/ordering invariants
- retry/backoff decisions
- security assumptions
- external protocol contracts (for example SSE event semantics)

### 4) Keep Comments High-Signal

Do not narrate obvious line-by-line behavior or duplicate symbol names in prose.

### 5) Drift Prevention

If behavior changes, update nearby comments/docstrings in the same PR/commit.

## Enforcement

- Authors: verify changed files meet this contract before commit.
- Reviewers: treat documentation adequacy as pass/fail, not optional polish.
- CI gate: optional; if added later, keep it changed-files-only and heuristic.
