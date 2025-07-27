# Code Review Agent - Development Makefile
# 
# This Makefile provides common development commands for the project.
# It follows best practices for Python project management.

.PHONY: help install install-dev clean test test-cov lint format type-check security-check
.PHONY: docker-build docker-up docker-down docker-logs docker-clean
.PHONY: celery-worker celery-flower run-dev run-prod
.PHONY: db-init db-migrate db-upgrade db-downgrade
.DEFAULT_GOAL := help

# Variables
PYTHON := python3
PIP := pip3
PROJECT_NAME := code-review-agent
DOCKER_COMPOSE := docker-compose -f compose.yml

help: ## Show this help message
	@echo "Code Review Agent - Development Commands"
	@echo "========================================"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Installation and Setup
install: ## Install production dependencies
	$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies (includes production)
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-asyncio pytest-cov black isort mypy pre-commit

clean: ## Clean up temporary files and caches
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +

# Code Quality
test: ## Run tests
	pytest tests/ -v

test-cov: ## Run tests with coverage
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term

lint: ## Run linting (flake8, black check, isort check)
	black --check app/ tests/
	isort --check-only app/ tests/
	flake8 app/ tests/

format: ## Format code (black, isort)
	black app/ tests/
	isort app/ tests/

type-check: ## Run type checking (mypy)
	mypy app/

security-check: ## Run security checks (bandit)
	bandit -r app/ -ll

# Docker Commands
docker-build: ## Build Docker images
	$(DOCKER_COMPOSE) build

docker-up: ## Start all services
	$(DOCKER_COMPOSE) up -d

docker-down: ## Stop all services
	$(DOCKER_COMPOSE) down

docker-logs: ## Show logs for all services
	$(DOCKER_COMPOSE) logs -f

docker-clean: ## Remove all containers, networks, and volumes
	$(DOCKER_COMPOSE) down -v --remove-orphans
	docker system prune -f

# Application Commands
run-dev: ## Run the application in development mode
	ENVIRONMENT=development uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod: ## Run the application in production mode
	ENVIRONMENT=production uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

celery-worker: ## Start Celery worker
	ENVIRONMENT=development celery -A app.worker.celery_app worker --loglevel=info

celery-flower: ## Start Celery Flower monitoring
	ENVIRONMENT=development celery -A app.worker.celery_app flower

# Database Commands (when Alembic is set up)
db-init: ## Initialize database migrations
	alembic init alembic

db-migrate: ## Create a new migration
	@read -p "Enter migration message: " message; \
	alembic revision --autogenerate -m "$$message"

db-upgrade: ## Apply migrations
	alembic upgrade head

db-downgrade: ## Rollback last migration
	alembic downgrade -1

# Development Setup
setup-dev: install-dev ## Set up development environment
	cp .env.example .env
	pre-commit install
	@echo "Development environment set up!"
	@echo "1. Update .env file with your configuration"
	@echo "2. Start services: make docker-up"
	@echo "3. Run the application: make run-dev"

# All-in-one commands
dev-start: docker-up run-dev ## Start infrastructure and run app in development

check-all: lint type-check security-check test ## Run all code quality checks

# CI/CD Commands
ci-test: ## Run tests for CI (with XML output)
	pytest tests/ -v --cov=app --cov-report=xml --cov-report=term

ci-quality: ## Run quality checks for CI
	black --check app/ tests/
	isort --check-only app/ tests/
	flake8 app/ tests/
	mypy app/
	bandit -r app/ -ll -f json -o security-report.json
