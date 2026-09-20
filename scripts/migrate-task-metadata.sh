#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJECT_ROOT"

STATE_FILE=".co-smos/state.json"
BAK_FILE=".co-smos/state.json.bak"

if [ ! -f "$STATE_FILE" ]; then
    echo "State file $STATE_FILE does not exist. Nothing to migrate."
    exit 0
fi

# Backup once if backup does not exist
if [ ! -f "$BAK_FILE" ]; then
    cp "$STATE_FILE" "$BAK_FILE"
    echo "Created backup at $BAK_FILE"
fi

python3 - "$STATE_FILE" <<'PY'
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

state_file = Path(sys.argv[1])

try:
    state = json.loads(state_file.read_text(encoding="utf-8"))
except Exception as e:
    print(f"Error reading {state_file}: {e}")
    sys.exit(1)

def id_to_iso(task_id):
    if not task_id or not isinstance(task_id, str):
        return None
    m = re.match(r"^task-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", task_id)
    if m:
        try:
            dt = datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)), int(m.group(6)),
                tzinfo=timezone.utc
            )
            return dt.isoformat()
        except ValueError:
            return None
    return None

migrated_count = 0

def process_task(task):
    global migrated_count
    if not isinstance(task, dict):
        return task

    changed = False

    parsed_dt = id_to_iso(task.get("id"))
    if parsed_dt and task.get("created_at") != parsed_dt:
        task["created_at"] = parsed_dt
        changed = True

    if task.get("proposed_by") is None:
        task["proposed_by"] = "unknown"
        changed = True

    if task.get("title") is None:
        req = task.get("request") or ""
        task["title"] = req.split("\n")[0][:80]
        changed = True

    if changed:
        migrated_count += 1

    return task

if isinstance(state.get("history"), list):
    state["history"] = [process_task(t) for t in state["history"]]

if isinstance(state.get("last_task"), dict):
    state["last_task"] = process_task(state["last_task"])

if isinstance(state.get("active_task"), dict):
    state["active_task"] = process_task(state["active_task"])

if isinstance(state.get("tasks"), list):
    state["tasks"] = [process_task(t) for t in state["tasks"]]

state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Migrated metadata for {migrated_count} task(s).")
PY
