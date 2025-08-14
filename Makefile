IMAGEVER=3.3
IMAGENAME=ai
# the final Repo will be registry.gitlab.com/morshed_main/infra
REPO=registry.gitlab.com/morshed_main/ai
REPOUSERNAME="ai.dev.marahel"

# Docker Compose configuration
COMPOSE_FILE=docker-compose.yml

# No needs for changes bellow this line 
IMAGEFULLNAME=${REPO}/${IMAGENAME}:${IMAGEVER}

.PHONY: help build run push all dev clean up down logs restart build-compose run-compose stop-compose test-connection shell-main shell-mcp
.DEFAULT_GOAL := help

help:
	@echo "Docker Compose Commands:"
	@echo "  up              : Build and start all services using Docker Compose"
	@echo "  down            : Stop and remove all containers, networks"
	@echo "  build-compose   : Build all services using Docker Compose"
	@echo "  run-compose     : Start all services (without building)"
	@echo "  stop-compose    : Stop all running services"
	@echo "  restart         : Restart all services"
	@echo "  logs            : Show logs from all services"
	@echo ""
	@echo "Development Commands:"
	@echo "  dev             : Run FastAPI server locally with hot reload"
	@echo "  clean           : Clean up local development files"
	@echo ""
	@echo "Debugging Commands:"
	@echo "  test-connection : Test connection between services"
	@echo "  shell-main      : Open shell in main-api container"
	@echo "  shell-mcp       : Open shell in mcp-servers container"
	@echo ""
	@echo "Legacy Docker Commands:"
	@echo "  build           : Build single Docker image (legacy)"
	@echo "  run             : Run single Docker container (legacy)"
	@echo "  push            : Push image to registry"
	@echo "  login           : Login to Docker registry"
	@echo "  all             : Build and push image (legacy)"

# Docker Compose commands
up:
	@echo "Building and starting all services..."
	@docker-compose -f ${COMPOSE_FILE} up --build -d

down:
	@echo "Stopping and removing all containers..."
	@docker-compose -f ${COMPOSE_FILE} down

build-compose:
	@echo "Building all services..."
	@docker-compose -f ${COMPOSE_FILE} build

run-compose:
	@echo "Starting all services..."
	@docker-compose -f ${COMPOSE_FILE} up -d

stop-compose:
	@echo "Stopping all services..."
	@docker-compose -f ${COMPOSE_FILE} stop

restart:
	@echo "Restarting all services..."
	@docker-compose -f ${COMPOSE_FILE} restart

logs:
	@echo "Showing logs from all services..."
	@docker-compose -f ${COMPOSE_FILE} logs -f

# Development commands
dev:
	@echo "Starting FastAPI development server..."
	@uv run uvicorn --app-dir src main:app --log-level=debug --host=0.0.0.0 --port=9696 --reload

clean:
	@echo "Cleaning up development files..."
	@rm -rf .venv log
	@rm -f uv.lock

# Legacy Docker commands (for backward compatibility)
build:
	@echo "Building Docker image..."
	@docker build -t ${IMAGEFULLNAME} .
		
run:
	@echo "Running Docker container..."
	@docker run --env-file .env -p 9696:9696 ${IMAGEFULLNAME}

login:
	@echo "Logging into Docker registry..."
	@docker login -u="${REPOUSERNAME}" ${REPO} 
		
push:
	@echo "Pushing Docker image..."
	@docker push ${IMAGEFULLNAME}

# Debugging commands
test-connection:
	@echo "Testing connection between services..."
	@docker-compose -f ${COMPOSE_FILE} exec main-api sh -c "ping -c 3 mcp-servers || echo 'Ping failed, trying curl...'; curl -f http://mcp-servers:9697/mcp || echo 'Connection test failed'"

shell-main:
	@echo "Opening shell in main-api container..."
	@docker-compose -f ${COMPOSE_FILE} exec main-api sh

shell-mcp:
	@echo "Opening shell in mcp-servers container..."
	@docker-compose -f ${COMPOSE_FILE} exec mcp-servers sh

all: build push
