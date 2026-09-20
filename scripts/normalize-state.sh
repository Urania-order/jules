#!/usr/bin/env bash
# scripts/normalize-state.sh
# Normalize created_at ISO timestamps in .co-smos/state.json from task IDs.

set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")}"
cd "$PROJECT_ROOT"

STATE_FILE=".co-smos/state.json"

if [ ! -f "$STATE_FILE" ]; then
  echo "State file $STATE_FILE not found."
  exit 0
fi

python3 - <<'PY'
import json, re, sys
from pathlib import Path

state_file = Path(".co-smos/state.json")
if not state_file.exists():
    sys.exit(0)

try:
    data = json.loads(state_file.read_text(encoding="utf-8"))
except Exception as e:
    print(f"Error reading state file: {e}")
    sys.exit(1)

if not isinstance(data, dict):
    sys.exit(0)

normalized_count = 0

def _norm_entry(entry):
    if not isinstance(entry, dict):
        return False
    tid = entry.get("id")
    if not tid or not isinstance(tid, str):
        return False
    m = re.match(r"^task-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", tid)
    if not m:
        return False
    iso_val = f"{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}:{m.group(5)}:{m.group(6)}+00:00"
    if entry.get("created_at") != iso_val:
        entry["created_at"] = iso_val
        return True
    return False

for h in data.get("history", []):
    if _norm_entry(h):
        normalized_count += 1

tasks = data.get("tasks", [])
if isinstance(tasks, list):
    for t in tasks:
        if _norm_entry(t):
            normalized_count += 1

if _norm_entry(data.get("active_task")):
    normalized_count += 1

if _norm_entry(data.get("last_task")):
    normalized_count += 1

if normalized_count > 0:
    state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(f"normalized created_at for {normalized_count} task(s)")
PY
