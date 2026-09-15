#!/usr/bin/env bash
# scripts/jules-complete.sh
# Atomically complete a Jules task.

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
cd "$PROJECT_ROOT"

STATE_FILE=".co-smos/state.json"
TASKS_DIR=".jules/tasks"

SESSION_ID=""
TASK_ID=""

if [ $# -eq 0 ]; then
  echo "Usage: ./scripts/jules-complete.sh <SESSION_ID>"
  echo "       ./scripts/jules-complete.sh --task <TASK_ID>"
  exit 1
fi

if [ "$1" = "--task" ]; then
  [ -z "${2:-}" ] && { echo "ERROR: --task requires TASK_ID"; exit 1; }
  TASK_ID="$2"
elif [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  echo "Usage: ./scripts/jules-complete.sh <SESSION_ID>"
  echo "       ./scripts/jules-complete.sh --task <TASK_ID>"
  exit 0
else
  SESSION_ID="$1"
fi

echo ""
echo "================================================"
echo " Jules Co-SMOS — Complete Task"
echo "================================================"
echo " Project root: $PROJECT_ROOT"
[ -n "$SESSION_ID" ] && echo " Session ID:   $SESSION_ID"
[ -n "$TASK_ID" ]    && echo " Task ID:      $TASK_ID"
echo ""

if [ -z "$TASK_ID" ]; then
  if [ ! -f "$STATE_FILE" ]; then
    echo "ERROR: $STATE_FILE not found and --task not provided."
    exit 3
  fi
  TASK_ID="$(python3 -c "
import json
try:
    s = json.load(open('$STATE_FILE'))
    a = s.get('active_task') or {}
    print(a.get('id') or '')
except Exception:
    print('')
")"
fi

if [ -z "$TASK_ID" ]; then
  echo "ERROR: could not determine TASK_ID (no active_task in state.json)."
  exit 3
fi

TASK_FILE="$TASKS_DIR/${TASK_ID}.md"
# Resolve SESSION_ID from log if empty
if [ -z "$SESSION_ID" ] && [ -n "$TASK_ID" ]; then
  LOG_FILE=".jules/results/${TASK_ID}.log"
  if [ -f "$LOG_FILE" ]; then
    SESSION_ID="$(grep -m1 '^ID:' "$LOG_FILE" | awk '{print $2}' || true)"
    if [ -n "$SESSION_ID" ]; then
      echo " Resolved SESSION_ID from log: $SESSION_ID"
    fi
  fi
fi

if [ -z "$SESSION_ID" ]; then
  echo "ERROR: could not determine SESSION_ID (no --session, no active_task, no log)."
  echo "       Hint: check .jules/results/${TASK_ID}.log for 'ID: <session>'"
  exit 3
fi

echo " Resolved TASK_ID: $TASK_ID"
echo ""

STASHED=0
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo "[1/7] Stashing local changes..."
  git stash push -u -m "jules-complete: pre-pull stash for $TASK_ID" >/dev/null
  STASHED=1
else
  echo "[1/7] No local changes to stash."
fi

echo "[2/7] Pulling result from Jules..."
PULL_OUT="$(jules remote pull --session "$SESSION_ID" --apply 2>&1 || true)"
echo "$PULL_OUT" | sed 's/^/      /'

if echo "$PULL_OUT" | grep -q "No diff found in the remote VM"; then
  PULL_RESULT="no-op"
  echo "      → No diff found. Marking as no-op."
elif echo "$PULL_OUT" | grep -qi "error\|failed\|conflict"; then
  PULL_RESULT="error"
  echo "      → Pull reported errors. Will record but continue."
else
  PULL_RESULT="applied"
fi

if [ "$STASHED" -eq 1 ]; then
  echo "[3/7] Restoring local changes..."
  if ! git stash pop >/dev/null 2>&1; then
    echo "      WARNING: stash pop reported conflicts. Resolve manually."
  fi
else
  echo "[3/7] No stash to restore."
fi

echo "[4/7] Current git status:"
git status --short | sed 's/^/      /'
echo ""
echo "      Diff stat (HEAD):"
git diff HEAD --stat | sed 's/^/      /' || true
echo ""

# --- post-pull forbidden paths check (ERRATA-0012) ---
FORBIDDEN_VIOLATIONS="$(git diff --name-only HEAD 2>/dev/null | grep -E '^\.(co-smos|jules/(tasks|results|queue))/' || true)"
if [ -n "$FORBIDDEN_VIOLATIONS" ]; then
  echo "      WARNING: forbidden paths were modified during this task:"
  echo "$FORBIDDEN_VIOLATIONS" | sed 's/^/        /'
  echo "      -> See ERRATA-0012"
  echo "      -> These files are orchestrator-owned and must be reverted if not intentional"
fi
echo ""

echo "[5/7] Updating $STATE_FILE..."
SESSION_ID="$SESSION_ID" TASK_ID="$TASK_ID" PULL_RESULT="$PULL_RESULT" python3 - <<'PY'
import json, os
from datetime import datetime, timezone
from pathlib import Path

state_file = Path(".co-smos/state.json")
task_id = os.environ["TASK_ID"]
session_id = os.environ.get("SESSION_ID") or ""
pull_result = os.environ.get("PULL_RESULT", "unknown")

if state_file.exists():
    try:
        state = json.loads(state_file.read_text())
    except Exception:
        state = {}
else:
    state = {}

state.setdefault("version", 1)
state.setdefault("project", "jules-codespace")
state.setdefault("agent", "jules")
state.setdefault("history", [])

active = state.get("active_task") or {}
now = datetime.now(timezone.utc).isoformat()

completed = {
    "id": task_id,
    "status": "completed",
    "session_id": session_id or active.get("session_id"),
    "branch": active.get("branch"),
    "request": active.get("request"),
    "started_at": active.get("started_at"),
    "finished_at": now,
    "result": pull_result,
}

state["last_task"] = completed
state["active_task"] = None
state["status"] = "ready"
state["history"].append(completed)

state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
print(f"      state.json updated: {task_id} -> completed (result={pull_result})")
PY

if [ -f "$TASK_FILE" ]; then
  echo "[6/7] Updating task record: $TASK_FILE"
  {
    echo ""
    echo "## Final Status"
    echo ""
    echo "completed"
    echo ""
    echo "## Result"
    echo ""
    echo "pull result: $PULL_RESULT"
    echo ""
    echo "Session: $SESSION_ID"
    echo ""
    echo "Completed at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >> "$TASK_FILE"
else
  echo "[6/7] WARNING: $TASK_FILE not found, skipping."
fi

echo "[7/7] Committing and pushing..."

CODE_PATHS=()
for p in frontend smos tests docs scripts Dockerfile .devcontainer .gitignore; do
  [ -e "$p" ] && CODE_PATHS+=("$p")
done

if [ ${#CODE_PATHS[@]} -gt 0 ]; then
  git add "${CODE_PATHS[@]}" 2>/dev/null || true
  if ! git diff --cached --quiet; then
    git commit -m "feat: apply Jules result for $TASK_ID

Session: $SESSION_ID
Pull result: $PULL_RESULT"
    echo "      -> code commit done"
  else
    echo "      -> no code changes to commit"
  fi
fi

ART_PATHS=(".co-smos" ".jules/tasks" ".jules/results" ".jules/history" ".jules/errata")
for p in "${ART_PATHS[@]}"; do
  [ -e "$p" ] && git add "$p" 2>/dev/null || true
done
if ! git diff --cached --quiet; then
  git commit -m "chore: record Co-SMOS artifacts for $TASK_ID

Session: $SESSION_ID
Pull result: $PULL_RESULT"
  echo "      -> artifacts commit done"
else
  echo "      -> no artifacts to commit"
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if git remote get-url origin >/dev/null 2>&1; then
  echo "      pushing $CURRENT_BRANCH -> origin..."
  git push origin "$CURRENT_BRANCH" || echo "      WARNING: push failed"
fi

echo ""
echo "================================================"
echo " Task completed"
echo "================================================"
echo ""
echo "Task ID:  $TASK_ID"
echo "Session:  $SESSION_ID"
echo "Result:   $PULL_RESULT"
echo ""
