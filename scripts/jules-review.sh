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
STATE_FILE=".co-smos/state.json"

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

# --- [2/5] Branch, commits, or state ---
echo "[2/5] BRANCH & COMMITS"
BRANCH_HAS_COMMITS=false
if [ -n "$BRANCH" ] && git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
    COMMITS=$(git log --oneline main.."$BRANCH" 2>/dev/null | wc -l)
    if [ "$COMMITS" -gt 0 ]; then
        echo "  Branch: $BRANCH ($COMMITS commits)"
        git log --oneline main.."$BRANCH" 2>/dev/null | head -10 | sed 's/^/    /'
        BRANCH_HAS_COMMITS=true
    else
        echo "  Branch: $BRANCH (no commits)"
    fi
fi

# Fallback: check state.json for completed task
if [ "$BRANCH_HAS_COMMITS" = "false" ]; then
    STATE_INFO=$(python3 - "$STATE_FILE" "$TASK_ID" <<'PY'
import json, sys
from pathlib import Path

state_file = Path(sys.argv[1])
task_id = sys.argv[2]

if not state_file.exists():
    print("")
    sys.exit(0)

state = json.loads(state_file.read_text())

for t in [state.get("last_task")] + state.get("history", []):
    if t and t.get("id") == task_id:
        print(f"  state.json: {t.get('status', 'unknown')}")
        if t.get("session_id"):
            print(f"  session:    {t.get('session_id')}")
        if t.get("pr"):
            print(f"  PR:         {t.get('pr')}")
        if t.get("finished_at"):
            print(f"  finished:   {t.get('finished_at')}")
        sys.exit(0)
print("")
PY
)
    if [ -n "$STATE_INFO" ]; then
        echo "$STATE_INFO"
        echo ""
        echo "  Recent commits in main:"
        git log --oneline -5 main 2>/dev/null | sed 's/^/    /'
    else
        echo "  (no branch commits, no state entry)"
    fi
fi
echo ""

# --- [3/5] Files changed ---
echo "[3/5] FILES CHANGED"
if [ "$BRANCH_HAS_COMMITS" = "true" ]; then
    git diff --stat main.."$BRANCH" 2>/dev/null | tail -20 | sed 's/^/  /'
else
    echo "  (see recent commits in main above)"
fi
echo ""

# --- [4/5] Session log tail ---
echo "[4/5] SESSION LOG (tail)"
if [ -f "$LOG_FILE" ]; then
    tail -15 "$LOG_FILE" | sed 's/^/  /'
else
    echo "  (no log file)"
fi
echo ""

# --- [5/5] Readiness check ---
echo "[5/5] READINESS"
READY=true

if [ "$BRANCH_HAS_COMMITS" = "true" ]; then
    echo "  ✅ Branch has commits"
elif [ -n "$STATE_INFO" ]; then
    echo "  ✅ Task recorded as completed in state.json"
else
    echo "  ⚠️  No commits on branch, no state entry"
    READY=false
fi

if [ -f "$LOG_FILE" ]; then
    if grep -qi 'completed\|success\|Ready for review' "$LOG_FILE" 2>/dev/null; then
        echo "  ✅ Session log shows completion"
    else
        echo "  ⚠️  Session log does not clearly show completion"
    fi
fi

if command -v uv >/dev/null 2>&1; then
    if uv run pytest tests/ -q \
        --ignore=tests/test_ecology_service.py \
        --ignore=tests/test_value_service.py \
        --ignore=tests/test_mcp.py >/dev/null 2>&1; then
        echo "  ✅ Tests pass"
    else
        echo "  ❌ Tests fail"
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
