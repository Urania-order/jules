#!/usr/bin/env bash
set -euo pipefail

# Ensure PATH includes node/nvm/jules (only if jules not found)
if ! command -v jules >/dev/null 2>&1; then
    NVM_BIN="$HOME/.nvm/versions/node/v16.20.2/bin"
    if [ -d "$NVM_BIN" ]; then
        export PATH="$NVM_BIN:$PATH"
    fi
fi

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJECT_ROOT"

QUEUE_DIR=".jules/queue"
PENDING_DIR="${QUEUE_DIR}/pending"
RUNNING_DIR="${QUEUE_DIR}/running"
COMPLETED_DIR="${QUEUE_DIR}/completed"
LOG_FILE="${QUEUE_DIR}/runner.log"

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
echo " Log file: $LOG_FILE"
echo "=========================================="
echo ""

process_next_task() {
    # Returns 0 if task was processed, 1 if no tasks pending
    python3 - "$PENDING_DIR" "$RUNNING_DIR" "$COMPLETED_DIR" "$DRY_RUN" "$LOG_FILE" <<'PY'
import json
import os
import re
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime, timezone

pending_dir = Path(sys.argv[1])
running_dir = Path(sys.argv[2])
completed_dir = Path(sys.argv[3])
dry_run = sys.argv[4] == "1"
log_file = Path(sys.argv[5])

def log(msg):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{now_str}] {msg}"
    print(msg)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Warning: failed to write to log file: {e}", file=sys.stderr)

def extract_session_id(log_content):
    if not log_content:
        return None
    # Look for "Session created: <id>" or "Session ID: <id>" or "Session: <id>"
    m = re.search(r"session\s*(?:created|id)?\s*[:=]\s*([0-9a-zA-Z_-]+)", log_content, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        if val.lower() not in ("created", "id", "is", "active", "started"):
            return val
    # Look for standalone long numeric session ID (15-20 digits)
    m_num = re.search(r"\b([0-9]{15,20})\b", log_content)
    if m_num:
        return m_num.group(1)
    # Look for session-<id>
    m_sess = re.search(r"\b(session-[0-9a-zA-Z_-]+)\b", log_content, re.IGNORECASE)
    if m_sess:
        return m_sess.group(1)
    return None

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
    log("No pending tasks in queue.")
    sys.exit(1)

# Sort pending: priority desc, created_at asc
def parse_priority(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 5

pending_tasks.sort(key=lambda item: (-parse_priority(item[1].get("priority", 5)), item[1].get("created_at", "")))

target_file, task_data = pending_tasks[0]
queue_task_id = task_data.get("id")
request = task_data.get("request")
priority = parse_priority(task_data.get("priority", 5))

log(f"Selected task for execution: {queue_task_id} (Priority: {priority})")
log(f"Request: {request}")

now = datetime.now(timezone.utc).isoformat()
task_data["status"] = "running"
task_data["started_at"] = now

running_file = running_dir / target_file.name
running_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False) + "\n")

# Remove from pending
if target_file.exists():
    target_file.unlink()

session_id = None
jules_task_id = None
error_msg = None
status = "completed"

if dry_run:
    log("[DRY-RUN] Simulating Jules task execution...")
    session_id = f"mock-session-{queue_task_id}"
    jules_task_id = queue_task_id
    log(f"[DRY-RUN] Simulating jules-complete.sh {jules_task_id} {session_id} feat/{jules_task_id}...")
