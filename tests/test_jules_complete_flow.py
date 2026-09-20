import json
import os
import shutil
import subprocess
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def setup_complete_env(tmp_path, monkeypatch):
    """Sets up a mock repo environment for jules-complete.sh testing."""
    # Initialize git repo in tmp_path
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test Agent"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "agent@example.com"], cwd=tmp_path, check=True)

    # Directories
    cosmos_dir = tmp_path / ".co-smos"
    tasks_dir = tmp_path / ".jules" / "tasks"
    results_dir = tmp_path / ".jules" / "results"
    scripts_dir = tmp_path / "scripts"
    mock_bin = tmp_path / "mock_bin"

    cosmos_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    mock_bin.mkdir(parents=True, exist_ok=True)

    # Copy jules-complete.sh
    shutil.copy(PROJECT_ROOT / "scripts" / "jules-complete.sh", scripts_dir / "jules-complete.sh")
    (scripts_dir / "jules-complete.sh").chmod(0o755)

    # Create initial state.json
    task_id = "task-20260917-154042"
    session_id = "sess-12345"

    state = {
        "version": 1,
        "project": "jules-codespace",
        "agent": "jules",
        "status": "busy",
        "active_task": {
            "id": task_id,
            "session_id": session_id,
            "branch": "feat/test",
            "request": "Test task",
            "started_at": "2026-09-17T15:40:42Z",
        },
        "last_task": None,
        "history": [],
    }
    (cosmos_dir / "state.json").write_text(json.dumps(state, indent=2))

    # Task card and log
    (tasks_dir / f"{task_id}.md").write_text(f"# Task {task_id}\n\nInitial task description\n")
    (results_dir / f"{task_id}.log").write_text(f"ID: {session_id}\nStarted task\n")

    # Initial code commit
    (tmp_path / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=tmp_path, check=True)

    # Create mock jules binary
    mock_jules = mock_bin / "jules"
    mock_jules.write_text("""#!/usr/bin/env bash
if [ "$1" = "remote" ] && [ "$2" = "pull" ]; then
    echo "Pulled remote changes successfully."
    exit 0
fi
exit 0
""")
    mock_jules.chmod(0o755)

    # Create mock uv binary
    mock_uv = mock_bin / "uv"
    mock_uv.write_text("""#!/usr/bin/env bash
if [ "${MOCK_PYTEST_EXIT:-0}" = "1" ]; then
    echo "FAILED tests/test_example.py::test_fail - AssertionError: assert False"
    echo "1 failed in 0.05s"
    exit 1
else
    echo "1 passed in 0.01s"
    exit 0
fi
""")
    mock_uv.chmod(0o755)

    # Create mock gh binary
    mock_gh = mock_bin / "gh"
    mock_gh.write_text("""#!/usr/bin/env bash
if [ "$1" = "run" ] && [ "$2" = "list" ]; then
    status="${MOCK_CI_STATUS:-success}"
    if [ "$status" = "timeout" ]; then
        echo "null"
    elif [ "$status" = "failure" ]; then
        echo "failure"
    else
        echo "success"
    fi
    exit 0
fi
exit 0
""")
    mock_gh.chmod(0o755)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))

    return {
        "root": tmp_path,
        "scripts": scripts_dir,
        "mock_bin": mock_bin,
        "task_id": task_id,
        "session_id": session_id,
    }


