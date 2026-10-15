#!/usr/bin/env bash
#
# jules-audit-list.sh — List saved audit reports
#
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

REPORTS_DIR="docs/audit-reports"
INDEX_FILE="$REPORTS_DIR/INDEX.md"

if [ ! -f "$INDEX_FILE" ]; then
    echo "No audit reports yet."
    echo "Save one with: ./scripts/jules-audit-report.sh <task-id>"
    exit 0
fi

cat "$INDEX_FILE"
