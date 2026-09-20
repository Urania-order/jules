import json
import os
import shutil
import subprocess
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Fixture providing isolated project directory with .co-smos and .jules dirs and initialized git repo."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True, check=True)

    cosmos_dir = tmp_path / ".co-smos"
    jules_dir = tmp_path / ".jules" / "queue"
    results_dir = tmp_path / ".jules" / "results"
    tasks_dir = tmp_path / ".jules" / "tasks"
    pending = jules_dir / "pending"
    running = jules_dir / "running"
    completed = jules_dir / "completed"

    results_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir.mkdir(parents=True, exist_ok=True)
    cosmos_dir.mkdir(parents=True, exist_ok=True)
    pending.mkdir(parents=True, exist_ok=True)
    running.mkdir(parents=True, exist_ok=True)
    completed.mkdir(parents=True, exist_ok=True)

    # Initial commit so git log/status/diff work smoothly
    dummy_file = tmp_path / "README.md"
    dummy_file.write_text("# Test Repo\n")
    gitignore_file = tmp_path / ".gitignore"
    gitignore_file.write_text(".jules/results/\n*.log\n.co-smos/state.json\n!.co-smos/state.json\n")
    state_file = cosmos_dir / "state.json"
    state_file.write_text("{}\n")
    subprocess.run(["git", "add", "README.md", ".gitignore", ".co-smos/state.json"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=tmp_path, capture_output=True, check=True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))

    return {
        "root": tmp_path,
        "cosmos": cosmos_dir,
        "state_file": cosmos_dir / "state.json",
        "pending": pending,
        "running": running,
        "completed": completed,
    }


def run_bash_script(script_name, *args, env=None, cwd=None):
    script_path = PROJECT_ROOT / "scripts" / script_name
    cmd = ["bash", str(script_path), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd
    )


def test_task_active_has_created_at(isolated_env):
    """test_task_active_has_created_at (mock jules-task.sh flow)"""
    mock_bin = isolated_env["root"] / "mock_bin"
    mock_bin.mkdir()
    mock_jules_cli = mock_bin / "jules"
    mock_jules_cli.write_text("#!/usr/bin/env bash\nexit 0\n")
    mock_jules_cli.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
    env["JULES_PROJECT_ROOT"] = str(isolated_env["root"])

    res = run_bash_script("jules-task.sh", "Test task description\nLine 2", env=env, cwd=isolated_env["root"])
    assert res.returncode == 0, f"stdout: {res.stdout}, stderr: {res.stderr}"

    state_data = json.loads(isolated_env["state_file"].read_text())
    active = state_data.get("active_task")
    assert active is not None
    assert "created_at" in active
    assert active["created_at"] is not None
    assert active["started_at"] is not None
    assert active["title"] == "Test task description"
    assert active["status"] == "RUNNING"


def test_task_active_has_proposed_by(isolated_env):
    """test_task_active_has_proposed_by"""
    mock_bin = isolated_env["root"] / "mock_bin"
    mock_bin.mkdir()
    mock_jules_cli = mock_bin / "jules"
    mock_jules_cli.write_text("#!/usr/bin/env bash\nexit 0\n")
    mock_jules_cli.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
    env["JULES_PROJECT_ROOT"] = str(isolated_env["root"])

    # Default fallback "operator"
    run_bash_script("jules-task.sh", "Default author task", env=env, cwd=isolated_env["root"])
    state_data = json.loads(isolated_env["state_file"].read_text())
    assert state_data["active_task"]["proposed_by"] == "operator"

    # Explicit COSMOS_AUTHOR
    env["COSMOS_AUTHOR"] = "alice"
    run_bash_script("jules-task.sh", "Custom author task", env=env, cwd=isolated_env["root"])
    state_data = json.loads(isolated_env["state_file"].read_text())
    assert state_data["active_task"]["proposed_by"] == "alice"


