#!/usr/bin/env bash
#
# jules-audit-report.sh — Save an audit report from Jules UI
#
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

REPORTS_DIR="docs/audit-reports"
INDEX_FILE="$REPORTS_DIR/INDEX.md"

TASK_ID="${1:-}"

if [ -z "$TASK_ID" ]; then
    echo ""
    echo "Usage: ./scripts/jules-audit-report.sh <task-id>"
    echo ""
    exit 1
fi

if [[ ! "$TASK_ID" =~ ^task- ]]; then
    echo "ERROR: Task ID must start with 'task-' (got: $TASK_ID)"
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

if [ -t 0 ]; then
    echo " Source:      clipboard (pbpaste)"
    echo ""

    if ! command -v pbpaste >/dev/null 2>&1; then
        echo "ERROR: pbpaste not available."
        exit 1
    fi

    CLIP_LINES="$(pbpaste | wc -l | tr -d ' ')"
    CLIP_CHARS="$(pbpaste | wc -c | tr -d ' ')"
    CLIP_HAS_DECISION="$(pbpaste | grep -cE "Final Decision|FINAL DECISION|READY_FOR|NEED_MORE_ANALYSIS|BLOCKED_BY" || true)"

    echo " Clipboard:   $CLIP_LINES lines, $CLIP_CHARS chars"
    echo " Has decision: $CLIP_HAS_DECISION"
    echo ""

    # Multi-level validation
    if [ "$CLIP_LINES" -eq 0 ]; then
        echo "ERROR: Clipboard is empty. Nothing to save."
        exit 1
    fi

    if [ "$CLIP_LINES" -lt 5 ]; then
        echo "WARNING: Clipboard has only $CLIP_LINES lines."
        read -p "Continue? [y/N] " -n 1 -r
        echo
        [[ ! $REPLY =~ ^[Yy]$ ]] && echo "Aborted." && exit 1
    fi

    # If clipboard is short AND has no decision — strong warning
    if [ "$CLIP_LINES" -lt 50 ] && [ "$CLIP_HAS_DECISION" -eq 0 ]; then
        echo "WARNING: Clipboard is short ($CLIP_LINES lines) and has no 'Final Decision' line."
        echo "         This may be an incomplete report."
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        [[ ! $REPLY =~ ^[Yy]$ ]] && echo "Aborted." && exit 1
    fi

    pbpaste > "$REPORT_FILE"
else
    echo " Source:      stdin (pipe/file)"
    echo ""
    cat > "$REPORT_FILE"
fi

LINE_COUNT="$(wc -l < "$REPORT_FILE" | tr -d ' ')"
if [ "$LINE_COUNT" -lt 5 ]; then
    echo "ERROR: Report is empty or too short ($LINE_COUNT lines)."
    rm -f "$REPORT_FILE"
    exit 1
fi

SAVED_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
HASH="$(shasum -a 256 "$REPORT_FILE" | awk '{print $1}')"
HEAD="$(git rev-parse --short HEAD)"

DECISION="$(grep -m1 -E "Final Decision|FINAL DECISION|READY_FOR|NEED_MORE_ANALYSIS|BLOCKED_BY" "$REPORT_FILE" | head -1 | sed 's/^[[:space:]]*//' | cut -c1-60 || echo "unknown")"

if [ ! -f "$INDEX_FILE" ]; then
    cat > "$INDEX_FILE" <<'INDEX_HEADER'
# Co-SMOS — Audit Reports Index

| Task ID | Saved At (UTC) | Decision | Lines | HEAD | Report |
|---|---|---|---|---|---|
INDEX_HEADER
fi

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

echo "------------------------------------------"
echo " Git"
echo "------------------------------------------"
echo ""

git add "$REPORT_FILE" "$INDEX_FILE"

if git diff --cached --quiet; then
    echo " No changes to commit."
else
    COMMIT_MSG="docs: record audit report for $TASK_ID"
    git commit -m "$COMMIT_MSG"
    echo ""
    echo " Commit: $COMMIT_MSG"
    echo ""
fi

read -p " Push to origin/main? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    git push origin main
    echo ""
    echo " Pushed to origin/main."
else
    echo ""
    echo " Not pushed. To push later:"
    echo "   git push origin main"
fi

echo ""
