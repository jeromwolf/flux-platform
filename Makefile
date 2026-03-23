.PHONY: help install test test-unit test-integration lint typecheck format ui-dev ui-build docker-up docker-down docker-logs docker-build clean

# Default
help:
	@echo "IMSP Platform - Available commands:"
	@echo ""
	@echo "  Development:"
	@echo "    make install       Install Python + UI dependencies"
	@echo "    make test          Run all tests"
	@echo "    make test-unit     Run unit tests only"
	@echo "    make test-integration  Run integration tests only"
	@echo "    make test-coverage Test coverage report"
	@echo "    make lint          Run ruff linter"
	@echo "    make typecheck     Run mypy type checker"
	@echo "    make format        Auto-format code with ruff"
	@echo ""
	@echo "  UI:"
	@echo "    make ui-dev        Start Vue dev server"
	@echo "    make ui-build      Build UI for production"
	@echo "    make ui-typecheck  Type check UI code"
	@echo ""
	@echo "  Infrastructure:"
	@echo "    make docker-up     Start all services"
	@echo "    make docker-down   Stop all services"
	@echo "    make docker-logs   Follow service logs"
	@echo "    make docker-build  Build Docker images"
	@echo ""
	@echo "  Cleanup:"
	@echo "    make clean         Remove build artifacts"

# --- Development ---

install:
	pip install -e ".[dev]"
	cd ui && npm ci

test:
	PYTHONPATH=.:core:domains python -m pytest tests/ -v --tb=short

test-unit:
	PYTHONPATH=.:core:domains python -m pytest tests/ -m unit -v --tb=short

test-integration:
	NEO4J_TEST_URI=bolt://localhost:7687 NEO4J_TEST_USER=neo4j NEO4J_TEST_PASSWORD=testpassword \
	PYTHONPATH=.:core:domains python -m pytest tests/integration/ -m integration -v --tb=short

test-coverage:
	PYTHONPATH=.:core:domains python -m pytest tests/ -m unit --cov=core --cov=domains --cov-report=term-missing --tb=short

lint:
	ruff check .

typecheck:
	mypy core/kg/ --ignore-missing-imports

format:
	ruff format .
	ruff check --fix .

# --- UI ---

ui-dev:
	cd ui && npm run dev

ui-build:
	cd ui && npm run build

ui-typecheck:
	cd ui && npx tsc --noEmit

# --- Infrastructure ---

docker-up:
	docker compose -f infra/docker-compose.yml up -d

docker-down:
	docker compose -f infra/docker-compose.yml down

docker-logs:
	docker compose -f infra/docker-compose.yml logs -f

docker-build:
	docker compose -f infra/docker-compose.yml build

# --- Cleanup ---

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache htmlcov coverage.xml test-results.xml
	rm -rf ui/dist ui/node_modules/.vite
