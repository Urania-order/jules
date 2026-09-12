import json
import os
import shutil
import subprocess
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def queue_dirs(tmp_path, monkeypatch):
    """Fixture providing isolated queue directories for testing."""
    jules_dir = tmp_path / ".jules" / "queue"
    pending = jules_dir / "pending"
    running = jules_dir / "running"
    completed = jules_dir / "completed"

    pending.mkdir(parents=True, exist_ok=True)
    running.mkdir(parents=True, exist_ok=True)
    completed.mkdir(parents=True, exist_ok=True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))

    return {
        "root": tmp_path,
        "queue": jules_dir,
        "pending": pending,
        "running": running,
        "completed": completed,
    }


def run_script(script_name, *args, env=None):
    script_path = PROJECT_ROOT / "scripts" / script_name
    cmd = ["bash", str(script_path), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
    )


def test_queue_add_default_priority(queue_dirs):
    res = run_script("jules-queue-add.sh", "Task 1 description")
    assert res.returncode == 0
    assert "Task added to queue successfully" in res.stdout

    pending_files = list(queue_dirs["pending"].glob("*.json"))
    assert len(pending_files) == 1

    data = json.loads(pending_files[0].read_text())
    assert data["request"] == "Task 1 description"
    assert data["priority"] == 5
    assert data["status"] == "pending"


def test_queue_add_priority_mapping(queue_dirs):
    run_script("jules-queue-add.sh", "Low task", "low")
    run_script("jules-queue-add.sh", "High task", "high")
    run_script("jules-queue-add.sh", "Custom task", "8")

    pending_files = list(queue_dirs["pending"].glob("*.json"))
    assert len(pending_files) == 3

    priorities = {}
    for p in pending_files:
        data = json.loads(p.read_text())
        priorities[data["request"]] = data["priority"]

    assert priorities["Low task"] == 1
    assert priorities["High task"] == 10
    assert priorities["Custom task"] == 8


def test_queue_add_invalid_priority(queue_dirs):
    res = run_script("jules-queue-add.sh", "Task invalid", "invalid_prio")
    assert res.returncode != 0
    assert "Priority must be an integer" in res.stdout or "Priority must be an integer" in res.stderr


def test_queue_status_output(queue_dirs):
    run_script("jules-queue-add.sh", "Task A", "low")
    run_script("jules-queue-add.sh", "Task B", "high")

    res = run_script("jules-queue-status.sh")
    assert res.returncode == 0
    assert "[Pending Tasks] (2)" in res.stdout
    assert "Task B" in res.stdout
    assert "Task A" in res.stdout


def test_queue_runner_dry_run(queue_dirs):
    run_script("jules-queue-add.sh", "Task Low", "low")
    run_script("jules-queue-add.sh", "Task High", "high")

    res = run_script("jules-queue-runner.sh", "--dry-run", "--once")
    assert res.returncode == 0
    assert "Task High" in res.stdout

    pending_files = list(queue_dirs["pending"].glob("*.json"))
    completed_files = list(queue_dirs["completed"].glob("*.json"))

    assert len(pending_files) == 1
    assert len(completed_files) == 1

    completed_data = json.loads(completed_files[0].read_text())
    assert completed_data["request"] == "Task High"
    assert completed_data["status"] == "completed"


def test_queue_runner_priority_order_loop(queue_dirs):
    run_script("jules-queue-add.sh", "Task Low", "low")       # 1
    run_script("jules-queue-add.sh", "Task High", "high")     # 10
    run_script("jules-queue-add.sh", "Task Medium", "normal") # 5

    res = run_script("jules-queue-runner.sh", "--dry-run", "--loop")
    assert res.returncode == 0

    log_content = (queue_dirs["queue"] / "runner.log").read_text()

    assert "Task High" in log_content
    assert "Task Medium" in log_content
    assert "Task Low" in log_content

    # Check order in log
    idx_high = log_content.find("Task High")
    idx_med = log_content.find("Task Medium")
    idx_low = log_content.find("Task Low")

    assert idx_high < idx_med < idx_low

    pending_files = list(queue_dirs["pending"].glob("*.json"))
    completed_files = list(queue_dirs["completed"].glob("*.json"))

    assert len(pending_files) == 0
    assert len(completed_files) == 3


