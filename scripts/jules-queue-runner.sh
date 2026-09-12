#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJECT_ROOT"

QUEUE_DIR=".jules/queue"
PENDING_DIR="${QUEUE_DIR}/pending"
RUNNING_DIR="${QUEUE_DIR}/running"
COMPLETED_DIR="${QUEUE_DIR}/completed"

mkdir -p "$PENDING_DIR" "$RUNNING_DIR" "$COMPLETED_DIR"

MODE="once"
DRY_RUN="${JULES_DRY_RUN:-0}"

for arg in "$@"; do
    case "$arg" in
        --once) MODE="once" ;;
        --loop) MODE="loop" ;;
        --dry-run) DRY_RUN=1 ;;
        --help)
            echo "Usage: ./scripts/jules-queue-runner.sh [--once|--loop] [--dry-run]"
            echo ""
            echo "Options:"
            echo "  --once     Process a single task from queue and exit (default)"
            echo "  --loop     Continuously process tasks until queue is empty"
            echo "  --dry-run  Simulate execution without starting Jules remote sessions"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo " Jules Task Queue Runner"
echo "=========================================="
echo " Mode:     $MODE"
echo " Dry Run:  $DRY_RUN"
echo "=========================================="
echo ""

process_next_task() {
    # Returns 0 if task was processed, 1 if no tasks pending
    python3 - "$PENDING_DIR" "$RUNNING_DIR" "$COMPLETED_DIR" "$DRY_RUN" <<'PY'
import json, sys, os, subprocess
from pathlib import Path
from datetime import datetime, timezone

pending_dir = Path(sys.argv[1])
running_dir = Path(sys.argv[2])
completed_dir = Path(sys.argv[3])
dry_run = sys.argv[4] == "1"

def load_json(p):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None

pending_files = list(pending_dir.glob("*.json"))
pending_tasks = []

for p in pending_files:
    data = load_json(p)
    if data:
        pending_tasks.append((p, data))

if not pending_tasks:
    print("No pending tasks in queue.")
    sys.exit(1)

# Sort pending: priority desc, created_at asc
pending_tasks.sort(key=lambda item: (-item[1].get("priority", 5), item[1].get("created_at", "")))

target_file, task_data = pending_tasks[0]
task_id = task_data.get("id")
request = task_data.get("request")
priority = task_data.get("priority", 5)

print(f"Selected task for execution: {task_id} (Priority: {priority})")
print(f"Request: {request}")

now = datetime.now(timezone.utc).isoformat()
task_data["status"] = "running"
task_data["started_at"] = now

running_file = running_dir / target_file.name
running_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False) + "\n")

# Remove from pending
if target_file.exists():
    target_file.unlink()

session_id = None
error_msg = None
status = "completed"

if dry_run:
    print("[DRY-RUN] Simulating Jules task execution...")
    session_id = f"mock-session-{task_id}"
else:
    print("Dispatching task via jules-task.sh...")
    try:
        res = subprocess.run(
            ["./scripts/jules-task.sh", request],
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode == 0:
            print("  Task successfully dispatched.")
            # Try to extract session ID from log or jules remote list
            log_path = Path(f".jules/results/{task_id}.log")
            if log_path.exists():
                log_content = log_path.read_text()
                # Extract session ID if present
                for line in log_content.splitlines():
                    if "session" in line.lower() or "id:" in line.lower():
                        parts = line.strip().split()
                        if len(parts) > 1:
                            session_id = parts[-1]
                            break
            if not session_id:
                session_id = f"session-active-{task_id}"
        else:
            status = "failed"
            error_msg = res.stderr or res.stdout or "jules-task.sh execution failed"
            print(f"  ❌ Error executing jules-task.sh: {error_msg}")
    except Exception as e:
        status = "failed"
        error_msg = str(e)
        print(f"  ❌ Exception during execution: {error_msg}")

finished_now = datetime.now(timezone.utc).isoformat()
task_data["status"] = status
task_data["finished_at"] = finished_now
task_data["session_id"] = session_id
task_data["error"] = error_msg

completed_file = completed_dir / target_file.name
completed_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False) + "\n")

# Remove from running
if running_file.exists():
    running_file.unlink()

print(f"Task {task_id} moved to completed queue (Status: {status}).")
sys.exit(0)
PY
}

if [ "$MODE" = "once" ]; then
    process_next_task || true
else
    while process_next_task; do
        echo "--- Task finished. Checking for next task... ---"
        sleep 1
    done
    echo "Queue processing finished."
fi
