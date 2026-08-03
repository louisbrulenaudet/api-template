.PHONY: docker-check docker-check-build docker-config docker-build docker-rebuild \
	docker-start docker-stop docker-restart docker-logs docker-clean docker-run-dev \
	docker-run-dev-tunnel docker-tunnel-logs docker-tunnel-stop

docker-check: ## Verify Docker installation and configuration
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "❌ Docker is not installed! Please install it first."; \
		exit 1; \
	elif ! docker compose version >/dev/null 2>&1; then \
		echo "❌ Docker Compose plugin is not installed! Please install it first."; \
		exit 1; \
	else \
		echo "✅ Docker and Docker Compose are installed"; \
	fi

docker-check-build: ## Run Docker's build checks without building (Dockerfile sets check=error=true)
	@echo "🔍 Running Docker build checks..."
	docker build --check .

docker-config: ## Validate the Compose file, with and without the tunnel profile
	@echo "🔍 Validating Compose..."
	$(COMPOSE) config -q
	@echo "🔍 Validating Compose (tunnel profile)..."
	$(COMPOSE) --profile $(TUNNEL_PROFILE) config -q
	@echo "✅ Compose configuration is valid"

docker-build: ## Create application containers
	@echo "🔨 Building application containers..."
	$(COMPOSE) build

docker-rebuild: ## Rebuild containers with fresh configuration
	@echo "🔨 Performing complete rebuild..."
	$(COMPOSE) down --volumes --remove-orphans
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

docker-start: ## Launch application services
	@echo "🚀 Starting application services..."
	$(COMPOSE) up -d

docker-stop: ## Stop all running services
	@echo "🛑 Stopping application services..."
	$(COMPOSE) down

docker-restart: ## Restart all application services
	@echo "🔄 Restarting services..."
	$(COMPOSE) down && $(COMPOSE) up -d

docker-logs: ## Display container logs
	@echo "📜 Showing application logs..."
	$(COMPOSE) logs -f

docker-clean: ## Remove all containers and volumes
	@echo "🧹 Cleaning up resources..."
	$(COMPOSE) down --volumes --remove-orphans

docker-run-dev: ## Start dev server with Compose watch (sync app/, rebuild on dep changes)
	@echo "🚀 Starting development server..."
	$(COMPOSE) up --watch $(APP_SERVICE)

docker-run-dev-tunnel: ## Start dev server (watch) + Cloudflare Tunnel (opt-in profile)
	@echo "🌐 Starting dev server + Cloudflare Tunnel..."
	$(COMPOSE) --profile $(TUNNEL_PROFILE) up --watch $(APP_SERVICE) $(TUNNEL_SERVICE)

docker-tunnel-logs: ## Follow Cloudflare Tunnel logs
	@echo "📜 Following Cloudflare Tunnel logs..."
	$(COMPOSE) --profile $(TUNNEL_PROFILE) logs -f $(TUNNEL_SERVICE)

docker-tunnel-stop: ## Stop tunnel (does not remove app files)
	@echo "🛑 Stopping Cloudflare Tunnel..."
	$(COMPOSE) --profile $(TUNNEL_PROFILE) stop $(TUNNEL_SERVICE)
