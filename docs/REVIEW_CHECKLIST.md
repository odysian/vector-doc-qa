# REVIEW_CHECKLIST.md

Post-implementation verification checklist. Run through after every feature before committing.

---

## Security

- [ ] All user input validated through Pydantic schemas
- [ ] String fields have explicit max_length constraints
- [ ] File uploads validated by magic bytes, not just extension
- [ ] File size checked during streaming upload (not after)
- [ ] File operations go through storage service abstraction (no direct route/service filesystem writes)
- [ ] Every endpoint is authenticated unless explicitly documented as public
- [ ] User can only access their own data (ownership check on every query)
- [ ] No secrets in code, logs, or error messages
- [ ] Rate limiting applied to endpoint (appropriate limit for the action)
- [ ] CORS restricted to specific frontend origin (no wildcard in production)
- [ ] Passwords hashed with Argon2 (never stored plaintext)
- [ ] JWT tokens validated on every protected request
- [ ] Login/refresh response bodies do not expose `access_token` or `refresh_token`
- [ ] No SQL string interpolation or f-strings in queries
- [ ] Error messages don't expose internals (stack traces, DB errors, file paths)
- [ ] Background job endpoints are non-blocking (no long-running work in request handlers)
- [ ] Job deduplication is enforced for repeat enqueue requests (stable job IDs)

## Performance

- [ ] No N+1 queries (check any query that loads related data)
- [ ] Indexes exist on columns used in WHERE clauses and JOINs
- [ ] Embedding generation uses batch API (not one-at-a-time)
- [ ] Large file operations are streamed (not loaded entirely into memory)
- [ ] Production storage backend is configured correctly (`STORAGE_BACKEND=gcs`, bucket/IAM validated)
- [ ] Frontend doesn't re-fetch data unnecessarily
- [ ] Polling uses lightweight status endpoints and stops after terminal states

## Code Quality

- [ ] Error handling uses HTTPException with descriptive detail messages
- [ ] Type hints on all function signatures (Python)
- [ ] TypeScript strict mode — no `any` types
- [ ] Constants in `constants.py`, not magic numbers in code
- [ ] Consistent with patterns in PATTERNS.md
- [ ] No dead code, commented-out code, or debug print statements
- [ ] No `console.log` left in frontend code
- [ ] Backend layering is preserved (`api -> services -> repositories`, `services -> integration services`) with no cross-layer shortcuts
- [ ] Public services are not pass-through-only wrappers; they add orchestration/validation/policy value
- [ ] Document pipeline parity holds: endpoint orchestration in command service / query service, `document_service.py` remains worker-focused
- [ ] Changed complex files meet module context requirements from `docs/CODE_COMMENTING_CONTRACT.md`
- [ ] Touched public/exported side-effecting behavior has concise docstrings/JSDoc
- [ ] Non-obvious transaction/concurrency/retry/protocol logic has rationale comments where needed
- [ ] No stale or obvious narration comments were introduced

## Database

- [ ] Schema change has an Alembic migration
- [ ] Migration is reversible (downgrade works)
- [ ] Foreign keys specify ON DELETE behavior where needed
- [ ] New tables use `quaero` schema
- [ ] No migration files were edited after being applied

## Tests

- [ ] Happy path covered
- [ ] At least one error case covered
- [ ] At least one edge case covered
- [ ] Assertions are specific (check response body, not just status code)
- [ ] Test names describe the scenario and expected outcome
- [ ] Async job status transitions are covered (`pending` -> `processing` -> terminal state)

## Workflow Reliability

- [ ] GH write actions used `scripts/gh_preflight.sh` and `--body-file`
- [ ] PR creation used `scripts/create_pr.sh` with fail-fast fallback order (exact command once -> elevated exact command -> manual one-liner + URL)
- [ ] Reviewer verdict recorded (`APPROVED` or `ACTIONABLE`)
- [ ] Review findings (if actionable) include severity + file/path:line + required fix
- [ ] Review stayed lean (no environment triage loops, no worktree setup, no unnecessary broad verification reruns)

## Documentation

- [ ] ARCHITECTURE.md updated if schema, endpoints, or infrastructure changed
- [ ] PATTERNS.md updated if new convention introduced
- [ ] ISSUES_WORKFLOW.md updated if issue/DoR/DoD policy changed
- [ ] TESTPLAN.md updated before writing new tests

---

_Add project-specific checks as they're discovered during reviews._
