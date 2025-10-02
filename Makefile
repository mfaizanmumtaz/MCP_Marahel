# GitLab Docker Registry Configuration
IMAGEVER=3.3
IMAGENAME=ai
REPO=registry.gitlab.com/morshed_main/ai
REPOUSERNAME="ai.dev.marahel"

# Docker Compose Configuration
COMPOSE_FILE_DEV=docker-compose.yml
COMPOSE_FILE_PROD=docker-compose.prod.yml

.PHONY: help infra-start infra-stop infra-restart infra-logs infra-status clean \
        dev dev-run dev-client dev-servers \
        build build-client build-servers \
        prod-build prod-up prod-down prod-restart prod-logs prod-status \
        gitlab-build gitlab-push gitlab-login gitlab-deploy
.DEFAULT_GOAL := help

help:
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║              MCP Marahel - Quick Commands                    ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "📦 Infrastructure Commands (PostgreSQL + Gotenberg):"
	@echo "  make infra-start  : Start infrastructure services"
	@echo "  make infra-stop   : Stop infrastructure services"
	@echo "  make infra-restart: Restart infrastructure services"
	@echo "  make infra-logs   : View infrastructure logs"
	@echo "  make infra-status : Show infrastructure status"
	@echo ""
	@echo "🚀 Local Development (No Docker):"
	@echo "  make dev          : Run MCP servers + client locally (hot reload)"
	@echo "  make dev-client   : Run only MCP client locally (port 8000)"
	@echo "  make dev-servers  : Run only MCP servers locally (port 9697)"
	@echo "  make clean        : Clean up development files"
	@echo ""
	@echo "🔨 Build Commands (Development Images):"
	@echo "  make build        : Build both MCP client and server images"
	@echo "  make build-client : Build only MCP client image"
	@echo "  make build-servers: Build only MCP servers image"
	@echo ""
	@echo "🏭 Production Deployment (Local Docker):"
	@echo "  make prod-build   : Build all production images"
	@echo "  make prod-up      : Start all production services"
	@echo "  make prod-down    : Stop all production services"
	@echo "  make prod-restart : Restart production services"
	@echo "  make prod-logs    : View production logs"
	@echo "  make prod-status  : Show production service status"
	@echo ""
	@echo "🚢 GitLab Registry Deployment:"
	@echo "  make gitlab-login : Login to GitLab registry"
	@echo "  make gitlab-build : Build and tag images for GitLab"
	@echo "  make gitlab-push  : Push images to GitLab registry"
	@echo "  make gitlab-deploy: Build + Push to GitLab (full deploy)"

################################################################################
# SECTION 1: Infrastructure Management (PostgreSQL + Gotenberg)
################################################################################

infra-start:
	@echo "📦 Starting infrastructure services..."
	@docker-compose -f ${COMPOSE_FILE_DEV} up -d
	@echo ""
	@echo "✅ Infrastructure started successfully!"
	@echo ""
	@$(MAKE) --no-print-directory infra-status

infra-stop:
	@echo "⏸️  Stopping infrastructure services..."
	@docker-compose -f ${COMPOSE_FILE_DEV} down
	@echo "✅ Infrastructure stopped"

infra-restart:
	@echo "🔄 Restarting infrastructure services..."
	@docker-compose -f ${COMPOSE_FILE_DEV} restart
	@echo ""
	@$(MAKE) --no-print-directory infra-status

infra-logs:
	@echo "📋 Showing infrastructure logs (Ctrl+C to exit)..."
	@docker-compose -f ${COMPOSE_FILE_DEV} logs -f

infra-status:
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║              Infrastructure Service Status                   ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@docker-compose -f ${COMPOSE_FILE_DEV} ps
	@echo ""
	@echo "🌐 Available Services:"
	@echo "  📊 PostgreSQL (pgvector)  : localhost:5432"
	@echo "  📄 Gotenberg API          : http://localhost:3000"
	@echo ""
	@echo "💡 Run 'make dev' to start MCP services locally"

clean:
	@echo "🧹 Cleaning up development files..."
	@rm -rf .venv log services/mcp_client/.venv services/mcp_servers/.venv
	@rm -f uv.lock services/mcp_client/uv.lock services/mcp_servers/uv.lock
	@echo "✅ Cleanup complete"

################################################################################
# SECTION 2: Local Development (No Docker - Direct Python Execution)
################################################################################

dev:
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║      Starting Local Development (No Docker Build)           ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "🔧 Starting MCP Servers on port 9697..."
	@echo "🚀 Starting MCP Client on port 8000..."
	@echo ""
	@echo "🌐 URLs:"
	@echo "  📊 PostgreSQL: localhost:5432"
	@echo "  📄 Gotenberg: http://localhost:3000"
	@echo "  🔧 MCP Servers: http://localhost:9697"
	@echo "  🚀 MCP Client: http://localhost:8000"
	@echo "  📖 API Docs: http://localhost:8000/docs"
	@echo ""
	@echo "🔄 Hot reload enabled for both services"
	@echo "⏸️  Press Ctrl+C to stop all services"
	@echo ""
	@$(MAKE) --no-print-directory dev-run

