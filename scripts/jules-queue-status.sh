#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJECT_ROOT"

QUEUE_DIR=".jules/queue"
PENDING_DIR="${QUEUE_DIR}/pending"
RUNNING_DIR="${QUEUE_DIR}/running"
COMPLETED_DIR="${QUEUE_DIR}/completed"

mkdir -p "$PENDING_DIR" "$RUNNING_DIR" "$COMPLETED_DIR"

echo "=========================================="
echo " Jules Task Queue Status"
echo "=========================================="
echo ""

python3 - "$PENDING_DIR" "$RUNNING_DIR" "$COMPLETED_DIR" <<'PY'
import json, sys
from pathlib import Path

pending_dir = Path(sys.argv[1])
running_dir = Path(sys.argv[2])
completed_dir = Path(sys.argv[3])

def load_json(p):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None

# Pending
pending_files = list(pending_dir.glob("*.json"))
pending_tasks = []
for p in pending_files:
    data = load_json(p)
    if data:
        pending_tasks.append(data)

# Sort pending: priority desc, created_at asc
pending_tasks.sort(key=lambda x: (-x.get("priority", 5), x.get("created_at", "")))

print(f"[Pending Tasks] ({len(pending_tasks)})")
if pending_tasks:
    for t in pending_tasks:
        req = t.get("request", "")
        if len(req) > 60:
            req = req[:57] + "..."
        print(f"  • [{t.get('id')}] Priority: {t.get('priority', 5)} | {req}")
else:
    print("  (none)")
print("")

# Running
running_files = list(running_dir.glob("*.json"))
running_tasks = []
for p in running_files:
    data = load_json(p)
    if data:
        running_tasks.append(data)

print(f"[Running Task] ({len(running_tasks)})")
if running_tasks:
    for t in running_tasks:
        req = t.get("request", "")
        if len(req) > 60:
            req = req[:57] + "..."
        session = t.get("session_id") or "N/A"
        started = t.get("started_at") or "N/A"
        print(f"  • [{t.get('id')}] Session: {session} | Started: {started}")
        print(f"    Request: {req}")
else:
    print("  (none)")
print("")

# Completed
completed_files = list(completed_dir.glob("*.json"))
completed_tasks = []
for p in completed_files:
    data = load_json(p)
    if data:
        completed_tasks.append(data)

completed_tasks.sort(key=lambda x: x.get("finished_at", ""), reverse=True)

print(f"[Completed Tasks Archive] ({len(completed_tasks)})")
if completed_tasks:
    for t in completed_tasks[:5]:
        req = t.get("request", "")
        if len(req) > 60:
            req = req[:57] + "..."
        finished = t.get("finished_at") or "N/A"
        status = t.get("status", "completed")
        print(f"  • [{t.get('id')}] Status: {status} | Finished: {finished} | {req}")
    if len(completed_tasks) > 5:
        print(f"  ... and {len(completed_tasks) - 5} more")
else:
    print("  (none)")
PY

echo ""
echo "=========================================="
