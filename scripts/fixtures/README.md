# Fixture Files

`demo_seed_data.json` is generated data for demo-account startup seeding.

- Do not hand-edit this file.
- Regenerate with:
  - `backend/.venv/bin/python scripts/export_demo_fixtures.py --user-id <id>`
  - add `--include-file-bytes` if you want embedded PDF bytes in the fixture.
- Runtime seed source is `backend/scripts/fixtures/demo_seed_data.json`.
- This file is a legacy mirror for operator convenience (`scp`, manual inspection).
- The export script writes compact deterministic JSON to both paths to reduce diff noise in PRs.
