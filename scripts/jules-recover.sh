#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$PROJECT_ROOT"

STATE_FILE=".co-smos/state.json"

echo ""
echo "════════════════════════════════════════════"
echo "  RECOVER: Co-SMOS state"
echo "════════════════════════════════════════════"
echo ""

if [ ! -f "$STATE_FILE" ]; then
    echo "No state.json found — nothing to recover."
    exit 0
fi

ACTIVE=$(python3 - "$STATE_FILE" <<'PY'
import json, sys
from pathlib import Path
state = json.loads(Path(sys.argv[1]).read_text())
a = state.get("active_task")
print(a.get("id") if a else "")
PY
)

if [ -z "$ACTIVE" ]; then
    echo "No active task — nothing to recover."
    echo ""
    echo "Current status:"
    python3 - "$STATE_FILE" <<'PY'
import json, sys
from pathlib import Path
s = json.loads(Path(sys.argv[1]).read_text())
print(f"  status:  {s.get('status', '(none)')}")
last = s.get("last_task") or {}
print(f"  last:    {last.get('id', '(none)')}")
PY
    exit 0
fi

echo "Active task found: $ACTIVE"
echo ""
echo "This task will be marked as FAILED and moved to history."
echo ""

read -rp "Continue? [y/N] " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Aborted."
    exit 0
fi

python3 - "$STATE_FILE" "$ACTIVE" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

state_file = Path(sys.argv[1])
task_id = sys.argv[2]
state = json.loads(state_file.read_text())

active = state.get("active_task") or {}
now = datetime.now(timezone.utc).isoformat()

failed = {
    "id": task_id,
    "status": "failed",
    "request": active.get("request"),
    "branch": active.get("branch"),
    "started_at": active.get("started_at"),
    "finished_at": now,
    "reason": "Manually marked as failed via jules-recover.sh",
}

state["last_task"] = failed
state["active_task"] = None
state["status"] = "ready"
state.setdefault("history", []).append(failed)

state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
print(f"  Task {task_id} marked as failed")
PY

echo ""
echo "Returning to main..."
CURRENT=$(git branch --show-current)
if [ "$CURRENT" != "main" ]; then
    echo "  Current branch: $CURRENT"
    read -rp "  Switch to main? [y/N] " SWITCH
    if [ "$SWITCH" = "y" ] || [ "$SWITCH" = "Y" ]; then
        if git diff --quiet && git diff --cached --quiet; then
            git checkout main
            echo "  ✅ Switched to main"
        else
            echo "  ⚠️  Uncommitted changes — stash them first:"
            echo "      git stash"
            echo "      git checkout main"
        fi
    fi
else
    echo "  Already on main"
fi

echo ""
echo "════════════════════════════════════════════"
echo "  RECOVERY COMPLETE"
echo "════════════════════════════════════════════"
echo ""
echo "Next:"
echo "  ./scripts/jules-status.sh"
echo ""
