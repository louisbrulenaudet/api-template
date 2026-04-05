.PHONY: check-docker docker-build docker-rebuild docker-start docker-stop docker-restart docker-logs docker-clean docker-run-dev docker-run-dev-tunnel docker-tunnel-logs docker-tunnel-stop docker-deploy-prod docker-logs-prod

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

docker-build: ## Create application containers
	@echo "🔨 Building application containers..."
	docker compose build

docker-rebuild: ## Rebuild containers with fresh configuration
	@echo "🔨 Performing complete rebuild..."
	docker compose down --volumes --remove-orphans
	docker compose build --no-cache
	docker compose up -d

docker-start: ## Launch application services
	@echo "🚀 Starting application services..."
	docker compose up -d

docker-stop: ## Stop all running services
	@echo "🛑 Stopping application services..."
	docker compose down

docker-restart: ## Restart all application services
	@echo "🔄 Restarting services..."
	docker compose down && docker compose up -d

docker-logs: ## Display container logs
	@echo "📜 Showing application logs..."
	docker compose logs -f

docker-clean: ## Remove all containers and volumes
	@echo "🧹 Cleaning up resources..."
	docker compose down --volumes --remove-orphans

docker-run-dev: ## Start development server with live reload
	@echo "🚀 Starting development server..."
	docker compose up -d app

docker-run-dev-tunnel: ## Start dev server with Cloudflare Tunnel (opt-in via profile)
	@echo "🌐 Starting dev server + Cloudflare Tunnel..."
	docker compose --profile tunnel up -d app cloudflared

docker-tunnel-logs: ## Follow Cloudflare Tunnel logs
	@echo "📜 Following Cloudflare Tunnel logs..."
	docker compose logs -f cloudflared

docker-tunnel-stop: ## Stop tunnel (does not remove app files)
	@echo "🛑 Stopping Cloudflare Tunnel..."
	docker compose stop cloudflared
