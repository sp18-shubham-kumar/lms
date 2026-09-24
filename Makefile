# Skills LMS — developer commands. Run `make help` for the list.
# Backend runs in backend/.venv; frontend in frontend/node_modules.

BACKEND := backend
FRONTEND := frontend
PY := $(BACKEND)/.venv/bin/python
PIP := $(BACKEND)/.venv/bin/pip

.DEFAULT_GOAL := help
.PHONY: help setup setup-backend setup-frontend db-up db-down migrate makemigrations \
        superuser backend frontend dev stop test test-backend test-frontend \
        lint lint-backend lint-frontend format clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

## --- Setup ---------------------------------------------------------------
setup: setup-backend setup-frontend ## Install backend + frontend dependencies

setup-backend: ## Create venv and install backend deps
	python3 -m venv $(BACKEND)/.venv
	$(PIP) install --upgrade pip
	$(PIP) install -r $(BACKEND)/requirements-dev.txt
	@test -f $(BACKEND)/.env || cp $(BACKEND)/.env.example $(BACKEND)/.env

setup-frontend: ## Install frontend deps
	cd $(FRONTEND) && npm install
	@test -f $(FRONTEND)/.env || cp $(FRONTEND)/.env.example $(FRONTEND)/.env

## --- Database ------------------------------------------------------------
db-up: ## Start Postgres (docker)
	docker compose up -d db

db-down: ## Stop Postgres
	docker compose down

migrate: ## Apply migrations
	$(PY) $(BACKEND)/manage.py migrate

makemigrations: ## Create migrations
	$(PY) $(BACKEND)/manage.py makemigrations

superuser: ## Create a Django superuser
	$(PY) $(BACKEND)/manage.py createsuperuser

## --- Run -----------------------------------------------------------------
backend: ## Run the backend dev server
	$(PY) $(BACKEND)/manage.py runserver 0.0.0.0:8000

frontend: ## Run the frontend dev server
	cd $(FRONTEND) && npm run dev

dev: db-up ## Start Postgres + both apps via PM2
	npx pm2 start ecosystem.config.js

stop: ## Stop PM2-managed apps
	npx pm2 delete all || true

## --- Quality -------------------------------------------------------------
test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	cd $(BACKEND) && .venv/bin/pytest

test-frontend: ## Run frontend tests
	cd $(FRONTEND) && npm run test

lint: lint-backend lint-frontend ## Lint everything

lint-backend: ## Ruff + black check + mypy
	cd $(BACKEND) && .venv/bin/ruff check . && .venv/bin/black --check . && .venv/bin/mypy .

lint-frontend: ## ESLint + tsc
	cd $(FRONTEND) && npm run lint

format: ## Auto-format backend (ruff --fix + black)
	cd $(BACKEND) && .venv/bin/ruff check --fix . && .venv/bin/black .

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/htmlcov $(FRONTEND)/dist