def run_complete_script(env_info, *args, env_vars=None):
    env = dict(os.environ)
    env["PATH"] = f"{env_info['mock_bin']}:{env.get('PATH', '')}"
    env["JULES_PROJECT_ROOT"] = str(env_info["root"])
    if env_vars:
        env.update(env_vars)

    script_path = env_info["scripts"] / "jules-complete.sh"
    return subprocess.run(
        ["bash", str(script_path), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=env_info["root"],
    )


def test_tests_pass_then_commit(setup_complete_env):
    # Make a code change
    smos_file = setup_complete_env["root"] / "smos" / "module.py"
    smos_file.parent.mkdir(parents=True, exist_ok=True)
    smos_file.write_text("# New code feature\n")

    res = run_complete_script(
        setup_complete_env,
        "--task", setup_complete_env["task_id"],
        env_vars={"JULES_NO_PUSH": "1", "JULES_SKIP_CI": "1", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res.returncode == 0, f"Stdout: {res.stdout}\nStderr: {res.stderr}"
    assert "✅ Tests passed" in res.stdout
    assert "code commit done" in res.stdout

    # Verify git log contains commit
    log_res = subprocess.run(["git", "log", "-1", "--oneline"], cwd=setup_complete_env["root"], capture_output=True, text=True)
    assert "record Co-SMOS artifacts" in log_res.stdout or "apply Jules result" in log_res.stdout


def test_tests_fail_preserves_changes(setup_complete_env):
    smos_file = setup_complete_env["root"] / "smos" / "failing_feature.py"
    smos_file.parent.mkdir(parents=True, exist_ok=True)
    smos_file.write_text("# Broken code\n")

    res = run_complete_script(
        setup_complete_env,
        "--task", setup_complete_env["task_id"],
        env_vars={"MOCK_PYTEST_EXIT": "1"}
    )
    assert res.returncode == 1
    assert "❌ Tests FAILED" in res.stdout
    assert "→ Commits NOT created" in res.stdout
    assert "→ Changes preserved in working tree" in res.stdout

    # Assert file still exists with content preserved
    assert smos_file.exists()
    assert smos_file.read_text() == "# Broken code\n"


def test_tests_fail_no_auto_rollback(setup_complete_env):
    smos_file = setup_complete_env["root"] / "smos" / "untracked_file.py"
    smos_file.parent.mkdir(parents=True, exist_ok=True)
    smos_file.write_text("print('test')")

    res = run_complete_script(
        setup_complete_env,
        "--task", setup_complete_env["task_id"],
        env_vars={"MOCK_PYTEST_EXIT": "1"}
    )
    assert res.returncode == 1

    # Verify file is still present and untracked / preserved
    assert smos_file.exists()
    git_status = subprocess.run(["git", "status", "-u"], cwd=setup_complete_env["root"], capture_output=True, text=True)
    assert "smos/untracked_file.py" in git_status.stdout


def test_skip_tests_env(setup_complete_env):
    smos_file = setup_complete_env["root"] / "smos" / "code.py"
    smos_file.parent.mkdir(parents=True, exist_ok=True)
    smos_file.write_text("# Code\n")

    res = run_complete_script(
        setup_complete_env,
        "--task", setup_complete_env["task_id"],
        env_vars={"JULES_SKIP_TESTS": "1", "JULES_NO_PUSH": "1", "JULES_SKIP_CI": "1", "MOCK_PYTEST_EXIT": "1"}
    )
    assert res.returncode == 0
    assert "JULES_SKIP_TESTS=1: Skipping test execution." in res.stdout


def test_ci_success_reported(setup_complete_env):
    res = run_complete_script(
        setup_complete_env,
        "--task", setup_complete_env["task_id"],
        env_vars={"JULES_NO_PUSH": "0", "JULES_CI_TIMEOUT": "1", "MOCK_CI_STATUS": "success", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res.returncode == 0
    assert "✅ CI passed" in res.stdout


def test_ci_failure_does_not_force_push(setup_complete_env):
    res = run_complete_script(
        setup_complete_env,
        "--task", setup_complete_env["task_id"],
        env_vars={"JULES_NO_PUSH": "0", "JULES_CI_TIMEOUT": "1", "MOCK_CI_STATUS": "failure", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res.returncode == 1
    assert "❌ CI FAILED" in res.stdout
    assert "→ Commits ARE pushed" in res.stdout
    assert "→ To revert: git revert HEAD~2..HEAD && git push" in res.stdout


def test_ci_timeout_reported(setup_complete_env):
    res = run_complete_script(
        setup_complete_env,
        "--task", setup_complete_env["task_id"],
        env_vars={"JULES_NO_PUSH": "0", "JULES_CI_TIMEOUT": "1", "MOCK_CI_STATUS": "timeout", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res.returncode == 0
    assert "⏳ CI timeout" in res.stdout
    assert "→ Check manually: gh run list" in res.stdout


def test_log_file_created(setup_complete_env):
    res = run_complete_script(
        setup_complete_env,
        "--task", setup_complete_env["task_id"],
        env_vars={"JULES_NO_PUSH": "1", "JULES_SKIP_CI": "1", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res.returncode == 0

    log_files = list((setup_complete_env["root"] / ".jules" / "results").glob("post-complete-*.log"))
    assert len(log_files) >= 1

    content = log_files[0].read_text()
    assert "step=[1/9]" in content
    assert "step=[7/9]" in content
    assert "step=[9/9]" in content


def test_jules_complete_does_not_move_admin_queue_files(setup_complete_env):
    """Verify jules-complete.sh untracked cleanup preserves admin-*.txt and *.meta.json files in pending, running, completed."""
    queue_dir = setup_complete_env["root"] / ".jules" / "queue"
    pending_txt = queue_dir / "pending" / "admin-123.txt"
    pending_meta = queue_dir / "pending" / "admin-123.meta.json"
    running_txt = queue_dir / "running" / "admin-456.txt"
    running_meta = queue_dir / "running" / "admin-456.meta.json"
    completed_txt = queue_dir / "completed" / "admin-789.txt"
    completed_meta = queue_dir / "completed" / "admin-789.meta.json"

    for d in ["pending", "running", "completed"]:
        (queue_dir / d).mkdir(parents=True, exist_ok=True)

    pending_txt.write_text("prompt 123")
    pending_meta.write_text("{}")
    running_txt.write_text("prompt 456")
    running_meta.write_text("{}")
    completed_txt.write_text("prompt 789")
    completed_meta.write_text("{}")

    res = run_complete_script(
        setup_complete_env,
        "--task", setup_complete_env["task_id"],
        env_vars={"JULES_NO_PUSH": "1", "JULES_SKIP_CI": "1", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res.returncode == 0

    # Verify admin files were NOT moved to deferred/
    assert pending_txt.exists()
    assert pending_meta.exists()
    assert running_txt.exists()
    assert running_meta.exists()
    assert completed_txt.exists()
    assert completed_meta.exists()

    deferred_dir = queue_dir / "deferred"
    assert not (deferred_dir / "admin-123.txt").exists()
    assert not (deferred_dir / "admin-456.txt").exists()
    assert not (deferred_dir / "admin-789.txt").exists()


def test_jules_complete_no_op_allows_retry(setup_complete_env):
    """Verify jules-complete.sh allows retry when previous result was no-op (ERRATA-0036)."""
    state_file = setup_complete_env["root"] / ".co-smos" / "state.json"
    state = json.loads(state_file.read_text())
    task_id = setup_complete_env["task_id"]
    state["history"].append({
        "id": task_id,
        "status": "completed",
        "result": "no-op"
    })
    state["last_task"] = {
        "id": task_id,
        "status": "completed",
        "result": "no-op"
    }
    state_file.write_text(json.dumps(state, indent=2))

    res = run_complete_script(
        setup_complete_env,
        "--task", task_id,
        env_vars={"JULES_NO_PUSH": "1", "JULES_SKIP_CI": "1", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res.returncode == 0
    assert "Task " + task_id + " is already completed and applied." not in res.stdout


def test_jules_complete_force_flag(setup_complete_env):
    """Verify jules-complete.sh --force and FORCE=1 skip idempotency check even if result was applied."""
    state_file = setup_complete_env["root"] / ".co-smos" / "state.json"
    state = json.loads(state_file.read_text())
    task_id = setup_complete_env["task_id"]
    state["history"].append({
        "id": task_id,
        "status": "completed",
        "result": "applied"
    })
    state["last_task"] = {
        "id": task_id,
        "status": "completed",
        "result": "applied"
    }
    state_file.write_text(json.dumps(state, indent=2))

    # Test without force: should skip
    res_noforce = run_complete_script(
        setup_complete_env,
        "--task", task_id,
        env_vars={"JULES_NO_PUSH": "1", "JULES_SKIP_CI": "1", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res_noforce.returncode == 0
    assert "Task " + task_id + " is already completed and applied." in res_noforce.stdout

    # Test with --force argument: should execute
    res_force_arg = run_complete_script(
        setup_complete_env,
        "--task", task_id, "--force",
        env_vars={"JULES_NO_PUSH": "1", "JULES_SKIP_CI": "1", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res_force_arg.returncode == 0
    assert "Task " + task_id + " is already completed and applied." not in res_force_arg.stdout

    # Test with FORCE=1 env: should execute
    res_force_env = run_complete_script(
        setup_complete_env,
        "--task", task_id,
        env_vars={"FORCE": "1", "JULES_NO_PUSH": "1", "JULES_SKIP_CI": "1", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res_force_env.returncode == 0
    assert "Task " + task_id + " is already completed and applied." not in res_force_env.stdout


def test_jules_complete_preserves_title_from_task_file(setup_complete_env):
    """Verify scripts/jules-complete.sh preserves title from task .md file when active_task is missing or title is empty/equal to task_id."""
    state_file = setup_complete_env["root"] / ".co-smos" / "state.json"
    task_id = setup_complete_env["task_id"]

    # Set active_task to None or empty dictionary without title/request
    state = json.loads(state_file.read_text())
    state["active_task"] = None
    state_file.write_text(json.dumps(state, indent=2))

    # Write a task markdown file with ## Request section
    task_md = setup_complete_env["root"] / ".jules" / "tasks" / f"{task_id}.md"
    task_md.write_text(
        f"# Jules Task\n\n## Task ID\n\n{task_id}\n\n## Request\n\nCo-SMOS v1.2.8 — Feature title from task card\n\n## Status\n\nstarted\n"
    )

    res = run_complete_script(
        setup_complete_env,
        "--task", task_id,
        env_vars={"JULES_NO_PUSH": "1", "JULES_SKIP_CI": "1", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res.returncode == 0, f"Stdout: {res.stdout}\nStderr: {res.stderr}"

    updated_state = json.loads(state_file.read_text())
    last = updated_state.get("last_task")
    assert last is not None
    assert last["title"] == "Co-SMOS v1.2.8 — Feature title from task card"
    assert last["request"] == "Co-SMOS v1.2.8 — Feature title from task card"


def test_jules_complete_fallback_request_from_title(setup_complete_env):
    """Verify scripts/jules-complete.sh populates request from title when request is missing."""
    state_file = setup_complete_env["root"] / ".co-smos" / "state.json"
    task_id = setup_complete_env["task_id"]

    state = json.loads(state_file.read_text())
    state["active_task"] = {
        "id": task_id,
        "title": "Title present but request missing",
        "request": None,
        "session_id": setup_complete_env["session_id"]
    }
    state_file.write_text(json.dumps(state, indent=2))

    res = run_complete_script(
        setup_complete_env,
        "--task", task_id,
        env_vars={"JULES_NO_PUSH": "1", "JULES_SKIP_CI": "1", "MOCK_PYTEST_EXIT": "0"}
    )
    assert res.returncode == 0, f"Stdout: {res.stdout}\nStderr: {res.stderr}"

    updated_state = json.loads(state_file.read_text())
    last = updated_state.get("last_task")
    assert last is not None
    assert last["title"] == "Title present but request missing"
    assert last["request"] == "Title present but request missing"
