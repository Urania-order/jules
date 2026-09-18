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
