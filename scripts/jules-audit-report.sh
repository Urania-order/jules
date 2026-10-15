#!/usr/bin/env bash
#
# jules-audit-report.sh — Save an audit report from Jules UI
#
# Usage:
#   ./scripts/jules-audit-report.sh <task-id>
#
# Behavior:
#   - If stdin is a pipe or file, read report from stdin.
#   - If stdin is a terminal, read report from clipboard (pbpaste on macOS).
#
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

REPORTS_DIR="docs/audit-reports"
INDEX_FILE="$REPORTS_DIR/INDEX.md"

TASK_ID="${1:-}"

if [ -z "$TASK_ID" ]; then
    echo ""
    echo "Usage:"
    echo "  ./scripts/jules-audit-report.sh <task-id>"
    echo ""
    echo "The report is read from:"
    echo "  - stdin (if piped):  cat report.md | $0 <task-id>"
    echo "  - clipboard (macOS): copy report, then run $0 <task-id>"
    echo ""
    echo "Existing reports:"
    if [ -f "$INDEX_FILE" ]; then
        grep "^| " "$INDEX_FILE" | tail -10
    else
        echo "  (none yet)"
    fi
    exit 1
fi

mkdir -p "$REPORTS_DIR"

REPORT_FILE="$REPORTS_DIR/${TASK_ID}-report.md"

echo ""
echo "=========================================="
echo " Jules Audit Report — Save"
echo "=========================================="
echo ""
echo " Task ID:     $TASK_ID"
echo " Report file: $REPORT_FILE"
echo ""

# Determine source: stdin (pipe/file) or clipboard
if [ -t 0 ]; then
    # stdin is a terminal -> read from clipboard
    echo " Source:      clipboard (pbpaste)"
    echo ""

    if ! command -v pbpaste >/dev/null 2>&1; then
        echo "ERROR: pbpaste not available (not macOS?)."
        echo "Pipe the report instead:"
        echo "  cat report.md | $0 $TASK_ID"
        exit 1
    fi

    if ! pbpaste > "$REPORT_FILE"; then
        echo "ERROR: failed to read clipboard."
        rm -f "$REPORT_FILE"
        exit 1
    fi
else
    # stdin is a pipe or file -> read from stdin
    echo " Source:      stdin (pipe/file)"
    echo ""
    cat > "$REPORT_FILE"
fi

# Verify non-empty
LINE_COUNT="$(wc -l < "$REPORT_FILE" | tr -d ' ')"
if [ "$LINE_COUNT" -lt 5 ]; then
    echo ""
    echo "ERROR: Report is empty or too short ($LINE_COUNT lines)."
    echo "Removing $REPORT_FILE"
    rm -f "$REPORT_FILE"
    exit 1
fi

# Compute metadata
SAVED_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
HASH="$(shasum -a 256 "$REPORT_FILE" | awk '{print $1}')"
HEAD="$(git rev-parse --short HEAD)"

DECISION="$(grep -m1 -E "Final Decision|FINAL DECISION|READY_FOR|NEED_MORE_ANALYSIS|BLOCKED_BY" "$REPORT_FILE" | head -1 | sed 's/^[[:space:]]*//' | cut -c1-60 || echo "unknown")"

# Update INDEX.md
if [ ! -f "$INDEX_FILE" ]; then
    cat > "$INDEX_FILE" <<'INDEX_HEADER'
# Co-SMOS — Audit Reports Index

| Task ID | Saved At (UTC) | Decision | Lines | HEAD | Report |
|---|---|---|---|---|---|
INDEX_HEADER
fi

# Remove existing entry for same task_id (idempotent)
if grep -q "| $TASK_ID |" "$INDEX_FILE"; then
    grep -v "| $TASK_ID |" "$INDEX_FILE" > "${INDEX_FILE}.tmp"
    mv "${INDEX_FILE}.tmp" "$INDEX_FILE"
fi

echo "| $TASK_ID | $SAVED_AT | $DECISION | $LINE_COUNT | $HEAD | [report](${TASK_ID}-report.md) |" >> "$INDEX_FILE"

echo ""
echo "------------------------------------------"
echo " Saved:    $REPORT_FILE"
echo " Lines:    $LINE_COUNT"
echo " Decision: $DECISION"
echo " HEAD:     $HEAD"
echo " Hash:     ${HASH:0:16}..."
echo " Index:    $INDEX_FILE"
echo ""
echo " Next steps:"
echo "   git add $REPORT_FILE $INDEX_FILE"
echo "   git commit -m \"docs: record audit report for $TASK_ID\""
echo "   git push origin main"
echo ""
