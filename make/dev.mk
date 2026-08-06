.PHONY: dev prod test test-cov sync sync-all check format type-check ci ci-check update pre-commit clean-venv install lock export-requirements check-requirements rules-check

# Convention: every routine command is `--frozen`; the lock changes only on explicit re-locking
# (quality/uv-dependencies).

dev: ## Start development server
	@echo "🚀 Starting development server..."
	uv run --frozen fastapi dev $(APP) --port $(DEV_PORT)

# Mirrors the `runtime` stage's CMD, with one deliberate difference: no `--host 0.0.0.0`, so it stays
# on loopback. FORWARDED_ALLOW_IPS is likewise unset here (ops/makefile).
prod: ## Start production server (uvicorn, as the Docker `runtime` stage runs it, but bound to loopback)
	@echo "🚀 Starting production server..."
	uv run --frozen uvicorn $(ASGI_APP) --port $(PORT) --no-server-header --timeout-graceful-shutdown 25

test: ## Run tests
	@echo "🧪 Running tests..."
	uv run --frozen pytest

test-cov: ## Run tests with coverage (writes .coverage + htmlcov/)
	@echo "🧪 Running tests with coverage..."
	uv run --frozen pytest --cov=app --cov-report=term-missing --cov-report=html

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
	uv run --frozen ty check

ci: format type-check ## Format + lint (Ruff) and type-check (ty); no tests
	@echo "✅ CI gate passed (ruff + ty)"

# The non-mutating mirror of CI's `test` job, in the workflow's own order. Keep the command list
# identical to the workflow's; the one intended difference is no `--output-format github` (ops/ci).
ci-check: sync check-requirements rules-check ## Exactly what CI's `test` job runs; never mutates the tree
	@echo "🔍 Checking formatting (Ruff)..."
	uv run --no-sync ruff format --check .
	@echo "🔍 Linting (Ruff)..."
	uv run --no-sync ruff check .
	@echo "🔍 Type checking (ty)..."
	uv run --no-sync ty check
	@echo "🧪 Running tests..."
	uv run --no-sync pytest
	@echo "✅ CI gate passed (ruff + ty + pytest + requirements export)"

update: ## Upgrade locked dependencies, then install them
	@echo "📡 Upgrading dependencies..."
	uv lock --upgrade
	uv sync --frozen
	@echo "✅ Dependencies updated successfully"

# `--no-dev` so the export is the RUNTIME closure, and re-run after every `make lock`
# (quality/uv-dependencies).
export-requirements: ## Regenerate requirements.txt from uv.lock (runtime closure only; uv.lock stays canonical)
	@echo "📤 Exporting requirements.txt from uv.lock..."
	uv export --frozen --no-dev --no-hashes -o requirements.txt

# The gate for the target above. Writes only to a temp file; `diff -I`, the explicit `mktemp` template
# and the dropped stdout are each load-bearing (ops/makefile).
check-requirements: ## Fail if requirements.txt has drifted from uv.lock
	@echo "🔍 Checking requirements.txt against uv.lock..."
	@tmp="$$(mktemp "$${TMPDIR:-/tmp}/requirements.XXXXXX")" && [ -n "$$tmp" ] || { \
		echo "❌ could not create a temp file"; exit 1; \
	}; \
	trap 'rm -f "$$tmp"' EXIT; \
	uv export --frozen --no-dev --no-hashes -o "$$tmp" >/dev/null || exit 1; \
	diff -u -I '^#  *uv export ' requirements.txt "$$tmp" || { \
		echo "❌ requirements.txt is stale - regenerate with 'make export-requirements'"; \
		exit 1; \
	}; \
	echo "✅ requirements.txt matches uv.lock"

clean-venv: ## Remove local Python virtual environment (.venv)
	@echo "🧹 Removing virtual environment..."
	rm -rf .venv

pre-commit: ## Run pre-commit checks
	uv run --frozen pre-commit run --all-files
