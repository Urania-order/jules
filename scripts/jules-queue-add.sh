#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJECT_ROOT"

TASK_DESC="${1:-}"
PRIORITY_INPUT="${2:-5}"

if [ -z "$TASK_DESC" ]; then
    echo "Usage: ./scripts/jules-queue-add.sh <task-description> [priority]"
    echo ""
    echo "Priority can be an integer (e.g. 1-10) or text (high=10, normal=5, low=1)."
    echo "Default priority: 5"
    exit 1
fi

# Convert string priority to integer if needed
case "$PRIORITY_INPUT" in
    high|High|HIGH) PRIORITY=10 ;;
    normal|Normal|NORMAL|medium|Medium|MEDIUM) PRIORITY=5 ;;
    low|Low|LOW) PRIORITY=1 ;;
    *)
        if [[ "$PRIORITY_INPUT" =~ ^[0-9]+$ ]]; then
            PRIORITY="$PRIORITY_INPUT"
        else
            echo "Error: Priority must be an integer or one of: high, normal, low."
            exit 1
        fi
        ;;
esac

PENDING_DIR=".jules/queue/pending"
mkdir -p "$PENDING_DIR"

TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
RAND_SUFFIX="$((RANDOM % 9000 + 1000))"
TASK_ID="task-${TIMESTAMP}-${RAND_SUFFIX}"
TASK_FILE="${PENDING_DIR}/${TASK_ID}.json"

CREATED_AT="$(date -u +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date +'%Y-%m-%dT%H:%M:%SZ')"

python3 - "$TASK_FILE" "$TASK_ID" "$TASK_DESC" "$PRIORITY" "$CREATED_AT" <<'PY'
import json, sys
from pathlib import Path

file_path = Path(sys.argv[1])
task_id = sys.argv[2]
request = sys.argv[3]
priority = int(sys.argv[4])
created_at = sys.argv[5]

data = {
    "id": task_id,
    "request": request,
    "priority": priority,
    "status": "pending",
    "created_at": created_at,
    "started_at": None,
    "finished_at": None,
    "session_id": None,
    "error": None
}

file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
PY

echo "Task added to queue successfully."
echo "  Task ID:  $TASK_ID"
echo "  Priority: $PRIORITY"
echo "  Request:  $TASK_DESC"
echo "  File:     $TASK_FILE"