def test_completed_copies_created_at(isolated_env):
    """test_completed_copies_created_at"""
    state = {
        "version": 1,
        "active_task": {
            "id": "task-20260918-190000",
            "request": "Test request",
            "title": "Test title",
            "priority": 4,
            "created_at": "2026-09-18T19:00:00+00:00",
            "started_at": "2026-09-18T19:00:05+00:00",
            "proposed_by": "bob",
            "source_task": "task-20260918-180000",
            "branch": "feat/task-20260918-190000"
        },
        "history": []
    }
    isolated_env["state_file"].write_text(json.dumps(state, indent=2))

    mock_bin = isolated_env["root"] / "mock_bin"
    mock_bin.mkdir()
    mock_jules_cli = mock_bin / "jules"
    mock_jules_cli.write_text("#!/usr/bin/env bash\necho 'No diff found in the remote VM'\nexit 0\n")
    mock_jules_cli.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
    env["JULES_PROJECT_ROOT"] = str(isolated_env["root"])
    env["JULES_SKIP_TESTS"] = "1"
    env["JULES_NO_PUSH"] = "1"
    env["JULES_SKIP_CI"] = "1"

    res = run_bash_script("jules-complete.sh", "session-12345", env=env, cwd=isolated_env["root"])
    assert res.returncode == 0, f"stdout: {res.stdout}, stderr: {res.stderr}"

    state_data = json.loads(isolated_env["state_file"].read_text())
    last = state_data.get("last_task")
    assert last is not None
    assert last["created_at"] == "2026-09-18T19:00:00+00:00"
    assert last["title"] == "Test title"
    assert last["priority"] == 4


def test_completed_copies_proposed_by(isolated_env):
    """test_completed_copies_proposed_by"""
    state = {
        "version": 1,
        "active_task": {
            "id": "task-20260918-191000",
            "request": "Test request author",
            "title": "Test request author",
            "priority": 5,
            "created_at": "2026-09-18T19:10:00+00:00",
            "started_at": "2026-09-18T19:10:05+00:00",
            "proposed_by": "carol",
            "source_task": None,
            "branch": "main"
        },
        "history": []
    }
    isolated_env["state_file"].write_text(json.dumps(state, indent=2))

    mock_bin = isolated_env["root"] / "mock_bin"
    mock_bin.mkdir()
    mock_jules_cli = mock_bin / "jules"
    mock_jules_cli.write_text("#!/usr/bin/env bash\necho 'No diff found in the remote VM'\nexit 0\n")
    mock_jules_cli.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
    env["JULES_PROJECT_ROOT"] = str(isolated_env["root"])
    env["JULES_SKIP_TESTS"] = "1"
    env["JULES_NO_PUSH"] = "1"
    env["JULES_SKIP_CI"] = "1"

    res = run_bash_script("jules-complete.sh", "session-67890", env=env, cwd=isolated_env["root"])
    assert res.returncode == 0, f"stdout: {res.stdout}, stderr: {res.stderr}"

    state_data = json.loads(isolated_env["state_file"].read_text())
    last = state_data.get("last_task")
    assert last is not None
    assert last["proposed_by"] == "carol"


def test_migration_backfills_created_at_from_id(isolated_env):
    """test_migration_backfills_created_at_from_id"""
    state = {
        "version": 1,
        "history": [
            {
                "id": "task-20260501-123456",
                "request": "Historical task request\nLine 2",
                "created_at": None,
                "proposed_by": None,
                "title": None
            }
        ]
    }
    isolated_env["state_file"].write_text(json.dumps(state, indent=2))

    env = dict(os.environ)
    env["JULES_PROJECT_ROOT"] = str(isolated_env["root"])

    res = run_bash_script("migrate-task-metadata.sh", env=env, cwd=isolated_env["root"])
    assert res.returncode == 0, f"stdout: {res.stdout}, stderr: {res.stderr}"
    assert "Migrated metadata for 1 task(s)" in res.stdout

    state_data = json.loads(isolated_env["state_file"].read_text())
    h0 = state_data["history"][0]
    assert h0["created_at"] == "2026-05-01T12:34:56+00:00"


