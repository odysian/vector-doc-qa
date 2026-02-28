# Codebase Audit Report

**Date:** 2026-02-28  
**Audited areas:** backend, frontend, infra, CI/build paths  
**Focus:** security, abstraction quality, code smells, future technical debt

## Execution Tracking

- Parent Spec: [#19](https://github.com/odysian/vector-doc-qa/issues/19) (`OPEN`)
- Completed: Task [#20](https://github.com/odysian/vector-doc-qa/issues/20) merged via PR [#27](https://github.com/odysian/vector-doc-qa/pull/27) on 2026-02-28.
- Remaining P1/P0 items continue under Task issues linked to Spec #19.

## Verification/Signals Collected

- `make backend-verify` passed (`ruff`, `mypy`, `pytest`, `bandit -ll`) with 86 tests passing.
- `make frontend-verify` failed in this environment because Next.js font fetching requires external network access.
- Manual source review across auth/session, document processing, search/query, worker, infra Terraform, and frontend API abstractions.

## External Validation (Claude Review)

- Independent review confirmed **all seven P0/P1 findings** as accurate against current source.
- Review outcome: **7/7 confirmed** (`P0-1`, `P1-2`, `P1-3`, `P1-4`, `P1-5`, `P1-6`, `P1-18`).
- Notable implementation clarifications captured in task docs:
  - Task `#21`: resolve refresh atomicity and helper transaction-boundary behavior together.
  - Task `#22`: make rollback → failed-status persistence transaction mechanics explicit.
  - Task `#23`: lock input validation ownership (callee contract) before implementation.

## Priority Summary

| Priority | Count | Theme |
|---|---:|---|
| P0 | 1 | Session-token confidentiality |
| P1 | 6 | Auth race conditions, data integrity, insecure defaults |
| P2 | 12 | Scalability/perf debt, leakage, maintainability |
| P3 | 4 | DX/docs/testing hygiene |

## Overlap With `backend-fixes-spec.md`

- **Fix 1 (async timeout)**: already implemented in current code (`run_with_timeout_async` + async PDF extraction).
- **Fix 2 (duplicate chunks on retry)**: covered by audit item **P1-3**.
- **Fix 3 (embedding/chunk misalignment)**: added as audit item **P1-18**.
- **Fix 4 (singleton API clients)**: added as audit item **P2-21**.
- **Fix 5 (transaction boundary in `validate_refresh_token`)**: added as audit item **P2-19**.
- **Fix 6 (`utcnow` vs aware UTC)**: covered by audit item **P2-12**.
- **Fix 7 (health endpoint path leak)**: added as audit item **P2-20**.
- **Fix 8 (empty `.where()`)**: not reproducible in current code; appears already cleaned up.

---

## P0 (Critical)

### 1) Tokens are returned in login/refresh JSON bodies despite cookie auth
- **Category:** Security
- **Severity:** Critical
- **Priority:** P0
- **Evidence:**
  - `backend/app/api/auth.py:68-70,93,137-140`
  - `frontend/lib/api.types.ts:30-35`
- **Why this matters:**
  - `access_token` and `refresh_token` become readable by JavaScript and any XSS payload, negating the main protection value of httpOnly cookies.
  - Token exfiltration enables long-lived account takeover outside the browser session.
- **Recommendation:**
  - Stop returning `access_token`/`refresh_token` in JSON for browser flows.
  - Return only `csrf_token` + metadata.
  - If legacy API clients must be supported, split into explicit legacy endpoints or conditional response mode behind an allowlist/flag.

---

## P1 (High)

### 2) Refresh-token rotation has a race window
- **Category:** Security / Correctness
- **Severity:** High
- **Priority:** P1
- **Evidence:** `backend/app/api/auth.py:121-133`, `backend/app/core/security.py:105-121`
- **Why this matters:**
  - Concurrent refresh requests can both validate the same token before delete/commit, potentially issuing multiple fresh tokens from one consumed token.
- **Recommendation:**
  - Make rotation atomic with row-level locking (`SELECT ... FOR UPDATE`) or a single conditional `DELETE ... RETURNING` and only issue new token if one row was deleted.

### 3) Failed processing can persist partial chunk rows; retries can duplicate data
- **Category:** Correctness / Technical debt
- **Severity:** High
- **Priority:** P1
- **Evidence:** `backend/app/services/document_service.py:62-95`
- **Why this matters:**
  - On errors after `flush()`, exception handler commits status/error without rollback, which may persist partial chunks.
  - Subsequent retries append new chunks without cleanup, causing duplicate/misaligned chunk sets and degraded retrieval quality.
- **Recommendation:**
  - Use explicit transaction boundaries: rollback work unit on failure, then mark document failed in a separate transaction.
  - Before retry processing, remove prior chunks for the document (or enforce idempotent rebuild semantics).

### 4) Insecure runtime defaults in config can become production foot-guns
- **Category:** Security
- **Severity:** High
- **Priority:** P1
- **Evidence:** `backend/app/config.py:15-23`
- **Why this matters:**
  - Hardcoded `secret_key` fallback and default DB credentials are dangerous if env configuration is incomplete.
- **Recommendation:**
  - Fail fast on startup when `SECRET_KEY`/DB URL are missing or look like known dev defaults in non-dev environments.

### 5) Infra defaults are permissive (SSH open world, broad SA scope, secure boot disabled)
- **Category:** Security / Infra hardening
- **Severity:** High
- **Priority:** P1
- **Evidence:**
  - `infra/terraform/variables.tf:80-84` (`0.0.0.0/0` SSH default)
  - `infra/terraform/main.tf:120-123` (`cloud-platform` scope)
  - `infra/terraform/main.tf:125-127` (secure boot disabled)
- **Why this matters:**
  - Expands attack surface and blast radius if VM/SSH credentials are compromised.
- **Recommendation:**
  - Remove public SSH default; require explicit restricted CIDRs.
  - Reduce service account scopes/roles to least privilege.
  - Enable secure boot unless blocked by a documented compatibility requirement.

### 6) Rate limiting likely sees proxy IP, not real client IP
- **Category:** Security / Availability
- **Severity:** High
- **Priority:** P1
- **Evidence:**
  - `backend/app/utils/rate_limit.py:18-21` (uses `request.client.host` only)
  - `backend/run-web-and-worker.sh:8` (uvicorn launched without proxy trust flags)
- **Why this matters:**
  - Behind NGINX, all requests may share one apparent IP, causing noisy-neighbor lockouts or ineffective rate controls.
- **Recommendation:**
  - Enable trusted proxy headers at app server layer and/or extract validated `X-Forwarded-For` with explicit trusted proxy controls.

### 18) Embedding batch filtering can misalign chunks and embeddings
- **Category:** Correctness / Retrieval quality
- **Severity:** High
- **Priority:** P1
- **Evidence:** `backend/app/services/embedding_service.py:45-66`, `backend/app/services/document_service.py:74-79`
- **Why this matters:**
  - `generate_embeddings_batch` filters `valid_texts`, so output length/order is based on filtered input.
  - Caller assigns embeddings by `zip(chunk_objects, embeddings)`, which can silently attach wrong vectors to wrong chunks if any empty string slips in.
- **Recommendation:**
  - Remove filtering in `generate_embeddings_batch`; validate all inputs are non-empty and fail fast if not.
  - Keep a strict invariant: output embeddings length/order must match original `texts` length/order.

---

## P2 (Medium)

### 7) Sensitive prompt/query text is logged at info level
- **Category:** Security / Privacy
- **Severity:** Medium
- **Priority:** P2
- **Evidence:**
  - `backend/app/api/documents.py:345`
  - `backend/app/services/search_service.py:15`
  - `backend/app/services/anthropic_service.py:56`
  - `backend/app/main.py:16` (global DEBUG logging)
- **Why this matters:**
  - User queries can contain confidential document details and PII; logging them increases exposure and retention risk.
- **Recommendation:**
  - Remove raw query text from logs; log IDs/lengths only.
  - Default production logging to INFO/WARN without debug payload details.

### 8) Internal exception strings are returned to clients
- **Category:** Security / API hygiene
- **Severity:** Medium
- **Priority:** P2
- **Evidence:**
  - `backend/app/api/documents.py:324-325,421`
  - `backend/app/utils/file_utils.py:137-138`
- **Why this matters:**
  - Exposes internal stack/component messages and makes exploitation/recon easier.
- **Recommendation:**
  - Return generic client-safe errors; log full exception server-side with correlation IDs.

### 9) Query/search endpoints eagerly load all chunks before semantic search
- **Category:** Performance / Abstraction
- **Severity:** Medium
- **Priority:** P2
- **Evidence:** `backend/app/api/documents.py:283-290,349-356`
- **Why this matters:**
  - Loads full chunk payloads into memory just to check existence/status; scales poorly with large docs.
- **Recommendation:**
  - Replace eager load with lightweight existence/count query (`SELECT 1`/`COUNT`) and keep search query separate.

### 10) No vector ANN index on embeddings
- **Category:** Scalability / Technical debt
- **Severity:** Medium
- **Priority:** P2
- **Evidence:** `backend/alembic/versions/49b4e1e72658_initial_migration_in_quaero_schema.py:148-163` (no IVFFLAT/HNSW index)
- **Why this matters:**
  - Similarity search will degrade as chunk count grows, creating latency/cost bottlenecks.
- **Recommendation:**
  - Add pgvector index strategy (IVFFLAT/HNSW) with tuned parameters and migration.

### 11) Message `sources` stores full chunk text per response
- **Category:** Data growth / Privacy
- **Severity:** Medium
- **Priority:** P2
- **Evidence:**
  - `backend/app/api/documents.py:397-404`
  - `backend/app/models/message.py:31-33`
- **Why this matters:**
  - Repeatedly duplicating chunk content inflates DB size and retains sensitive excerpts in chat history indefinitely.
- **Recommendation:**
  - Store chunk IDs + similarity + optional short excerpt hash/preview, and resolve full text on read when needed.

### 12) Time handling is inconsistent (naive timestamps + UTC comparisons)
- **Category:** Correctness / Technical debt
- **Severity:** Medium
- **Priority:** P2
- **Evidence:**
  - `backend/app/models/base.py:49-50,85`
  - `backend/app/models/message.py:35`
  - `backend/alembic/versions/49b4e1e72658_initial_migration_in_quaero_schema.py:97-99,140,173`
- **Why this matters:**
  - Mixed naive/aware timestamps are a classic source of subtle bugs in retention windows and worker recovery logic.
- **Recommendation:**
  - Standardize on timezone-aware UTC (`TIMESTAMPTZ`) across models/migrations.

### 13) Stale-processing recovery uses `uploaded_at`, not processing start/update time
- **Category:** Correctness
- **Severity:** Medium
- **Priority:** P2
- **Evidence:** `backend/app/workers/arq_worker.py:21-28`
- **Why this matters:**
  - Old documents retried today can be incorrectly marked stale during startup because upload time is unrelated to current processing attempt.
- **Recommendation:**
  - Track `processing_started_at` (or `updated_at`) and use that for stale detection.

### 14) Frontend data layer owns navigation side effects
- **Category:** Abstraction / Maintainability
- **Severity:** Medium
- **Priority:** P2
- **Evidence:** `frontend/lib/api.ts:171-175`
- **Why this matters:**
  - Hard redirect inside API utility couples transport layer with routing, making tests and reuse harder.
- **Recommendation:**
  - Return typed auth/session errors to callers; handle redirects in page/layout/auth boundary.

### 19) `validate_refresh_token` commits inside a shared helper
- **Category:** Transaction integrity / Abstraction
- **Severity:** Medium
- **Priority:** P2
- **Evidence:** `backend/app/core/security.py:117-121`
- **Why this matters:**
  - Helper-level commits break caller-owned transaction boundaries and make refresh/logout flows harder to reason about atomically.
- **Recommendation:**
  - Remove commit from helper and let endpoint/service layer own commit/rollback decisions.

### 20) Health endpoint discloses absolute filesystem path
- **Category:** Security / Information disclosure
- **Severity:** Medium
- **Priority:** P2
- **Evidence:** `backend/app/main.py:104,113`
- **Why this matters:**
  - Public health responses should not expose internal filesystem layout (`upload_dir`), which aids reconnaissance.
- **Recommendation:**
  - Remove `upload_dir` from `/health` response payloads.

### 21) AI clients are instantiated per request instead of reused
- **Category:** Performance / Resource efficiency
- **Severity:** Medium
- **Priority:** P2
- **Evidence:** `backend/app/services/embedding_service.py:17`, `backend/app/services/embedding_service.py:53`, `backend/app/services/anthropic_service.py:62`
- **Why this matters:**
  - Recreating clients repeatedly adds avoidable connection/TLS overhead under load.
- **Recommendation:**
  - Use lazy module-level singleton clients for OpenAI and Anthropic SDKs.

### 22) Chunking lacks explicit guardrails for invalid config values
- **Category:** Correctness hardening
- **Severity:** Medium
- **Priority:** P2
- **Evidence:** `backend/app/utils/pdf_utils.py:99-102,115-145`
- **Why this matters:**
  - If `chunk_size <= 0` or `overlap >= chunk_size` (misconfiguration), progression logic can degrade badly or become non-progressing in edge cases.
- **Recommendation:**
  - Validate and enforce `chunk_size > 0`, `overlap >= 0`, and `overlap < chunk_size` before entering the loop.

---

## P3 (Low)

### 15) Frontend build is brittle in restricted/offline environments due Google font fetch
- **Category:** Build reliability
- **Severity:** Low
- **Priority:** P3
- **Evidence:** `frontend/app/layout.tsx:5-23` and `make frontend-verify` failure in this environment.
- **Why this matters:**
  - CI or isolated environments without outbound internet can fail builds unexpectedly.
- **Recommendation:**
  - Self-host fonts (`next/font/local`) or provide fallback strategy for restricted build environments.

### 16) Async pytest configuration drift warning
- **Category:** Test maintainability
- **Severity:** Low
- **Priority:** P3
- **Evidence:** warning from `pytest-asyncio` during `make backend-verify`; current `backend/pytest.ini:6-8` lacks `asyncio_default_fixture_loop_scope`.
- **Why this matters:**
  - Future pytest-asyncio defaults may change behavior unexpectedly.
- **Recommendation:**
  - Pin explicit fixture loop scope in `pytest.ini`.

### 17) Documentation/config drift on access token expiry
- **Category:** Process / Technical debt
- **Severity:** Low
- **Priority:** P3
- **Evidence:**
  - `AGENTS.md:70` says `access_token_expire_minutes=0`
  - `backend/app/config.py:20` sets `30`
- **Why this matters:**
  - Conflicting operational assumptions increase incident risk and onboarding confusion.
- **Recommendation:**
  - Align docs and code, and capture final policy in ADR/docs.

### 23) Optional defensive clamp for fallback `end` assignment in chunking
- **Category:** Code robustness / Readability
- **Severity:** Low
- **Priority:** P3
- **Evidence:** `backend/app/utils/pdf_utils.py:126-127`
- **Why this matters:**
  - Current control flow is effectively safe, but explicitly clamping `end = min(start + chunk_size, len(text))` in that fallback branch removes ambiguity for future maintainers/ports.
- **Recommendation:**
  - Add explicit cap in the fallback branch as a small hardening/readability improvement.

---

## Suggested Next Task Sequence

1. **P0/P1 auth hardening pass**: remove token bodies, fix refresh race, add regression tests for concurrent refresh.
2. **Document processing and embedding integrity pass**: transactional cleanup semantics, retry idempotency, embedding-order invariants.
3. **Infra hardening pass**: SSH CIDR tightening, secure boot decision, least-privilege service account.
4. **Runtime safety/perf pass**: singleton AI clients, `/health` response minimization, remove helper-level commits, logging/error hardening.
5. **Retrieval scalability + chunk hardening pass**: vector index migration, remove eager chunk loading, chunk config validation and fallback clamp.
6. **Hygiene pass**: pytest config/doc consistency and residual low-priority cleanup.
