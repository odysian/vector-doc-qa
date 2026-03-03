.PHONY: help verify backend-verify frontend-verify

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

verify: backend-verify frontend-verify ## Run all verification checks

backend-verify: ## Lint, type-check, test, and security-scan the backend
	@test -x backend/.venv/bin/ruff || (echo "Missing backend/.venv. Run: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" && exit 1)
	@cd backend && \
		.venv/bin/ruff check . && \
		.venv/bin/mypy . --ignore-missing-imports --explicit-package-bases && \
		.venv/bin/pytest -v && \
		.venv/bin/bandit -r app/ -ll

frontend-verify: ## Type-check, test, lint, and build the frontend
	@cd frontend && \
		npx tsc --noEmit && \
		npm test && \
		npm run lint && \
		npm run build
