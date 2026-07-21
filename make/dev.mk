.PHONY: dev prod test sync sync-all check format type-check ci update pre-commit clean-venv install lock export-requirements

# Convention: routine commands run against uv.lock exactly via `--frozen` (install
# from the lock, never re-resolve). The lock changes ONLY on explicit re-locking
# (`make lock` / `make update` / `uv add`), where the relative `exclude-newer`
# freshness gate is applied. This keeps every other command deterministic.

dev: ## Start development server
	@echo "🚀 Starting development server..."
	uv run --frozen fastapi dev $(APP) --port $(DEV_PORT)

prod: ## Start production server
	@echo "🚀 Starting production server..."
	uv run --frozen fastapi run $(APP) --port $(PORT)

test: ## Run tests
	@echo "🧪 Running tests..."
	uv run --frozen pytest

sync: ## Install from uv.lock exactly (--frozen; dev group included; matches CI)
	@echo "📦 Syncing project environment (frozen)..."
	uv sync --frozen

sync-all: ## Sync every dependency group from uv.lock (--frozen)
	@echo "📦 Syncing project environment with all dependency groups..."
	uv sync --frozen --all-groups

install: sync ## Install project dependencies (alias for sync)

lock: ## Re-resolve and write uv.lock (applies the exclude-newer freshness gate)
	@echo "📦 Locking project dependencies..."
	uv lock

check: ## Run code quality checks
	@echo "🔍 Running code analysis..."
	uv run --frozen ruff check .

format: ## Format source code
	@echo "🔧 Formatting code..."
	uv run --frozen ruff format .
	uv run --frozen ruff check . --fix

type-check: ## Type check the source code
	@echo "🔍 Type checking the source code..."
	uv run --frozen ty check .

ci: format type-check ## Format + lint (Ruff) and type-check (ty); no tests
	@echo "✅ CI gate passed (ruff + ty)"

update: ## Upgrade locked dependencies, then install them
	@echo "📡 Upgrading dependencies..."
	uv lock --upgrade
	uv sync --frozen
	@echo "✅ Dependencies updated successfully"

export-requirements: ## Regenerate requirements.txt from uv.lock (pip-style export; uv.lock stays canonical)
	@echo "📤 Exporting requirements.txt from uv.lock..."
	uv export --frozen --no-hashes -o requirements.txt

clean-venv: ## Remove local Python virtual environment (.venv)
	@echo "🧹 Removing virtual environment..."
	rm -rf .venv

pre-commit: ## Run pre-commit checks
	uv run --frozen pre-commit run --all-files
