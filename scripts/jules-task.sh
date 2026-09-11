#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"

cd "$PROJECT_ROOT"

TASK="${*:-}"

if [ -z "$TASK" ]; then
    echo ""
    echo "Usage:"
    echo ""
    echo "  ./scripts/jules-task.sh \"your task\""
    echo ""
    exit 1
fi

TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
TASK_ID="task-${TIMESTAMP}"

TASK_FILE=".jules/tasks/${TASK_ID}.md"
STATE_FILE=".co-smos/state.json"

CURRENT_BRANCH="$(git branch --show-current)"
REPOSITORY="$(git remote get-url origin 2>/dev/null || echo 'unknown')"

echo ""
echo "=========================================="
echo " Jules Co-SMOS Task"
echo "=========================================="
echo ""
echo "Task ID:    $TASK_ID"
echo "Branch:     $CURRENT_BRANCH"
echo "Repository: $REPOSITORY"
echo ""
echo "Task:"
echo "$TASK"
echo ""

mkdir -p \
    .jules/tasks \
    .jules/history \
    .jules/results \
    .co-smos

cat > "$TASK_FILE" <<TASKEOF
# Jules Task

## Task ID

$TASK_ID

## Created

$(date -Iseconds)

## Repository

$REPOSITORY

## Branch

$CURRENT_BRANCH

## Request

$TASK

## Status

started

TASKEOF

if command -v python3 >/dev/null 2>&1; then

python3 - "$STATE_FILE" "$TASK_ID" "$TASK" <<'PY'
import json
import sys
from pathlib import Path

state_file = Path(sys.argv[1])
task_id = sys.argv[2]
task = sys.argv[3]

if state_file.exists():
    try:
        state = json.loads(state_file.read_text())
    except Exception:
        state = {}
else:
    state = {}

state["active_task"] = {
    "id": task_id,
    "request": task
}

state["status"] = "running"

state_file.write_text(
    json.dumps(state, indent=2, ensure_ascii=False) + "\n"
)
PY

fi

echo "[1/4] Checking Jules..."

if ! command -v jules >/dev/null 2>&1; then
    echo ""
    echo "ERROR: Jules CLI is not installed."
    echo ""
    echo "Run:"
    echo "  npm install -g @google/jules"
    echo ""
    exit 1
fi

echo "[2/4] Starting Jules..."

JULES_PROMPT=$(cat <<PROMPTEOF
You are working inside the repository:

$REPOSITORY

Current branch:

$CURRENT_BRANCH

Co-SMOS task ID:

$TASK_ID

User request:

$TASK

Follow AGENTS.md strictly.

Required workflow:

ANALYZE
PLAN
IMPLEMENT
TEST
REVIEW
REPORT

Before modifying files inspect the existing architecture.

Do not modify main directly.

Record important decisions.

Run all relevant tests.

At the end report:

STATUS
CHANGES
TESTS
RISKS
NEXT STEP
PROMPTEOF
)

echo ""
echo "Sending task to Jules..."
echo ""

jules remote new \
    --repo . \
    --session "$JULES_PROMPT" \
    > ".jules/results/${TASK_ID}.log" 2>&1 || {

    echo ""
    echo "Jules task failed to start."
    echo ""
    cat ".jules/results/${TASK_ID}.log"

    if command -v python3 >/dev/null 2>&1; then
        python3 - "$STATE_FILE" <<'PY'
import json
import sys
from pathlib import Path

p = Path(sys.argv[1])

if p.exists():
    state = json.loads(p.read_text())
else:
    state = {}

state["status"] = "failed"
state["active_task"] = None

p.write_text(
    json.dumps(state, indent=2, ensure_ascii=False) + "\n"
)
PY
    fi

    exit 1
}

echo ""
echo "=========================================="
echo " Jules task submitted"
echo "=========================================="
echo ""
echo "Task ID:"
echo "  $TASK_ID"
echo ""
echo "Log:"
echo "  .jules/results/${TASK_ID}.log"
echo ""
echo "Check Jules sessions with:"
echo "  jules remote list --session"
echo ""
