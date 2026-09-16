import subprocess
import pytest
from pathlib import Path
from smos.adapters.jules_cli import JulesCLIAdapter

PROJECT_ROOT = Path(__file__).parent.parent


def test_cli_adapter_add_task(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))

    pending_dir = tmp_path / ".jules" / "queue" / "pending"
    running_dir = tmp_path / ".jules" / "queue" / "running"
    completed_dir = tmp_path / ".jules" / "queue" / "completed"

    pending_dir.mkdir(parents=True, exist_ok=True)
    running_dir.mkdir(parents=True, exist_ok=True)
    completed_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = PROJECT_ROOT / "scripts"
    adapter = JulesCLIAdapter(scripts_dir=scripts_dir)
    res = adapter.add_task("Test task from unit test", priority=3)
    assert res["success"] is True
    assert "Task added to queue successfully" in res["stdout"]

    isolated_pending_files = list(pending_dir.glob("task-*.json"))
    assert len(isolated_pending_files) == 1

    real_pending_dir = PROJECT_ROOT / ".jules" / "queue" / "pending"
    if real_pending_dir.exists():
        real_pending_files = list(real_pending_dir.glob("task-*.json"))
        assert isolated_pending_files[0] not in real_pending_files


def test_cli_adapter_nonexistent_script(tmp_path):
    adapter = JulesCLIAdapter(scripts_dir=tmp_path)
    res = adapter.add_task("Test non-existent", priority=1)
    assert res["success"] is False
    assert res["exit_code"] == 127
    assert "Script not found" in res["error"]


def test_cli_adapter_does_not_touch_real_queue(tmp_path, monkeypatch):
    git_status_before = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
        cwd=PROJECT_ROOT
    ).stdout

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))

    pending_dir = tmp_path / ".jules" / "queue" / "pending"
    running_dir = tmp_path / ".jules" / "queue" / "running"
    completed_dir = tmp_path / ".jules" / "queue" / "completed"

    pending_dir.mkdir(parents=True, exist_ok=True)
    running_dir.mkdir(parents=True, exist_ok=True)
    completed_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = PROJECT_ROOT / "scripts"
    adapter = JulesCLIAdapter(scripts_dir=scripts_dir)
    res = adapter.add_task("Test task isolation check", priority=3)
    assert res["success"] is True

    git_status_after = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
        cwd=PROJECT_ROOT
    ).stdout

    assert git_status_before == git_status_after
