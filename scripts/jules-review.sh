#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$PROJECT_ROOT"

TASK_ID="${1:-}"

if [ -z "$TASK_ID" ]; then
    echo "Usage: ./scripts/jules-review.sh <task-id>"
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
echo "  REVIEW: $TASK_ID"
echo "════════════════════════════════════════════"
echo ""

# --- Extract branch from task card ---
BRANCH=$(python3 - "$TASK_FILE" <<'PY'
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
m = re.search(r"## (?:Work )?[Bb]ranch\s*\n(.+)", text)
print(m.group(1).strip() if m else "")
PY
)

# --- [1/5] Task status ---
echo "[1/5] TASK STATUS"
python3 - "$TASK_FILE" <<'PY'
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
for key in ["Request", "Status", "Created"]:
    m = re.search(rf"## {key}\s*\n(.+?)(?=\n## |\Z)", text, re.DOTALL)
    if m:
        val = m.group(1).strip().splitlines()[0] if m.group(1).strip() else "(empty)"
        print(f"  {key}: {val[:100]}")
PY
echo ""

# --- [2/5] Branch & commits ---
echo "[2/5] BRANCH & COMMITS"
if [ -n "$BRANCH" ]; then
    echo "  Branch: $BRANCH"
    if git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
        echo "  Commits ahead of main:"
        git log --oneline main.."$BRANCH" 2>/dev/null | head -10 | sed 's/^/    /' || echo "    (none)"
    else
        echo "  (branch not found locally)"
    fi
else
    echo "  (no branch recorded)"
fi
echo ""

# --- [3/5] Files changed ---
echo "[3/5] FILES CHANGED"
if [ -n "$BRANCH" ] && git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
    STAT=$(git diff --stat main.."$BRANCH" 2>/dev/null | tail -20)
    if [ -n "$STAT" ]; then
        echo "$STAT" | sed 's/^/  /'
    else
        echo "  (no changes)"
    fi
else
    echo "  (cannot compute — branch not found)"
fi
echo ""

# --- [4/5] Session log tail ---
echo "[4/5] SESSION LOG (tail)"
if [ -f "$LOG_FILE" ]; then
    tail -20 "$LOG_FILE" | sed 's/^/  /'
else
    echo "  (no log file)"
fi
echo ""

# --- [5/5] Readiness check ---
echo "[5/5] READINESS"
READY=true

if [ -n "$BRANCH" ] && git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
    COMMITS=$(git log --oneline main.."$BRANCH" 2>/dev/null | wc -l)
    if [ "$COMMITS" -eq 0 ]; then
        echo "  ⚠️  No commits on branch — nothing to review"
        READY=false
    else
        echo "  ✅ $COMMITS commit(s) on branch"
    fi
else
    echo "  ⚠️  Branch not found — cannot verify changes"
    READY=false
fi

if [ -f "$LOG_FILE" ]; then
    if grep -qi 'completed\|success' "$LOG_FILE" 2>/dev/null; then
        echo "  ✅ Session log shows completion"
    else
        echo "  ⚠️  Session log does not clearly show completion"
    fi
fi

if command -v uv >/dev/null 2>&1; then
    echo ""
    echo "  Running tests..."
    if uv run pytest tests/ -q \
        --ignore=tests/test_ecology_service.py \
        --ignore=tests/test_value_service.py \
        --ignore=tests/test_mcp.py >/dev/null 2>&1; then
        echo "  ✅ Tests pass"
    else
        echo "  ❌ Tests fail — review before merge"
        READY=false
    fi
fi

echo ""
if [ "$READY" = "true" ]; then
    echo "  RESULT: ✅ Ready for merge"
else
    echo "  RESULT: ⚠️  Not ready — check warnings above"
fi
echo ""
echo "════════════════════════════════════════════"
echo "  END OF REVIEW"
echo "════════════════════════════════════════════"
echo ""
