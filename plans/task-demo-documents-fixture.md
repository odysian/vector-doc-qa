## Summary

Generate the 3 demo PDF documents, upload/process them, export the fixture, and add the Tell-Tale Heart eval case.

Parent Spec: #79

**Depends on:** Task 1 (demo seed infrastructure) for the export script.

## Scope

**In scope:**
- Create 3 PDF documents:
  1. `acme-q4-report.pdf` — Q4 earnings report (contains: "Q4 revenue", "$5M", "customer growth", "12%")
  2. `security-policy-2025.pdf` — security policy (contains: "password", "rotation", "90 days")
  3. `the-tell-tale-heart.pdf` — Poe short story
- Upload and process all 3 through the app
- Run `export_demo_fixtures.py` to generate `scripts/fixtures/demo_seed_data.json`
- Add eval case `case-004-tell-tale-heart` to `scripts/fixtures/mini_eval_cases.json`
- Verify eval harness passes all 4 cases
- Commit fixture JSON and updated eval cases

**Out of scope:**
- Frontend changes
- Backend code changes (handled in Task 1)

## Files

- `scripts/fixtures/demo_seed_data.json` (new, generated)
- `scripts/fixtures/mini_eval_cases.json` (add case-004)

## Acceptance Criteria

- [ ] 3 demo PDFs created with expected fact content
- [ ] Fixture JSON committed with documents + chunks + embeddings
- [ ] Eval case `case-004-tell-tale-heart` added with expected_facts
- [ ] `make backend-mini-eval` passes all 4 cases
- [ ] App startup with empty DB creates demo user with 3 completed documents

## Verification

```bash
make backend-mini-eval
```

## Notes

This task is partially manual (PDF creation, upload, processing) and partially scripted (fixture export). The PDFs themselves don't need to be committed — only the exported fixture JSON matters for seeding.
