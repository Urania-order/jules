#!/usr/bin/env bash
#
# jules-last.sh — Show active/last task ID with ready-to-copy command
#
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

python3 - <<'PY'
import json
from pathlib import Path

p = Path(".co-smos/state.json")
if not p.exists():
    print("No state.json found.")
    raise SystemExit(1)

s = json.loads(p.read_text())
active = s.get("active_task") or {}
last = s.get("last_task") or {}

active_id = active.get("id")
last_id = last.get("id")

if active_id:
    print(f"Active task: {active_id}")
    print(f"  Status: {active.get('status', 'unknown')}")
    print()
    print(f"  Complete it with:")
    print(f"    ./scripts/jules-complete.sh")
    print()
    print(f"  Or explicitly:")
    print(f"    ./scripts/jules-complete.sh --task {active_id}")
elif last_id:
    status = last.get("status", "unknown")
    result = last.get("result", "unknown")
    print(f"Last task: {last_id}")
    print(f"  Status: {status}")
    print(f"  Result: {result}")
    print()
    if status == "completed" and result == "applied":
        print("  Task is already completed and applied.")
        print()
        print("  If you need to re-run completion:")
        print(f"    ./scripts/jules-complete.sh --task {last_id} --force")
    else:
        print(f"  Re-run completion with:")
        print(f"    ./scripts/jules-complete.sh --task {last_id}")
else:
    print("No tasks found.")
PY
