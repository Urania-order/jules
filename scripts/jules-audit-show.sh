#!/usr/bin/env bash
#
# jules-audit-show.sh — Show a saved audit report
#
# Usage:
#   ./scripts/jules-audit-show.sh task-20261015-122801
#
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

REPORTS_DIR="docs/audit-reports"
TASK_ID="${1:-}"

if [ -z "$TASK_ID" ]; then
    echo "Usage: ./scripts/jules-audit-show.sh <task-id>"
    echo ""
    echo "Available reports:"
    ls -1 "$REPORTS_DIR"/*-report.md 2>/dev/null | sed 's|.*/||; s|-report.md||' || echo "  (none)"
    exit 1
fi

REPORT_FILE="$REPORTS_DIR/${TASK_ID}-report.md"

if [ ! -f "$REPORT_FILE" ]; then
    echo "Report not found: $REPORT_FILE"
    echo ""
    echo "Available reports:"
    ls -1 "$REPORTS_DIR"/*-report.md 2>/dev/null | sed 's|.*/||; s|-report.md||' || echo "  (none)"
    exit 1
fi

cat "$REPORT_FILE"
