#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$PROJECT_ROOT"

SESSION_ID="${1:-}"

if [ -z "$SESSION_ID" ]; then
    echo "Usage: ./scripts/jules-complete.sh <session-id>"
    echo ""
    echo "Get session ID with:"
    echo "  jules remote list --session"
    exit 1
fi

STATE_FILE=".co-smos/state.json"

echo ""
echo "════════════════════════════════════════════"
echo "  COMPLETE: session $SESSION_ID"
echo "════════════════════════════════════════════"
echo ""

# --- [1/3] Pull result from Jules ---
echo "[1/3] Pulling result from Jules..."

if ! command -v jules >/dev/null 2>&1; then
    echo "  ❌ jules CLI not found"
    exit 1
fi

set +e
jules remote pull --session "$SESSION_ID" --apply 2>&1 | tail -10
PULL_EXIT=$?
set -e

if [ $PULL_EXIT -ne 0 ]; then
    echo ""
    echo "  ⚠️  Pull failed (exit $PULL_EXIT)."
    echo "  This may be because:"
    echo "    - no changes to apply"
    echo "    - conflicts with local changes"
    echo "  Check git status and resolve manually."
    echo ""
fi

# --- [2/3] Git status ---
echo ""
echo "[2/3] Git status:"
git status --short
echo ""

# --- [3/3] Update state ---
echo "[3/3] Updating Co-SMOS state..."

if [ -f "$STATE_FILE" ]; then
    python3 - "$STATE_FILE" "$SESSION_ID" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

state_file = Path(sys.argv[1])
session_id = sys.argv[2]
state = json.loads(state_file.read_text())

active = state.get("active_task")

if not active:
    print("  (no active task in state)")
    sys.exit(0)

now = datetime.now(timezone.utc).isoformat()
completed = {
    "id": active["id"],
    "status": "completed",
    "session_id": session_id,
    "branch": active.get("branch"),
    "request": active.get("request"),
    "started_at": active.get("started_at"),
    "finished_at": now,
}

state["last_task"] = completed
state["active_task"] = None
state["status"] = "ready"
state.setdefault("history", []).append(completed)
state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
print(f"  Task {active['id']} marked as completed")
PY
else
    echo "  (no state.json)"
fi

echo ""
echo "════════════════════════════════════════════"
echo "  DONE"
echo "════════════════════════════════════════════"
echo ""
echo "Next:"
echo "  git diff"
echo "  git add ."
echo "  git commit -m \"feat: apply Jules task result\""
echo "  git push"
echo "  gh pr create"
echo ""
