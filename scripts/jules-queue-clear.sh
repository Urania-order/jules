#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJECT_ROOT"

QUEUE_DIR=".jules/queue"
PENDING_DIR="${QUEUE_DIR}/pending"
RUNNING_DIR="${QUEUE_DIR}/running"
COMPLETED_DIR="${QUEUE_DIR}/completed"

mkdir -p "$PENDING_DIR" "$RUNNING_DIR" "$COMPLETED_DIR"

MODE="${1:-}"

if [ "$MODE" = "--help" ] || [ -z "$MODE" ]; then
    echo "Usage: ./scripts/jules-queue-clear.sh [--completed|--all]"
    echo ""
    echo "Options:"
    echo "  --completed   Clear only completed tasks archive"
    echo "  --all         Clear pending, running, and completed tasks"
    exit 1
fi

case "$MODE" in
    --completed)
        rm -f "${COMPLETED_DIR}"/*.json 2>/dev/null || true
        echo "Cleared completed tasks queue."
        ;;
    --all)
        rm -f "${PENDING_DIR}"/*.json 2>/dev/null || true
        rm -f "${RUNNING_DIR}"/*.json 2>/dev/null || true
        rm -f "${COMPLETED_DIR}"/*.json 2>/dev/null || true
        echo "Cleared all queues (pending, running, completed)."
        ;;
    *)
        echo "Error: Unknown option '$MODE'."
        echo "Usage: ./scripts/jules-queue-clear.sh [--completed|--all]"
        exit 1
        ;;
esac
