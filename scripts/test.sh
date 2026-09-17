#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
if [ -z "$VIRTUAL_ENV" ]; then
  echo "Activating .venv..."
  source .venv/bin/activate
fi
python -m pytest tests/ "$@"
