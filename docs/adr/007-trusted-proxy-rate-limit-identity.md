# ADR-007: Trusted Proxy Boundary for Rate-Limit Identity

**Date:** 2026-03-01
**Status:** Applied
**Branch:** task-24-proxy-aware-rate-limit-identity

---

## Context

### Background
Rate-limit keys for public endpoints are IP-based. In production, traffic may
arrive through one or more reverse proxies that set `X-Forwarded-For`.

### Problem
Using only `request.client.host` behind proxies can collapse many users into a
single proxy IP. Blindly trusting forwarded headers can allow spoofing and
rate-limit bypass.

### Root Cause (if a bug or production incident)
Rate-limit identity derivation had no explicit trusted-proxy boundary and did
not define how to handle forwarded-header chains safely.

---

## Options Considered

### Option A: App-level trusted proxy parsing for rate-limit identity
Parse `X-Forwarded-For` only when the direct peer is in an explicit
`trusted_proxy_ips` list (IP/CIDR). Strip trusted hops right-to-left and use
the first untrusted IP as the client identity.

**Accepted.** Keeps trust boundaries explicit in app config, avoids blind
header trust, and preserves correct client identity through multi-hop proxies.

### Option B: Depend on Uvicorn proxy-header rewriting for all identity
Trust `request.client.host` after Uvicorn proxy handling and rely on runtime
`--forwarded-allow-ips` for security.

**Rejected.** Correctness and spoof-safety would depend entirely on runtime
flags; misconfiguration can silently widen trust.

---

## Decision

1. Added `trusted_proxy_ips` configuration (IP/CIDR list) for backend trust
   boundaries.
2. Updated rate-limit IP derivation to trust forwarded headers only when the
   direct peer is trusted.
3. Implemented right-to-left trusted-hop stripping for `X-Forwarded-For`.
4. Preserved existing auth-first behavior for `get_user_or_ip_key` (user ID key
   when token is valid, IP fallback otherwise).
5. Added regression tests for non-proxied behavior, trusted-proxy behavior, and
   spoofing resistance.

---

## Consequences

- Deployments behind proxies must set `trusted_proxy_ips` correctly, otherwise
  limits fall back to proxy peer IPs.
- Forwarded-header spoofing from untrusted direct peers does not alter
  rate-limit identity.
- Behavior remains backward-compatible for authenticated endpoints that already
  key on `user:<id>`.
- Runtime proxy settings should avoid broad trust (for example wildcard
  forwarded-allow lists), because this ADR assumes direct-peer trust is
  deliberate and explicit.
