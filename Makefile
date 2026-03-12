.PHONY: help verify backend-verify frontend-verify eval backend-mini-eval infra-cutover-prepare infra-cutover-postcheck

MINI_EVAL_ARGS ?= --user-id 1
CUTOVER_TFVARS ?= envs/prod.tfvars
CUTOVER_HEALTH_URL ?= https://api.quaero.odysian.dev/health
CUTOVER_BASELINE_MIN ?=
CUTOVER_POST_MIN ?=
CUTOVER_OPS_AGENT_GATE ?= false
CUTOVER_PIN_FAMILY ?= false

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

verify: backend-verify frontend-verify ## Run all verification checks

backend-verify: ## Boundary-check, lint, type-check, test, and security-scan the backend
	@bash scripts/check_backend_boundaries.sh
	@test -x backend/.venv/bin/ruff || (echo "Missing backend/.venv. Run: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" && exit 1)
	@cd backend && \
		.venv/bin/ruff check . --cache-dir .ruff_cache && \
		.venv/bin/mypy . --ignore-missing-imports --explicit-package-bases --cache-dir .mypy_cache && \
		.venv/bin/pytest -v -o cache_dir=.pytest_cache && \
		.venv/bin/bandit -r app/ -ll

frontend-verify: ## Type-check, test, lint, and build the frontend
	@cd frontend && \
		npx tsc --noEmit && \
		npm test && \
		npm run lint && \
		npm run build

eval: ## Run mini eval harness and write report artifacts (override with MINI_EVAL_ARGS='...')
	@test -x backend/.venv/bin/python || (echo "Missing backend/.venv. Run: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" && exit 1)
	@cd backend && \
		PYTHONPATH=. .venv/bin/python -m scripts.run_mini_eval \
			--fixture scripts/fixtures/mini_eval_cases.json \
			--output-dir reports/mini_eval \
			$(MINI_EVAL_ARGS)

backend-mini-eval: eval ## Backward-compatible alias for eval

infra-cutover-prepare: ## Cutover prep automation: snapshot + terraform checks/plan + evidence draft
	@bash scripts/infra_cutover.sh prepare \
		--tfvars "$(CUTOVER_TFVARS)" \
		$(if $(filter true TRUE 1 yes YES,$(CUTOVER_PIN_FAMILY)),--pin-image-family,)

infra-cutover-postcheck: ## Cutover postchecks: health gate + optional ops-agent/bootstrap target checks
	@bash scripts/infra_cutover.sh postcheck \
		--health-url "$(CUTOVER_HEALTH_URL)" \
		--tfvars "$(CUTOVER_TFVARS)" \
		$(if $(CUTOVER_BASELINE_MIN),--baseline-min $(CUTOVER_BASELINE_MIN),) \
		$(if $(CUTOVER_POST_MIN),--post-min $(CUTOVER_POST_MIN),) \
		$(if $(filter true TRUE 1 yes YES,$(CUTOVER_OPS_AGENT_GATE)),--ops-agent-gate,)
