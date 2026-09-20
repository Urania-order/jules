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


def test_admin_whitelist_has_run_task(client):
    """Verify 'run-task' is present in ADMIN_COMMAND_WHITELIST with expected timeout and script path."""
    from smos.api.main import ADMIN_COMMAND_WHITELIST
    assert "run-task" in ADMIN_COMMAND_WHITELIST
    cfg = ADMIN_COMMAND_WHITELIST["run-task"]
    assert cfg["exec"] == "./scripts/run-task.sh"
    assert cfg["fixed_args"] == []
    assert cfg["timeout"] == 1200


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


def test_run_next_returns_job_id(client, tmp_path):
    """Verify POST /api/admin/queue/run-next returns {started: True, job_id, filename} immediately."""
    add_res = client.post(
        "/api/admin/queue/add",
        json={"text": "Execute task cycle", "verify_task": "11"},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert add_res.status_code == 200
    filename = add_res.json()["filename"]

    # Mock subprocess.run so worker thread finishes cleanly
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (
        "=== [1/5] Dispatch ===\nTask ID: task-20260918-123456\n=== [5/5] Verify ===\nDone: task-20260918-123456",
        ""
    )
    mock_proc.returncode = 0

    with patch("subprocess.Popen", return_value=mock_proc):
        res = client.post(
            "/api/admin/queue/run-next",
            headers={"Authorization": "Bearer dev-operator-token"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["started"] is True
        assert "job_id" in data
        assert data["filename"] == filename


def test_run_next_async_completes_and_moves_to_completed_on_success(client, tmp_path):
    """Verify async run-next execution completes, updates job status, and moves files to completed/ on success."""
    import time

    add_res = client.post(
        "/api/admin/queue/add",
        json={"text": "Execute task cycle", "verify_task": "11"},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert add_res.status_code == 200
    filename = add_res.json()["filename"]
    meta_filename = Path(filename).stem + ".meta.json"

    pending_dir = tmp_path / ".jules" / "queue" / "pending"
    completed_dir = tmp_path / ".jules" / "queue" / "completed"

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (
        "=== [1/5] Dispatch ===\nTask ID: task-20260918-123456\n=== [5/5] Verify ===\nDone: task-20260918-123456",
        ""
    )
    mock_proc.returncode = 0

    with patch("subprocess.Popen", return_value=mock_proc):
        res = client.post(
            "/api/admin/queue/run-next",
            headers={"Authorization": "Bearer dev-operator-token"}
        )
        assert res.status_code == 200
        job_id = res.json()["job_id"]

        # Poll job endpoint until completed
        for _ in range(50):
            job_res = client.get(
                f"/api/admin/queue/jobs/{job_id}",
                headers={"Authorization": "Bearer dev-operator-token"}
            )
            assert job_res.status_code == 200
            job_data = job_res.json()
            if job_data["status"] == "completed":
                break
            time.sleep(0.05)

        assert job_data["status"] == "completed"
        assert job_data["exit_code"] == 0
        assert job_data["task_id"] == "task-20260918-123456"

    # Assert file lifecycle
    assert not (pending_dir / filename).exists()
    assert (completed_dir / filename).exists()
    assert (completed_dir / meta_filename).exists()


def test_queue_jobs_endpoint(client, tmp_path):
    """Verify GET /api/admin/queue/jobs returns list of recent jobs."""
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("Task ID: task-20260918-123456", "")
    mock_proc.returncode = 0

    client.post(
        "/api/admin/queue/add",
        json={"text": "Task A"},
        headers={"Authorization": "Bearer dev-operator-token"}
    )

    with patch("subprocess.Popen", return_value=mock_proc):
        res = client.post(
            "/api/admin/queue/run-next",
            headers={"Authorization": "Bearer dev-operator-token"}
        )
        assert res.status_code == 200

        jobs_res = client.get(
            "/api/admin/queue/jobs",
            headers={"Authorization": "Bearer dev-operator-token"}
        )
        assert jobs_res.status_code == 200
        jobs_list = jobs_res.json().get("jobs", [])
        assert len(jobs_list) >= 1
        assert jobs_list[0]["job_id"] == res.json()["job_id"]


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
