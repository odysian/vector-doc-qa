## Summary
- normalize backend cache paths so lint/type/test cache artifacts stay under `backend/`
- prevent accidental nested cache directory creation at `backend/backend/`
- update backend verify commands to pass explicit cache dirs

## Changes
- `Makefile`: pass explicit cache flags for ruff/mypy/pytest in `backend-verify`
- `pyproject.toml`: use local cache paths (`.ruff_cache`, `.mypy_cache`, `.pytest_cache`)
- `plans/fast-cache-layout-fix.md`: fast-mode kickoff checklist

## Verification
- `make backend-verify` (pass)
