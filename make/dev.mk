.PHONY: dev prod test sync sync-all check format type-check update pre-commit clean-venv install lock

dev: ## Start development server
	@echo "🚀 Starting development server..."
	uv run fastapi dev $(APP) --port $(DEV_PORT)

prod: ## Start production server
	@echo "🚀 Starting production server..."
	uv run fastapi run $(APP) --port $(PORT)

test: ## Run tests
	@echo "🧪 Running tests..."
	uv run pytest

sync: ## Install/sync dependencies (uv.lock + dev group; matches CI)
	@echo "📦 Syncing project environment..."
	uv sync

sync-all: ## Sync with all optional extras from pyproject.toml
	@echo "📦 Syncing project environment with all extras..."
	uv sync --all-extras

install: sync ## Install project dependencies (alias for sync)

lock: ## Lock project dependencies
	@echo "📦 Locking project dependencies..."
	uv lock

check: ## Run code quality checks
	@echo "🔍 Running code analysis..."
	uv run ruff check .

format: ## Format source code
	@echo "🔧 Formatting code..."
	uv run ruff format .
	uv run ruff check . --fix

type-check: ## Type check the source code
	@echo "🔍 Type checking the source code..."
	uv run ty check .

update: ## Update locked dependencies and apply
	@echo "📡 Upgrading dependencies..."
	uv lock --upgrade
	uv sync
	@echo "✅ Dependencies updated successfully"

clean-venv: ## Remove local Python virtual environment (.venv)
	@echo "🧹 Removing virtual environment..."
	rm -rf .venv

pre-commit: ## Run pre-commit checks
	uv run pre-commit run --all-files
