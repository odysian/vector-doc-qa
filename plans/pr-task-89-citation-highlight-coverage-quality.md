## Summary
- improve citation snippet matching to choose the best contiguous phrase coverage instead of returning the first short anchor window
- keep robust-match guardrails so weak overlaps still fall back to page-level highlight behavior
- add frontend tests for coverage selection, weak-overlap fallback, delayed text-layer retries, and same-page retrigger behavior

## Verification
- `make frontend-verify`

Closes #89
