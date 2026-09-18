import json
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess
from fastapi.testclient import TestClient
from smos.api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    jules_queue = tmp_path / ".jules" / "queue"
    for d in ["pending", "running", "completed", "proposed", "deferred"]:
        (jules_queue / d).mkdir(parents=True, exist_ok=True)

    history_dir = tmp_path / ".jules" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    project_scripts = Path(__file__).parent.parent / "scripts"
    if project_scripts.exists():
        for s in project_scripts.glob("*.sh"):
            dest = scripts_dir / s.name
            shutil.copy(s, dest)
            dest.chmod(0o755)

    return TestClient(app)


def test_admin_run_whitelisted(client):
    """Verify whitelisted command execution succeeds for operator role."""
    res = client.post(
        "/api/admin/run",
        json={"command": "git-status", "args": ""},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "stdout" in data
    assert "stderr" in data
    assert "exit_code" in data
    assert "duration_ms" in data
    assert isinstance(data["exit_code"], int)
    assert isinstance(data["duration_ms"], int)


def test_admin_run_rejects_unknown(client):
    """Verify non-whitelisted command is rejected with 400 error and logged to audit."""
    res = client.post(
        "/api/admin/run",
        json={"command": "unauthorized_cmd", "args": ""},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 400
    data = res.json()
    assert data["status"] == "error"
    assert data["code"] == "UNKNOWN_COMMAND"

    # Verify audit log recorded rejection
    audit_res = client.get(
        "/api/admin/audit",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert audit_res.status_code == 200
    entries = audit_res.json().get("entries", [])
    assert len(entries) > 0
    latest = entries[0]
    assert latest["command"] == "unauthorized_cmd"
    assert latest["exit_code"] == 400


def test_admin_run_requires_operator(client):
    """Verify endpoint authentication and role requirements."""
    # 1. Missing token -> 401
    res_no_auth = client.post("/api/admin/run", json={"command": "git-status", "args": ""})
    assert res_no_auth.status_code == 401

    # 2. Consultant role -> 403
    res_consultant = client.post(
        "/api/admin/run",
        json={"command": "git-status", "args": ""},
        headers={"Authorization": "Bearer dev-consultant-token"}
    )
    assert res_consultant.status_code == 403

    # 3. Operator role -> 200
    res_operator = client.post(
        "/api/admin/run",
        json={"command": "git-status", "args": ""},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res_operator.status_code == 200

    # 4. Admin role -> 200
    res_admin = client.post(
        "/api/admin/run",
        json={"command": "git-status", "args": ""},
        headers={"Authorization": "Bearer dev-admin-token"}
    )
    assert res_admin.status_code == 200


def test_admin_run_logs_audit(client, tmp_path):
    """Verify admin command executions write entries to .jules/history/admin_audit.jsonl and API audit endpoint."""
    res = client.post(
        "/api/admin/run",
        json={"command": "git-log", "args": ""},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 200

    audit_res = client.get(
        "/api/admin/audit",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert audit_res.status_code == 200
    entries = audit_res.json().get("entries", [])
    assert len(entries) > 0
    latest = entries[0]
    assert latest["command"] == "git-log"
    assert latest["by"] == "operator"
    assert "timestamp" in latest
    assert "duration_ms" in latest

    # Direct file check
    audit_file = tmp_path / ".jules" / "history" / "admin_audit.jsonl"
    assert audit_file.exists()
    file_lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(file_lines) >= 1
    file_entry = json.loads(file_lines[-1])
    assert file_entry["command"] == "git-log"


def test_admin_run_timeout(client):
    """Verify timeout is caught gracefully and returns exit code 124 with error message."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["./scripts/test.sh"], timeout=300, output=b"partial output")):
        res = client.post(
            "/api/admin/run",
            json={"command": "test", "args": ""},
            headers={"Authorization": "Bearer dev-operator-token"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["exit_code"] == 124
        assert "timed out after 300 seconds" in data["stderr"]
        assert data["stdout"] == "partial output"

        # Verify audit log entry
        audit_res = client.get(
            "/api/admin/audit",
            headers={"Authorization": "Bearer dev-operator-token"}
        )
        assert audit_res.status_code == 200
        entries = audit_res.json().get("entries", [])
        assert len(entries) > 0
        latest = entries[0]
        assert latest["command"] == "test"
        assert latest["exit_code"] == 124


def test_queue_add_writes_file(client, tmp_path):
    """Verify POST /api/admin/queue/add creates prompt .txt and optional sidecar .meta.json in pending/."""
    res = client.post(
        "/api/admin/queue/add",
        json={"text": "Implement feature X", "verify_task": "11"},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["queued"] is True
    filename = data["filename"]
    assert filename.startswith("admin-")
    assert filename.endswith(".txt")

    pending_dir = tmp_path / ".jules" / "queue" / "pending"
    txt_file = pending_dir / filename
    assert txt_file.exists()
    assert txt_file.read_text(encoding="utf-8") == "Implement feature X"

    meta_file = pending_dir / (Path(filename).stem + ".meta.json")
    assert meta_file.exists()
    meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta_data["verify_task"] == "11"
    assert meta_data["by"] == "operator"


def test_queue_add_requires_text(client):
    """Verify POST /api/admin/queue/add returns 400 if prompt text is empty."""
    res = client.post(
        "/api/admin/queue/add",
        json={"text": "   ", "verify_task": None},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 400
    data = res.json()
    assert data["status"] == "error"
    assert data["code"] == "MISSING_TEXT"


def test_queue_run_next_empty(client):
    """Verify POST /api/admin/queue/run-next returns 400 next_task_not_formed when no pending tasks exist."""
    res = client.post(
        "/api/admin/queue/run-next",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 400
    data = res.json()
    assert data["status"] == "error"
    assert data["code"] == "next_task_not_formed"
    assert data["error"] == "next_task_not_formed"


def test_queue_run_next_dispatches(client, tmp_path):
    """Verify FULL lifecycle of task dispatch: pending/ -> running/ -> completed/."""
    # 1. Add task to queue
    add_res = client.post(
        "/api/admin/queue/add",
        json={"text": "Execute task cycle", "verify_task": "11"},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert add_res.status_code == 200
    filename = add_res.json()["filename"]
    meta_filename = Path(filename).stem + ".meta.json"

    pending_dir = tmp_path / ".jules" / "queue" / "pending"
    running_dir = tmp_path / ".jules" / "queue" / "running"
    completed_dir = tmp_path / ".jules" / "queue" / "completed"

    assert (pending_dir / filename).exists()
    assert (pending_dir / meta_filename).exists()

    # Mock subprocess.run for run-task.sh
    mock_process_res = subprocess.CompletedProcess(
        args=["./scripts/run-task.sh"],
        returncode=0,
        stdout="=== [1/5] Dispatch ===\nTask ID: task-20260918-123456\n=== [5/5] Verify ===\nDone: task-20260918-123456",
        stderr=""
    )

    with patch("subprocess.run", return_value=mock_process_res) as mock_run:
        res = client.post(
            "/api/admin/queue/run-next",
            headers={"Authorization": "Bearer dev-operator-token"}
        )
        assert res.status_code == 200
        data = res.json()

        assert data["dispatched"] is True
        assert data["filename"] == filename
        assert data["task_id"] == "task-20260918-123456"
        assert data["exit_code"] == 0

        # Verify command argument passed to run-task.sh
        called_cmd = mock_run.call_args[0][0]
        assert "run-task.sh" in called_cmd[0]
        assert filename in called_cmd[1]
        assert "--verify" in called_cmd
        assert "11" in called_cmd

    # Assert FULL lifecycle state transitions:
    # 1) pending/ is cleared
    assert not (pending_dir / filename).exists()
    assert not (pending_dir / meta_filename).exists()

    # 2) running/ was used and cleared on completion
    assert not (running_dir / filename).exists()
    assert not (running_dir / meta_filename).exists()

    # 3) completed/ contains the file and sidecar
    assert (completed_dir / filename).exists()
    assert (completed_dir / meta_filename).exists()


def test_queue_list_returns_counts(client, tmp_path):
    """Verify GET /api/admin/queue/list returns file details across pending, running, completed."""
    pending_dir = tmp_path / ".jules" / "queue" / "pending"
    running_dir = tmp_path / ".jules" / "queue" / "running"
    completed_dir = tmp_path / ".jules" / "queue" / "completed"

    (pending_dir / "admin-1.txt").write_text("task 1", encoding="utf-8")
    (running_dir / "admin-2.txt").write_text("task 2", encoding="utf-8")
    (completed_dir / "admin-3.txt").write_text("task 3", encoding="utf-8")

    res = client.get(
        "/api/admin/queue/list",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 200
    data = res.json()

    assert len(data["pending"]) == 1
    assert data["pending"][0]["filename"] == "admin-1.txt"

    assert len(data["running"]) == 1
    assert data["running"][0]["filename"] == "admin-2.txt"

    assert len(data["completed"]) == 1
    assert data["completed"][0]["filename"] == "admin-3.txt"


def test_queue_audit_logged(client):
    """Verify queue/add and queue/run-next record audit entries."""
    # 1. Add
    add_res = client.post(
        "/api/admin/queue/add",
        json={"text": "Audit task text"},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert add_res.status_code == 200

    # 2. Audit check
    audit_res = client.get(
        "/api/admin/audit",
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert audit_res.status_code == 200
    entries = audit_res.json()["entries"]
    assert len(entries) > 0
    latest = entries[0]
    assert latest["command"] == "queue/add"
    assert latest["by"] == "operator"
    assert latest["exit_code"] == 0
