.PHONY: help verify backend-verify frontend-verify

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

verify: backend-verify frontend-verify ## Run all verification checks

backend-verify: ## Lint, type-check, test, and security-scan the backend
	@cd backend && \
		ruff check . && \
		mypy . --ignore-missing-imports --explicit-package-bases && \
		pytest -v && \
		bandit -r app/ -ll

frontend-verify: ## Type-check, lint, and build the frontend
	@cd frontend && \
		npx tsc --noEmit && \
		npm run lint && \
		npm run build
