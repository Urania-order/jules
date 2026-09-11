#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$PROJECT_ROOT"

TASK_ID="${1:-}"

if [ -z "$TASK_ID" ]; then
    echo "Usage: ./scripts/jules-replay.sh <task-id>"
    echo ""
    echo "Available tasks:"
    ls -1t .jules/tasks/*.md 2>/dev/null | sed 's|.jules/tasks/||; s|\.md$||' | sed 's/^/  /' || echo "  (none)"
    exit 1
fi

TASK_FILE=".jules/tasks/${TASK_ID}.md"
LOG_FILE=".jules/results/${TASK_ID}.log"

if [ ! -f "$TASK_FILE" ]; then
    echo "Error: task card not found: $TASK_FILE"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════"
echo "  REPLAY: $TASK_ID"
echo "════════════════════════════════════════════"
echo ""

# --- [1/7] Task card ---
echo "[1/7] TASK CARD"
echo "  File: $TASK_FILE"
echo ""

# --- [2/7] Original request ---
echo "[2/7] ORIGINAL REQUEST"
python3 - "$TASK_FILE" <<'PY'
import re, sys
from pathlib import Path

text = Path(sys.argv[1]).read_text()

# Extract Request section
m = re.search(r"## Request\s*\n(.+?)(?=\n## |\Z)", text, re.DOTALL)
if m:
    req = m.group(1).strip()
    for line in req.splitlines():
        print(f"  {line}")
else:
    print("  (no request section)")

# Extract branch if present
m = re.search(r"## (?:Work )?[Bb]ranch\s*\n(.+)", text)
if m:
    print("")
    print(f"  Branch: {m.group(1).strip()}")

# Extract status
m = re.search(r"## Status\s*\n(.+)", text)
if m:
    print(f"  Status: {m.group(1).strip()}")
PY
echo ""

# --- [3/7] Session log ---
echo "[3/7] SESSION LOG"
if [ -f "$LOG_FILE" ]; then
    echo "  File: $LOG_FILE"
    echo "  Size: $(wc -l < "$LOG_FILE") lines"
    echo ""
    echo "  --- first 20 lines ---"
    head -20 "$LOG_FILE" | sed 's/^/  /'
    if [ "$(wc -l < "$LOG_FILE")" -gt 20 ]; then
        echo "  ..."
        echo "  --- last 10 lines ---"
        tail -10 "$LOG_FILE" | sed 's/^/  /'
    fi
else
    echo "  (no log file)"
fi
echo ""

# --- [4/7] Plan / workflow ---
echo "[4/7] PLAN / WORKFLOW"
if [ -f "$LOG_FILE" ]; then
    grep -iE 'ANALYZE|PLAN|IMPLEMENT|TEST|REVIEW|REPORT|Plan approved' "$LOG_FILE" 2>/dev/null | head -10 | sed 's/^/  /' || echo "  (no workflow markers)"
else
    echo "  (no log)"
fi
echo ""

# --- [5/7] Changes ---
echo "[5/7] CHANGES"
BRANCH=$(python3 - "$TASK_FILE" <<'PY'
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
m = re.search(r"## (?:Work )?[Bb]ranch\s*\n(.+)", text)
print(m.group(1).strip() if m else "")
PY
)

if [ -n "$BRANCH" ] && git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
    echo "  Branch: $BRANCH"
    echo ""
    echo "  Commits on branch (not in main):"
    git log --oneline main.."$BRANCH" 2>/dev/null | head -10 | sed 's/^/    /' || echo "    (no commits)"
    echo ""
    echo "  Files changed:"
    git diff --stat main.."$BRANCH" 2>/dev/null | tail -20 | sed 's/^/    /' || echo "    (none)"
elif [ -n "$BRANCH" ]; then
    echo "  Branch $BRANCH not found locally"
else
    echo "  (no branch recorded)"
fi
echo ""

# --- [6/7] Decisions ---
echo "[6/7] DECISIONS (ADRs)"
if [ -d ".jules/history" ]; then
    ADRS=$(ls -1t .jules/history/adr-*.md 2>/dev/null | head -5)
    if [ -n "$ADRS" ]; then
        echo "$ADRS" | sed 's/^/  /'
        echo ""
        echo "  --- most recent ADR (first 30 lines) ---"
        head -30 $(echo "$ADRS" | head -1) | sed 's/^/  /'
    else
        echo "  (no ADRs)"
    fi
else
    echo "  (no .jules/history/)"
fi
echo ""

# --- [7/7] Tests ---
echo "[7/7] TESTS"
if command -v uv >/dev/null 2>&1; then
    echo "  Running: uv run pytest tests/ (quiet)"
    RESULT=$(uv run pytest tests/ -q \
        --ignore=tests/test_ecology_service.py \
        --ignore=tests/test_value_service.py \
        --ignore=tests/test_mcp.py 2>&1 | tail -1)
    echo "  $RESULT"
else
    echo "  (uv not found)"
fi
echo ""

echo "════════════════════════════════════════════"
echo "  END OF REPLAY"
echo "════════════════════════════════════════════"
echo ""