def test_queue_runner_waiting_and_completion(queue_dirs, tmp_path):
    mock_bin = tmp_path / "mock_bin"
    mock_bin.mkdir()

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy(PROJECT_ROOT / "scripts" / "jules-queue-runner.sh", scripts_dir / "jules-queue-runner.sh")
    (scripts_dir / "jules-queue-runner.sh").chmod(0o755)

    mock_jules_task = scripts_dir / "jules-task.sh"
    mock_jules_task.write_text("""#!/usr/bin/env bash
mkdir -p .co-smos .jules/results
cat > .co-smos/state.json <<EOF
{
  "active_task": {
    "id": "task-mock-999",
    "request": "$1"
  }
}
EOF
cat > .jules/results/task-mock-999.log <<EOF
Session created: session-mock-888
EOF
exit 0
""")
    mock_jules_task.chmod(0o755)

    mock_jules_complete = scripts_dir / "jules-complete.sh"
    mock_jules_complete.write_text("""#!/usr/bin/env bash
echo "jules-complete called with task=$1 session=$2 branch=$3" >> .jules/complete.log
exit 0
""")
    mock_jules_complete.chmod(0o755)

    mock_jules_cli = mock_bin / "jules"
    counter_file = tmp_path / "jules_poll_count"
    mock_jules_cli.write_text(f"""#!/usr/bin/env bash
if [ "$1" = "remote" ] && [ "$2" = "list" ]; then
    counter_file="{counter_file}"
    count=0
    if [ -f "$counter_file" ]; then
        count=$(cat "$counter_file")
    fi
    count=$((count + 1))
    echo "$count" > "$counter_file"
    if [ "$count" -ge 2 ]; then
        echo "session-mock-888   Completed"
    else
        echo "session-mock-888   In Progress"
    fi
fi
""")
    mock_jules_cli.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
    env["JULES_PROJECT_ROOT"] = str(tmp_path)
    env["JULES_POLL_INTERVAL"] = "1"
    env["JULES_POLL_TIMEOUT"] = "10"

    # Add task
    run_script("jules-queue-add.sh", "Integration test task", "high")

    # Run queue runner in real mode
    runner_script = scripts_dir / "jules-queue-runner.sh"
    res = subprocess.run(
        ["bash", str(runner_script), "--once"],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path
    )
    assert res.returncode == 0, f"Stdout: {res.stdout}, Stderr: {res.stderr}"

    # Verify task completed
    completed_files = list((tmp_path / ".jules" / "queue" / "completed").glob("*.json"))
    assert len(completed_files) == 1
    data = json.loads(completed_files[0].read_text())
    assert data["status"] == "completed"
    assert data["session_id"] == "session-mock-888"
    assert data["jules_task_id"] == "task-mock-999"

    # Verify jules-complete.sh was called
    complete_log = (tmp_path / ".jules" / "complete.log").read_text()
    assert "task-mock-999" in complete_log
    assert "session-mock-888" in complete_log
    assert "feat/task-mock-999" in complete_log

    # Verify runner log
    runner_log = (tmp_path / ".jules" / "queue" / "runner.log").read_text()
    assert "Selected task for execution" in runner_log
    assert "Session session-mock-888 status is Completed." in runner_log
    assert "Calling jules-complete.sh" in runner_log


def test_queue_clear(queue_dirs):
    run_script("jules-queue-add.sh", "Pending task")
    run_script("jules-queue-runner.sh", "--dry-run", "--once")
    run_script("jules-queue-add.sh", "New pending task")

    assert len(list(queue_dirs["pending"].glob("*.json"))) == 1
    assert len(list(queue_dirs["completed"].glob("*.json"))) == 1

    # Clear completed only
    res = run_script("jules-queue-clear.sh", "--completed")
    assert res.returncode == 0
    assert len(list(queue_dirs["pending"].glob("*.json"))) == 1
    assert len(list(queue_dirs["completed"].glob("*.json"))) == 0

    # Clear all
    res = run_script("jules-queue-clear.sh", "--all")
    assert res.returncode == 0
    assert len(list(queue_dirs["pending"].glob("*.json"))) == 0
    assert len(list(queue_dirs["completed"].glob("*.json"))) == 0
