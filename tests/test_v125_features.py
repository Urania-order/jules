import json
import os
import shutil
import time
import subprocess
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from smos.api.main import app, RUN_JOBS
from smos.core.queue import QueueManager
from smos.core.task import TaskStatus


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    jules_queue = tmp_path / ".jules" / "queue"
    for d in ["pending", "running", "blocked", "completed", "proposed", "deferred"]:
        (jules_queue / d).mkdir(parents=True, exist_ok=True)

    history_dir = tmp_path / ".jules" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    cosmos_dir = tmp_path / ".co-smos"
    cosmos_dir.mkdir(parents=True, exist_ok=True)
    (cosmos_dir / "state.json").write_text("{}\n", encoding="utf-8")

    RUN_JOBS.clear()

    return TestClient(app)


def test_run_next_picks_oldest_by_birthtime(client, tmp_path):
    """Verify admin_queue_run_next picks oldest pending file by birthtime/mtime."""
    pending_dir = tmp_path / ".jules" / "queue" / "pending"

    f1 = pending_dir / "admin-newer.txt"
    f1.write_text("Newer task", encoding="utf-8")

    time.sleep(0.05)

    f2 = pending_dir / "admin-older.txt"
    f2.write_text("Older task", encoding="utf-8")

    # Artificially set st_mtime of f2 to earlier time
    old_time = time.time() - 100
    os.utime(str(f2), (old_time, old_time))

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("Task ID: task-20260920-000001", "")
    mock_proc.returncode = 0

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)
        res = client.post(
            "/api/admin/queue/run-next",
            headers={"Authorization": "Bearer dev-operator-token"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["started"] is True
        assert data["filename"] == "admin-older.txt"


def test_cancel_terminates_subprocess_graceful(client, tmp_path):
    """Verify POST /api/admin/queue/cancel/{job_id} calls proc.terminate()."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # running
    mock_proc.wait.return_value = 0

    job_id = "job-cancel-test"
    RUN_JOBS[job_id] = {
        "job_id": job_id,
        "status": "running",
        "filename": "admin-1234.txt",
        "started_at": "2026-09-20T00:00:00Z",
        "proc": mock_proc
    }

    res = client.post(
        f"/api/admin/queue/cancel/{job_id}",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"
    mock_proc.terminate.assert_called_once()


def test_kill_sends_sigkill(client, tmp_path):
    """Verify POST /api/admin/queue/kill/{job_id} calls proc.kill()."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # running

    job_id = "job-kill-test"
    RUN_JOBS[job_id] = {
        "job_id": job_id,
        "status": "running",
        "filename": "admin-5678.txt",
        "started_at": "2026-09-20T00:00:00Z",
        "proc": mock_proc
    }

    res = client.post(
        f"/api/admin/queue/kill/{job_id}",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "killed"
    mock_proc.kill.assert_called_once()


def test_cancel_moves_file_to_deferred(client, tmp_path):
    """Verify canceling job moves task file from running/ or blocked/ to deferred/."""
    running_dir = tmp_path / ".jules" / "queue" / "running"
    deferred_dir = tmp_path / ".jules" / "queue" / "deferred"

    txt_file = running_dir / "admin-cancel-file.txt"
    txt_file.write_text("Cancel test", encoding="utf-8")

    job_id = "job-cancel-move"
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    RUN_JOBS[job_id] = {
        "job_id": job_id,
        "status": "running",
        "filename": "admin-cancel-file.txt",
        "started_at": "2026-09-20T00:00:00Z",
        "proc": mock_proc
    }

    res = client.post(
        f"/api/admin/queue/cancel/{job_id}",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 200

    assert not txt_file.exists()
    assert (deferred_dir / "admin-cancel-file.txt").exists()


def test_kill_moves_file_to_deferred(client, tmp_path):
    """Verify killing job moves task file from running/ or blocked/ to deferred/."""
    blocked_dir = tmp_path / ".jules" / "queue" / "blocked"
    deferred_dir = tmp_path / ".jules" / "queue" / "deferred"

    txt_file = blocked_dir / "admin-kill-file.txt"
    txt_file.write_text("Kill test", encoding="utf-8")

    job_id = "job-kill-move"
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    RUN_JOBS[job_id] = {
        "job_id": job_id,
        "status": "running",
        "filename": "admin-kill-file.txt",
        "started_at": "2026-09-20T00:00:00Z",
        "proc": mock_proc
    }

    res = client.post(
        f"/api/admin/queue/kill/{job_id}",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 200

    assert not txt_file.exists()
    assert (deferred_dir / "admin-kill-file.txt").exists()


def test_queue_files_endpoint_sorted(client, tmp_path):
    """Verify GET /api/queue/files returns file cards sorted by ctime ASC across folders."""
    pending_dir = tmp_path / ".jules" / "queue" / "pending"

    f1 = pending_dir / "admin-2.txt"
    f1.write_text("Second file", encoding="utf-8")

    f2 = pending_dir / "admin-1.txt"
    f2.write_text("First file", encoding="utf-8")

    now = time.time()
    os.utime(str(f2), (now - 10, now - 10))
    os.utime(str(f1), (now, now))

    res = client.get(
        "/api/queue/files",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 200
    data = res.json()

    assert "pending" in data
    assert "running" in data
    assert "blocked" in data
    assert "completed" in data
    assert "deferred" in data

    pending_list = data["pending"]
    assert len(pending_list) == 2
    assert pending_list[0]["filename"] == "admin-1.txt"
    assert pending_list[1]["filename"] == "admin-2.txt"


def test_queue_file_delete_moves_to_deferred(client, tmp_path):
    """Verify DELETE /api/queue/files/{folder}/{filename} soft-deletes file to deferred/."""
    pending_dir = tmp_path / ".jules" / "queue" / "pending"
    deferred_dir = tmp_path / ".jules" / "queue" / "deferred"

    txt_file = pending_dir / "admin-del.txt"
    txt_file.write_text("Delete prompt", encoding="utf-8")

    meta_file = pending_dir / "admin-del.meta.json"
    meta_file.write_text("{}", encoding="utf-8")

    res = client.delete(
        "/api/queue/files/pending/admin-del.txt",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["deleted"] is True
    assert data["moved_to"] == "deferred"

    assert not txt_file.exists()
    assert not meta_file.exists()

    assert (deferred_dir / "admin-del.txt").exists()
    assert (deferred_dir / "admin-del.meta.json").exists()


def test_queue_file_delete_rejects_path_traversal(client, tmp_path):
    """Verify DELETE /api/queue/files/{folder}/{filename} rejects path traversal with 400."""
    res = client.delete(
        "/api/queue/files/pending/..%2F..%2Fetc%2Fpasswd",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code in (400, 404)


def test_list_all_tasks_excludes_cancelled(tmp_path, monkeypatch):
    """Verify QueueManager.list_all_tasks excludes CANCELLED tasks."""
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    cosmos_dir = tmp_path / ".co-smos"
    cosmos_dir.mkdir(parents=True, exist_ok=True)

    state_data = {
        "history": [
            {"id": "task-001", "status": "completed", "request": "Req 1"},
            {"id": "task-002", "status": "cancelled", "request": "Req 2"},
            {"id": "task-003", "status": "pending", "request": "Req 3"}
        ]
    }
    (cosmos_dir / "state.json").write_text(json.dumps(state_data), encoding="utf-8")

    qm = QueueManager(queue_dir=tmp_path / ".jules" / "queue")
    tasks = qm.list_all_tasks()

    t_ids = [t.id for t in tasks]
    assert "task-001" in t_ids
    assert "task-002" not in t_ids
    assert "task-003" in t_ids


def test_list_all_tasks_dedup_keeps_last(tmp_path, monkeypatch):
    """Verify QueueManager.list_all_tasks deduplicates candidates keeping the last state."""
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    cosmos_dir = tmp_path / ".co-smos"
    cosmos_dir.mkdir(parents=True, exist_ok=True)

    state_data = {
        "history": [
            {"id": "task-001", "status": "pending", "request": "Stale request"},
            {"id": "task-001", "status": "completed", "request": "Updated request"}
        ]
    }
    (cosmos_dir / "state.json").write_text(json.dumps(state_data), encoding="utf-8")

    qm = QueueManager(queue_dir=tmp_path / ".jules" / "queue")
    tasks = qm.list_all_tasks()

    assert len(tasks) == 1
    assert tasks[0].request == "Updated request"
    assert tasks[0].status == TaskStatus.COMPLETED


def test_task_from_dict_fallback_title_from_id(tmp_path, monkeypatch):
    """Verify QueueManager._task_from_dict falls back title/request from task id when missing."""
    qm = QueueManager(queue_dir=tmp_path / ".jules" / "queue")

    data = {"id": "task-20260920-120000"}
    task = qm._task_from_dict(data, default_status=TaskStatus.PENDING)

    assert task.request == "task-20260920-120000"
    assert task.title == "task-20260920-120000"


def test_task_from_dict_fallback_created_at_from_id(tmp_path, monkeypatch):
    """Verify QueueManager._task_from_dict parses created_at from task ID."""
    qm = QueueManager(queue_dir=tmp_path / ".jules" / "queue")

    data = {"id": "task-20260920-120000"}
    task = qm._task_from_dict(data, default_status=TaskStatus.PENDING)

    assert task.created_at == "2026-09-20T12:00:00+00:00"


def test_task_from_dict_fallback_proposed_by_unknown(tmp_path, monkeypatch):
    """Verify QueueManager._task_from_dict falls back proposed_by to 'unknown'."""
    qm = QueueManager(queue_dir=tmp_path / ".jules" / "queue")

    data = {"id": "task-101"}
    task = qm._task_from_dict(data, default_status=TaskStatus.PENDING)

    assert task.proposed_by == "unknown"


def test_jules_task_writes_full_active_task(tmp_path, monkeypatch):
    """Verify scripts/jules-task.sh writes full active_task dictionary."""
    # Setup mock git repo and jules CLI
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
    (tmp_path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=tmp_path, capture_output=True, check=True)

    mock_bin = tmp_path / "mock_bin"
    mock_bin.mkdir()
    (mock_bin / "jules").write_text("#!/usr/bin/env bash\nexit 0\n")
    (mock_bin / "jules").chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
    env["JULES_PROJECT_ROOT"] = str(tmp_path)

    script = Path(__file__).parent.parent / "scripts" / "jules-task.sh"
    res = subprocess.run(
        ["bash", str(script), "Task title line\nTask body line 2"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env
    )
    assert res.returncode == 0, res.stderr

    state_file = tmp_path / ".co-smos" / "state.json"
    assert state_file.exists()
    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    active = state_data.get("active_task")

    assert active is not None
    assert active["title"] == "Task title line"
    assert active["request"] == "Task title line\nTask body line 2"
    assert active["status"] == "RUNNING"
    assert active["priority"] == 5
    assert active["created_at"] is not None
    assert active["proposed_by"] == "operator"


def test_jules_complete_copies_title_from_active(tmp_path, monkeypatch):
    """Verify scripts/jules-complete.sh copies title field from active_task to completed record."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
    (tmp_path / "README.md").write_text("# Test\n")
    (tmp_path / ".gitignore").write_text(".jules/results/\n*.log\n.co-smos/state.json\n")
    subprocess.run(["git", "add", "README.md", ".gitignore"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=tmp_path, capture_output=True, check=True)

    (tmp_path / ".jules" / "results").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".jules" / "tasks").mkdir(parents=True, exist_ok=True)

    cosmos_dir = tmp_path / ".co-smos"
    cosmos_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "version": 1,
        "active_task": {
            "id": "task-20260920-150000",
            "request": "Feature request\nLine 2",
            "title": "Feature title",
            "priority": 5,
            "created_at": "2026-09-20T15:00:00+00:00",
            "started_at": "2026-09-20T15:00:05+00:00",
            "proposed_by": "operator",
            "source_task": None,
            "branch": "main"
        },
        "history": []
    }
    (cosmos_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    mock_bin = tmp_path / "mock_bin"
    mock_bin.mkdir()
    (mock_bin / "jules").write_text("#!/usr/bin/env bash\necho 'No diff found in the remote VM'\nexit 0\n")
    (mock_bin / "jules").chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
    env["JULES_PROJECT_ROOT"] = str(tmp_path)
    env["JULES_SKIP_TESTS"] = "1"
    env["JULES_NO_PUSH"] = "1"
    env["JULES_SKIP_CI"] = "1"

    script = Path(__file__).parent.parent / "scripts" / "jules-complete.sh"
    res = subprocess.run(
        ["bash", str(script), "sess-1"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env
    )
    assert res.returncode == 0, res.stderr

    state_data = json.loads((cosmos_dir / "state.json").read_text(encoding="utf-8"))
    last = state_data.get("last_task")
    assert last is not None
    assert last["title"] == "Feature title"


def test_jules_complete_copies_created_at_from_active(tmp_path, monkeypatch):
    """Verify scripts/jules-complete.sh copies created_at field from active_task to completed record."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
    (tmp_path / "README.md").write_text("# Test\n")
    (tmp_path / ".gitignore").write_text(".jules/results/\n*.log\n.co-smos/state.json\n")
    subprocess.run(["git", "add", "README.md", ".gitignore"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=tmp_path, capture_output=True, check=True)

    (tmp_path / ".jules" / "results").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".jules" / "tasks").mkdir(parents=True, exist_ok=True)

    cosmos_dir = tmp_path / ".co-smos"
    cosmos_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "version": 1,
        "active_task": {
            "id": "task-20260920-160000",
            "request": "Created at test",
            "title": "Created at test",
            "priority": 5,
            "created_at": "2026-09-20T16:00:00+00:00",
            "started_at": "2026-09-20T16:00:05+00:00",
            "proposed_by": "operator",
            "source_task": None,
            "branch": "main"
        },
        "history": []
    }
    (cosmos_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    mock_bin = tmp_path / "mock_bin"
    mock_bin.mkdir()
    (mock_bin / "jules").write_text("#!/usr/bin/env bash\necho 'No diff found in the remote VM'\nexit 0\n")
    (mock_bin / "jules").chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
    env["JULES_PROJECT_ROOT"] = str(tmp_path)
    env["JULES_SKIP_TESTS"] = "1"
    env["JULES_NO_PUSH"] = "1"
    env["JULES_SKIP_CI"] = "1"

    script = Path(__file__).parent.parent / "scripts" / "jules-complete.sh"
    res = subprocess.run(
        ["bash", str(script), "sess-2"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env
    )
    assert res.returncode == 0, res.stderr

    state_data = json.loads((cosmos_dir / "state.json").read_text(encoding="utf-8"))
    last = state_data.get("last_task")
    assert last is not None
    assert last["created_at"] == "2026-09-20T16:00:00+00:00"


def test_jules_complete_copies_proposed_by_from_active(tmp_path, monkeypatch):
    """Verify scripts/jules-complete.sh copies proposed_by field from active_task to completed record."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
    (tmp_path / "README.md").write_text("# Test\n")
    (tmp_path / ".gitignore").write_text(".jules/results/\n*.log\n.co-smos/state.json\n")
    subprocess.run(["git", "add", "README.md", ".gitignore"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=tmp_path, capture_output=True, check=True)

    (tmp_path / ".jules" / "results").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".jules" / "tasks").mkdir(parents=True, exist_ok=True)

    cosmos_dir = tmp_path / ".co-smos"
    cosmos_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "version": 1,
        "active_task": {
            "id": "task-20260920-170000",
            "request": "Proposed by test",
            "title": "Proposed by test",
            "priority": 5,
            "created_at": "2026-09-20T17:00:00+00:00",
            "started_at": "2026-09-20T17:00:05+00:00",
            "proposed_by": "consultant",
            "source_task": None,
            "branch": "main"
        },
        "history": []
    }
    (cosmos_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    mock_bin = tmp_path / "mock_bin"
    mock_bin.mkdir()
    (mock_bin / "jules").write_text("#!/usr/bin/env bash\necho 'No diff found in the remote VM'\nexit 0\n")
    (mock_bin / "jules").chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
    env["JULES_PROJECT_ROOT"] = str(tmp_path)
    env["JULES_SKIP_TESTS"] = "1"
    env["JULES_NO_PUSH"] = "1"
    env["JULES_SKIP_CI"] = "1"

    script = Path(__file__).parent.parent / "scripts" / "jules-complete.sh"
    res = subprocess.run(
        ["bash", str(script), "sess-3"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env
    )
    assert res.returncode == 0, res.stderr

    state_data = json.loads((cosmos_dir / "state.json").read_text(encoding="utf-8"))
    last = state_data.get("last_task")
    assert last is not None
    assert last["proposed_by"] == "consultant"
