#!/usr/bin/env bash
#
# jules-audit-verify.sh — Verify audit-trail continuity
#
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

REPORTS_DIR="docs/audit-reports"
INDEX_FILE="$REPORTS_DIR/INDEX.md"

if [ ! -f "$INDEX_FILE" ]; then
    echo "No index found. Nothing to verify."
    exit 0
fi

echo ""
echo "=========================================="
echo " Audit-Trail Verification"
echo "=========================================="
echo ""

CURRENT_HEAD="$(git rev-parse --short HEAD)"
echo " Current HEAD: $CURRENT_HEAD"
echo ""

MISSING=0
TOTAL=0

while IFS='|' read -r _ task_id saved_at decision lines head _; do
    task_id="$(echo "$task_id" | xargs)"
    [ -z "$task_id" ] && continue
    [[ "$task_id" == "Task ID" ]] && continue
    [[ "$task_id" == "---" ]] && continue

    TOTAL=$((TOTAL + 1))
    REPORT_FILE="$REPORTS_DIR/${task_id}-report.md"

    if [ ! -f "$REPORT_FILE" ]; then
        echo " MISSING: $task_id"
        MISSING=$((MISSING + 1))
    fi
done < "$INDEX_FILE"

echo ""
echo " Total reports: $TOTAL"
echo " Missing:       $MISSING"
echo ""

if [ "$MISSING" -gt 0 ]; then
    echo " Audit-trail is INCOMPLETE"
    exit 1
else
    echo " Audit-trail is COMPLETE"
fi
echo ""
