#!/usr/bin/env bash
set -euo pipefail

# Ensure PATH includes uv and node/jules
PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJECT_ROOT"

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"

echo "=========================================="
echo " Starting Co-SMOS Web Control Room v0.9"
echo " Host: http://${HOST}:${PORT}"
echo "=========================================="

# Run FastAPI backend via uvicorn
exec uv run uvicorn smos.api.main:app --host "$HOST" --port "$PORT"