def test_migration_backfills_proposed_by_unknown(isolated_env):
    """test_migration_backfills_proposed_by_unknown"""
    state = {
        "version": 1,
        "last_task": {
            "id": "task-20260601-080000",
            "request": "Last task request",
            "created_at": "2026-06-01T08:00:00+00:00",
            "proposed_by": None,
            "title": "Last task request"
        }
    }
    isolated_env["state_file"].write_text(json.dumps(state, indent=2))

    env = dict(os.environ)
    env["JULES_PROJECT_ROOT"] = str(isolated_env["root"])

    res = run_bash_script("migrate-task-metadata.sh", env=env, cwd=isolated_env["root"])
    assert res.returncode == 0, f"stdout: {res.stdout}, stderr: {res.stderr}"

    state_data = json.loads(isolated_env["state_file"].read_text())
    last = state_data["last_task"]
    assert last["proposed_by"] == "unknown"


def test_migration_preserves_existing_values(isolated_env):
    """test_migration_preserves_existing_values"""
    state = {
        "version": 1,
        "history": [
            {
                "id": "task-20260701-100000",
                "request": "Existing full task",
                "created_at": "2026-07-01T10:00:00+00:00",
                "proposed_by": "dave",
                "title": "Existing full task"
            }
        ]
    }
    isolated_env["state_file"].write_text(json.dumps(state, indent=2))

    env = dict(os.environ)
    env["JULES_PROJECT_ROOT"] = str(isolated_env["root"])

    res = run_bash_script("migrate-task-metadata.sh", env=env, cwd=isolated_env["root"])
    assert res.returncode == 0, f"stdout: {res.stdout}, stderr: {res.stderr}"
    assert "Migrated metadata for 0 task(s)" in res.stdout

    state_data = json.loads(isolated_env["state_file"].read_text())
    h0 = state_data["history"][0]
    assert h0["created_at"] == "2026-07-01T10:00:00+00:00"
    assert h0["proposed_by"] == "dave"
    assert h0["title"] == "Existing full task"


def test_queue_runner_sorts_by_created_at(isolated_env):
    """test_queue_runner_sorts_by_created_at"""
    # Create two pending tasks with same priority (5) but different created_at
    task1 = {
        "id": "task-111",
        "request": "Task Created Later",
        "priority": 5,
        "created_at": "2026-09-18T20:00:00Z"
    }
    task2 = {
        "id": "task-222",
        "request": "Task Created Earlier",
        "priority": 5,
        "created_at": "2026-09-18T10:00:00Z"
    }

    (isolated_env["pending"] / "task-111.json").write_text(json.dumps(task1))
    (isolated_env["pending"] / "task-222.json").write_text(json.dumps(task2))

    env = dict(os.environ)
    env["JULES_PROJECT_ROOT"] = str(isolated_env["root"])

    res = run_bash_script("jules-queue-runner.sh", "--dry-run", "--once", env=env, cwd=isolated_env["root"])
    assert res.returncode == 0, f"stdout: {res.stdout}, stderr: {res.stderr}"

    # Selected task should be task-222 because created_at is earlier ("2026-09-18T10:00:00Z" < "2026-09-18T20:00:00Z")
    assert "Selected task for execution: task-222" in res.stdout


def test_normalize_created_at_from_id(tmp_path):
    """Verify normalize_created_at_state converts task-YYYYMMDD-HHMMSS to ISO created_at."""
    from smos.core.state import normalize_created_at_state

    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "history": [
            {
                "id": "task-20260920-155505",
                "created_at": "2026-09-20T12:00:00.000000",
                "title": "Task 1"
            }
        ],
        "active_task": {
            "id": "task-20260920-160000",
            "created_at": None,
            "title": "Task 2"
        }
    }), encoding="utf-8")

    count = normalize_created_at_state(state_file)
    assert count == 2

    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert data["history"][0]["created_at"] == "2026-09-20T15:55:05+00:00"
    assert data["active_task"]["created_at"] == "2026-09-20T16:00:00+00:00"


def test_normalize_created_at_idempotent(tmp_path):
    """Verify normalize_created_at_state is idempotent and returns 0 when already normalized."""
    from smos.core.state import normalize_created_at_state

    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "history": [
            {
                "id": "task-20260920-155505",
                "created_at": "2026-09-20T15:55:05+00:00",
                "title": "Task 1"
            }
        ]
    }), encoding="utf-8")

    count = normalize_created_at_state(state_file)
    assert count == 0