dev-run:
	@cd services/mcp_servers/src && uv run python main.py & \
	cd services/mcp_client && uv run uvicorn --app-dir src main:app --log-level=debug --host=0.0.0.0 --port=8000 --reload

dev-client:
	@echo "💻 Starting MCP Client locally..."
	@echo "🚀 MCP Client: http://localhost:8000"
	@echo "📖 API Docs: http://localhost:8000/docs"
	@echo ""
	@cd services/mcp_client && uv run uvicorn --app-dir src main:app --log-level=debug --host=0.0.0.0 --port=8000 --reload

dev-servers:
	@echo "🔧 Starting MCP Servers locally..."
	@echo "🔧 MCP Servers: http://localhost:9697"
	@echo ""
	@cd services/mcp_servers/src && uv run python main.py

################################################################################
# SECTION 3: Build Docker Images (Development)
################################################################################

build:
	@echo "🔨 Building all service images..."
	@$(MAKE) --no-print-directory build-servers
	@$(MAKE) --no-print-directory build-client
	@echo ""
	@echo "✅ All images built successfully!"

build-servers:
	@echo "🔨 Building MCP Servers image (no cache)..."
	@docker build --no-cache -t mcp-servers:latest ./services/mcp_servers
	@echo "✅ MCP Servers image built"

build-client:
	@echo "🔨 Building MCP Client image (no cache)..."
	@docker build --no-cache -t mcp-client:latest ./services/mcp_client
	@echo "✅ MCP Client image built"

################################################################################
# SECTION 4: Production Deployment (Local Docker Compose)
################################################################################

prod-build:
	@echo "🏭 Building production images with docker-compose (no cache)..."
	@docker-compose -f ${COMPOSE_FILE_PROD} build --no-cache
	@echo "✅ Production build complete"

prod-up:
	@echo "🏭 Starting production services..."
	@docker-compose -f ${COMPOSE_FILE_PROD} up -d
	@echo ""
	@echo "✅ Production services started successfully!"
	@echo ""
	@$(MAKE) --no-print-directory prod-status

prod-down:
	@echo "⏸️  Stopping production services..."
	@docker-compose -f ${COMPOSE_FILE_PROD} down
	@echo "✅ All production services stopped"

prod-restart:
	@echo "🔄 Restarting production services..."
	@docker-compose -f ${COMPOSE_FILE_PROD} restart
	@echo ""
	@$(MAKE) --no-print-directory prod-status

prod-logs:
	@echo "📋 Showing production logs (Ctrl+C to exit)..."
	@docker-compose -f ${COMPOSE_FILE_PROD} logs -f

prod-status:
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║             Production Service Status                        ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@docker-compose -f ${COMPOSE_FILE_PROD} ps
	@echo ""
	@echo "🌐 Production URLs:"
	@echo "  📊 PostgreSQL (pgvector)  : localhost:5432"
	@echo "  📄 Gotenberg API          : http://localhost:3000"
	@echo "  🔧 MCP Servers API        : http://localhost:9697"
	@echo "  🚀 MCP Client API         : http://localhost:8000"
	@echo "  📖 API Documentation      : http://localhost:8000/docs"
	@echo ""
	@echo "💡 All services running in production mode"

################################################################################
# SECTION 5: GitLab Registry Deployment
################################################################################

gitlab-login:
	@echo "🔐 Logging into GitLab registry..."
	@docker login -u="${REPOUSERNAME}" ${REPO}
	@echo "✅ Login successful"

gitlab-build:
	@echo "🚢 Building images for GitLab registry..."
	@docker-compose -f ${COMPOSE_FILE_PROD} build
	@echo ""
	@echo "🏷️  Tagging images for GitLab..."
	@docker tag mcp-client ${REPO}/mcp-client:${IMAGEVER}
	@docker tag mcp-servers ${REPO}/mcp-servers:${IMAGEVER}
	@docker tag mcp-client ${REPO}/mcp-client:latest
	@docker tag mcp-servers ${REPO}/mcp-servers:latest
	@echo "✅ Images built and tagged for GitLab"

gitlab-push:
	@echo "📤 Pushing images to GitLab registry..."
	@docker push ${REPO}/mcp-servers:${IMAGEVER}
	@docker push ${REPO}/mcp-client:${IMAGEVER}
	@docker push ${REPO}/mcp-servers:latest
	@docker push ${REPO}/mcp-client:latest
	@echo "✅ Images pushed to GitLab registry"

gitlab-deploy:
	@echo "🚀 Full GitLab deployment (Build + Push)..."
	@$(MAKE) --no-print-directory gitlab-build
	@$(MAKE) --no-print-directory gitlab-push
	@echo ""
	@echo "✅ GitLab deployment complete!"
	@echo ""
	@echo "📦 Pushed images:"
	@echo "  - ${REPO}/mcp-servers:${IMAGEVER}"
	@echo "  - ${REPO}/mcp-client:${IMAGEVER}"
	@echo "  - ${REPO}/mcp-servers:latest"
	@echo "  - ${REPO}/mcp-client:latest"
