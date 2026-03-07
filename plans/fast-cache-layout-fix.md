## Fast Kickoff: Backend Cache Layout Fix

## Scope
- Keep backend tool caches in `backend/` only.
- Eliminate accidental nested cache output at `backend/backend/`.
- Touch only cache configuration and backend verification command flags.

## Checklist
- [x] Update backend verify commands to use explicit cache directories relative to `backend/`.
- [x] Align tool configuration so direct backend commands also write caches under `backend/`.
- [x] Remove generated nested cache folder `backend/backend/`.
- [x] Run backend verification once.

## Verification
```bash
make backend-verify
```

## Suggested Commit Message
`fix: normalize backend cache directories`
