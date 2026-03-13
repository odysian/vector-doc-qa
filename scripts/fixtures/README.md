# Fixture Files

This directory no longer stores the demo seed fixture payload.

- Runtime seed source: `backend/scripts/fixtures/demo_seed_data.json`.
- Regenerate with:
  - `backend/.venv/bin/python scripts/export_demo_fixtures.py --user-id <id>`
  - add `--include-file-bytes` to embed PDF bytes in the fixture.
