.PHONY: help install dev test test-unit test-integration test-e2e test-coverage test-quick lint lint-fix format quality ci ui clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime dependencies
	uv sync

dev: ## Install with dev + test + ui groups
	uv sync --group dev --group test --group ui

test: ## Run the full test suite
	uv run pytest

test-unit: ## Run unit tests only (fast)
	uv run pytest -m unit

test-integration: ## Run integration tests (may hit network)
	uv run pytest -m integration -n auto

test-e2e: ## Run end-to-end pipeline tests
	uv run pytest -m e2e

test-coverage: ## Run tests with coverage report
	uv run pytest --cov=little_warren --cov-report=term-missing

test-quick: ## Fail-fast unit tests
	uv run pytest tests/unit/ -x -v

lint: ## Check lint rules
	uv run ruff check

lint-fix: ## Fix lint issues
	uv run ruff check --fix

format: ## Format code
	uv run ruff format

quality: lint format ## Lint + format (run before committing)

ci: ## Full CI loop: install, quality, test
	$(MAKE) dev
	$(MAKE) quality
	$(MAKE) test

ui: ## Launch the Streamlit analysis UI
	uv run streamlit run src/little_warren/infrastructure/ui/app.py

clean: ## Remove caches and build artifacts
	find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -not -path "./.venv/*" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage *.egg-info
