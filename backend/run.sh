#!/usr/bin/env bash
# Run the FastAPI backend from inside the backend/ directory.
# Handles venv activation, PYTHONPATH, and env defaults automatically.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV="$PROJECT_ROOT/.venv"

if [ ! -f "$VENV/bin/python" ]; then
  echo "❌ .venv not found at $VENV — run: python3.11 -m venv $VENV && pip install -r requirements.txt"
  exit 1
fi

# Env defaults (override by exporting before calling this script)
export PYTHONPATH="$PROJECT_ROOT"
export AI_MOCK_MODE="${AI_MOCK_MODE:-true}"
export SECRET_KEY="${SECRET_KEY:-dev-secret-key-change-in-prod}"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:Lumina%28%2B%299399739940@db.krqsomtvrdaijjibyqwo.supabase.co:5432/postgres}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export SENTRY_DSN="${SENTRY_DSN:-}"

PORT="${1:-8000}"
echo "🚀 Starting backend on http://localhost:$PORT  (AI_MOCK_MODE=$AI_MOCK_MODE)"
export WATCHFILES_FORCE_POLLING=1
exec "$VENV/bin/uvicorn" backend.main:app --reload --reload-dir "$SCRIPT_DIR" --port "$PORT"
