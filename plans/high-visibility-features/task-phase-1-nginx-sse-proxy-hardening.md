## Summary

Fix production SSE delivery so streaming answers render token-by-token in the frontend instead of arriving as one buffered block.

Parent Spec: #38
Depends on: Streaming backend/frontend already shipped

## What this delivers

1. NGINX proxy configuration hardening for SSE (`/api/documents/{id}/query/stream`)
2. Explicit anti-buffering and long-lived stream settings in VM bootstrap config
3. Production verification steps proving first-token latency and incremental token delivery
4. Runbook updates for future debugging of SSE buffering regressions

## Problem Statement

Local streaming works, but production shows full-response flush behavior:
- `meta` timing appears, but answer text renders all at once
- Network responses are `200` but token cadence is lost

Most likely cause: reverse-proxy buffering/compression behavior between client and FastAPI stream response.

## Acceptance Criteria

- [ ] NGINX location handling API traffic disables response buffering for SSE traffic
- [ ] SSE path supports long-lived responses without premature timeout/flush issues
- [ ] Compression does not interfere with incremental token delivery
- [ ] Streaming query in production visibly updates token-by-token (not full-block flush)
- [ ] No regression for non-streaming API endpoints
- [ ] `make backend-verify` still passes
- [ ] Runbook contains explicit SSE troubleshooting checks (headers/logs/proxy config)

## Implementation Notes

- Keep routing contract unchanged (`POST /api/documents/{document_id}/query/stream`).
- Prefer narrow proxy tuning for API/SSE behavior over broad global changes.
- Validate with browser network timing + manual UX check.

## Verification

```bash
make backend-verify
```

Operational checks after deploy:

```bash
curl -N -i https://api.quaero.odysian.dev/api/documents/<id>/query/stream
sudo nginx -t
sudo systemctl reload nginx
```

## Files in scope

- `infra/terraform/scripts/startup.sh.tftpl`
- `docs/GCP_RUNBOOK.md`
- `docs/ARCHITECTURE.md` (if behavior/infra notes change)

## Files explicitly out of scope

- Query endpoint contract changes
- Frontend rendering logic changes (unless needed for verification instrumentation)
- New infrastructure services/load balancers/CDNs

## Labels

`type:task`, `area:backend`
