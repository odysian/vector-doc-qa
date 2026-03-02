## Goal
Fail closed on unsafe runtime configuration defaults so production cannot boot with dev-grade secrets/credentials.
Default: this Task should represent the entire feature end-to-end unless split criteria apply.

## Scope
**In:**
- Add startup validation for critical security config (`SECRET_KEY`, DB URL patterns, other sensitive defaults).
- Distinguish dev/local behavior from production behavior with explicit environment checks.
- Add tests for config validation outcomes.

**Out:**
- Full secret management platform migration.
- Refactoring all settings fields.

## Implementation notes
- Parent Spec: #19
- Validation should be explicit and actionable (clear error messages, fail fast).

## Decision locks (backend-coupled only)
- [ ] Locked: Environment detection policy for strict validation enforcement.
- [ ] Locked: Exact forbidden default patterns and enforcement behavior.

## Acceptance criteria
- [ ] Production-like startup fails when critical secrets/DB config are unsafe defaults.
- [ ] Local/dev workflow remains usable with intentional non-production settings.
- [ ] Config validation behavior is covered by tests.
- [ ] Documentation reflects required secure env vars.

## Verification
```bash
make backend-verify
cd backend && .venv/bin/pytest -v tests/test_auth.py
```

## PR checklist
- [ ] PR references this issue (`Closes #...`)
- [ ] Docs updated if needed (`docs/ARCHITECTURE.md`, `docs/PATTERNS.md`, `docs/REVIEW_CHECKLIST.md`, `docs/ISSUES_WORKFLOW.md`, `TESTPLAN.md`, `docs/adr/`)
- [ ] Tests added/updated where needed