else:
    log("Dispatching task via jules-task.sh...")
    try:
        env = os.environ.copy()
        env["COSMOS_AUTHOR"] = task_data.get("proposed_by") or "runner"
        res = subprocess.run(
            ["./scripts/jules-task.sh", request],
            capture_output=True,
            text=True,
            check=False,
            env=env
        )
        if res.returncode == 0:
            log("  Task successfully dispatched via jules-task.sh.")
            # Extract jules_task_id from state.json
            state_file = Path(".co-smos/state.json")
            if state_file.exists():
                try:
                    state_data = json.loads(state_file.read_text())
                    jules_task_id = (state_data.get("active_task") or {}).get("id")
                except Exception:
                    pass
            if not jules_task_id:
                jules_task_id = queue_task_id

            # Poll jules remote list --session until completed or timeout (max 1 hour)
            poll_interval = int(os.environ.get("JULES_POLL_INTERVAL", "10"))
            max_timeout = int(os.environ.get("JULES_POLL_TIMEOUT", "3600"))
            elapsed = 0
            session_completed = False

            while elapsed < max_timeout:
                # Try to extract session ID if not set yet
                if not session_id:
                    log_path = Path(f".jules/results/{jules_task_id}.log")
                    if log_path.exists():
                        session_id = extract_session_id(log_path.read_text())

                # Check jules remote list --session
                try:
                    list_res = subprocess.run(
                        ["jules", "remote", "list", "--session"],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    list_output = list_res.stdout

                    # If session_id not found in log, try parsing session ID from list output
                    if not session_id and list_res.returncode == 0:
                        session_id = extract_session_id(list_output)

                    if list_res.returncode == 0 and session_id:
                        # Search for status line for session_id
                        found_status = None
                        for line in list_output.splitlines():
                            if session_id in line:
                                l_lower = line.lower()
                                if "completed" in l_lower:
                                    found_status = "completed"
                                elif "failed" in l_lower or "error" in l_lower:
                                    found_status = "failed"
                                elif "in progress" in l_lower or "running" in l_lower or "pending" in l_lower:
                                    found_status = "running"
                                break

                        if found_status == "completed":
                            log(f"  Session {session_id} status is Completed.")
                            session_completed = True
                            break
                        elif found_status == "failed":
                            status = "failed"
                            error_msg = f"Session {session_id} failed according to jules remote list"
                            log(f"  ❌ {error_msg}")
                            break
                        else:
                            log(f"  [{elapsed}/{max_timeout}s] Waiting for session {session_id or 'unknown'} to complete...")
                    else:
                        log(f"  [{elapsed}/{max_timeout}s] Polling session list...")

                except Exception as poll_err:
                    log(f"  Warning during polling: {poll_err}")

                time.sleep(poll_interval)
                elapsed += poll_interval

            if not session_completed and status != "failed":
                status = "failed"
                error_msg = f"Task timed out after {max_timeout}s waiting for session completion"
                log(f"  ❌ {error_msg}")

            if session_completed:
                if not session_id:
                    session_id = f"session-{jules_task_id}"
                branch_name = f"feat/{jules_task_id}"
                log(f"Calling jules-complete.sh {jules_task_id} {session_id} {branch_name}...")
                # Auto-merge mode for runner (no TTY)
                env = os.environ.copy()
                env["JULES_AUTO_MERGE"] = "1"
                complete_res = subprocess.run(
                    ["./scripts/jules-complete.sh", jules_task_id, session_id, branch_name],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                )
                if complete_res.returncode == 0:
                    status = "completed"
                    log(f"  ✅ jules-complete.sh executed successfully for {jules_task_id}.")
                else:
                    status = "failed"
                    error_msg = complete_res.stderr or complete_res.stdout or "jules-complete.sh execution failed"
                    log(f"  ❌ Error executing jules-complete.sh: {error_msg}")

        else:
            status = "failed"
            error_msg = res.stderr or res.stdout or "jules-task.sh execution failed"
            log(f"  ❌ Error executing jules-task.sh: {error_msg}")
    except Exception as e:
        status = "failed"
        error_msg = str(e)
        log(f"  ❌ Exception during execution: {error_msg}")

finished_now = datetime.now(timezone.utc).isoformat()
task_data["status"] = status
task_data["finished_at"] = finished_now
task_data["session_id"] = session_id
task_data["jules_task_id"] = jules_task_id
task_data["error"] = error_msg

completed_file = completed_dir / target_file.name
completed_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False) + "\n")

# Remove from running
if running_file.exists():
    running_file.unlink()

log(f"Task {queue_task_id} moved to completed queue (Status: {status}).")
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
