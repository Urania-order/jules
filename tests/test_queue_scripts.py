import json
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
