PROJECT_ROOT := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
VENV         := $(PROJECT_ROOT)/.venv
PYTHON       := $(VENV)/bin/python
PIP          := $(VENV)/bin/pip
UVICORN      := $(VENV)/bin/uvicorn

# ── Dev environment variables ─────────────────────────────────────────────────
export PYTHONPATH         := $(PROJECT_ROOT)
export AI_MOCK_MODE       ?= true
export SECRET_KEY         ?= dev-secret-key-change-in-production
export DATABASE_URL       ?= postgresql+asyncpg://postgres:postgres@localhost:5432/smartcontract
export REDIS_URL          ?= redis://localhost:6379/0
export SENTRY_DSN         ?=

.PHONY: dev backend frontend install test lint clean help

## Start the FastAPI backend (dev mode with auto-reload)
dev backend:
	@echo "🚀 Starting backend on http://localhost:8000"
	@cd $(PROJECT_ROOT) && $(UVICORN) backend.main:app --reload --port 8000

## Start the Next.js frontend (dev mode)
frontend:
	@echo "🎨 Starting frontend on http://localhost:3000"
	@cd $(PROJECT_ROOT)/frontend && npm run dev

## Install all backend dependencies into .venv
install:
	@$(PIP) install -r $(PROJECT_ROOT)/backend/requirements.txt

## Run all backend tests
test:
	@cd $(PROJECT_ROOT) && $(PYTHON) -m pytest tests/ -v

## Run linter
lint:
	@$(VENV)/bin/ruff check backend/

## Kill any process on port 8000
kill:
	@lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "Killed port 8000" || echo "Port 8000 was free"

## Clean Python cache files
clean:
	@find $(PROJECT_ROOT) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	 find $(PROJECT_ROOT) -name "*.pyc" -delete 2>/dev/null; echo "Cleaned"

help:
	@grep -E '^##' $(MAKEFILE_LIST) | sed 's/## //'
