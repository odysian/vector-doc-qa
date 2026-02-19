# REVIEW_CHECKLIST.md

Post-implementation verification checklist. Run through after every feature before committing.

---

## Security

- [ ] All user input validated through Pydantic schemas
- [ ] String fields have explicit max_length constraints
- [ ] File uploads validated by magic bytes, not just extension
- [ ] File size checked during streaming upload (not after)
- [ ] Every endpoint is authenticated unless explicitly documented as public
- [ ] User can only access their own data (ownership check on every query)
- [ ] No secrets in code, logs, or error messages
- [ ] Rate limiting applied to endpoint (appropriate limit for the action)
- [ ] CORS restricted to specific frontend origin (no wildcard in production)
- [ ] Passwords hashed with Argon2 (never stored plaintext)
- [ ] JWT tokens validated on every protected request
- [ ] No SQL string interpolation or f-strings in queries
- [ ] Error messages don't expose internals (stack traces, DB errors, file paths)
- [ ] Background job endpoints are non-blocking (no long-running work in request handlers)
- [ ] Job deduplication is enforced for repeat enqueue requests (stable job IDs)

## Performance

- [ ] No N+1 queries (check any query that loads related data)
- [ ] Indexes exist on columns used in WHERE clauses and JOINs
- [ ] Embedding generation uses batch API (not one-at-a-time)
- [ ] Large file operations are streamed (not loaded entirely into memory)
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

## Documentation

- [ ] ARCHITECTURE.md updated if schema, endpoints, or infrastructure changed
- [ ] PATTERNS.md updated if new convention introduced
- [ ] TESTPLAN.md updated before writing new tests

---

_Add project-specific checks as they're discovered during reviews._
