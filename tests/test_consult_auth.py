import pytest
import hmac
from unittest.mock import patch
from fastapi.testclient import TestClient
from smos.api.main import app

import shutil
from pathlib import Path

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    jules_queue = tmp_path / ".jules" / "queue"
    for d in ["pending", "running", "completed", "proposed", "deferred"]:
        (jules_queue / d).mkdir(parents=True, exist_ok=True)

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    project_scripts = Path(__file__).parent.parent / "scripts"
    if project_scripts.exists():
        for s in project_scripts.glob("*.sh"):
            dest = scripts_dir / s.name
            shutil.copy(s, dest)
            dest.chmod(0o755)

    return TestClient(app)


def test_consult_missing_token_401(client):
    """Missing Authorization header returns 401 CONSULT_AUTH_REQUIRED."""
    res = client.get("/api/consult/state")
    assert res.status_code == 401
    data = res.json()
    assert data["status"] == "error"
    assert data["code"] == "CONSULT_AUTH_REQUIRED"
    assert data["exit_code"] is None


def test_consult_bad_token_403(client):
    """Invalid token in Authorization header returns 403 CONSULT_AUTH_INVALID."""
    res = client.get("/api/consult/state", headers={"Authorization": "Bearer invalid-secret-token"})
    assert res.status_code == 403
    data = res.json()
    assert data["status"] == "error"
    assert data["code"] == "CONSULT_AUTH_INVALID"
    assert data["exit_code"] is None


def test_consultant_can_read_state(client):
    """Consultant role can access read-only consult endpoints."""
    res = client.get("/api/consult/state", headers={"Authorization": "Bearer dev-consultant-token"})
    assert res.status_code == 200
    data = res.json()
    assert data["read_only"] is True
    assert "system_status" in data


def test_consultant_cannot_create_task(client):
    """Consultant role is forbidden from creating tasks."""
    res = client.post(
        "/api/tasks",
        json={"request": "Unauthorized task", "priority": 3},
        headers={"Authorization": "Bearer dev-consultant-token"}
    )
    assert res.status_code == 403
    data = res.json()
    assert data["status"] == "error"
    assert data["code"] == "CONSULT_ROLE_FORBIDDEN"


def test_consultant_cannot_edit_task(client):
    """Consultant role is forbidden from editing tasks."""
    res = client.patch(
        "/api/tasks/task-20260916-000000-0001",
        json={"title": "Unauthorized patch"},
        headers={"Authorization": "Bearer dev-consultant-token"}
    )
    assert res.status_code == 403
    data = res.json()
    assert data["status"] == "error"
    assert data["code"] == "CONSULT_ROLE_FORBIDDEN"


def test_consultant_cannot_run_batch(client):
    """Consultant role is forbidden from running batch tasks."""
    res = client.post(
        "/api/batch/run",
        json={"task_ids": ["task-1"], "confirm": True},
        headers={"Authorization": "Bearer dev-consultant-token"}
    )
    assert res.status_code == 403
    data = res.json()
    assert data["status"] == "error"
    assert data["code"] == "CONSULT_ROLE_FORBIDDEN"


def test_operator_can_create_task(client):
    """Operator role can create tasks."""
    res = client.post(
        "/api/tasks",
        json={"request": "Operator Created Task", "priority": 3},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"


def test_operator_can_edit_task(client):
    """Operator role can edit tasks."""
    # First create task
    res_add = client.post(
        "/api/tasks",
        json={"request": "Task To Edit", "priority": 3},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    task_id = res_add.json()["task"]["id"]

    res_patch = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Operator Edited Title"},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["title"] == "Operator Edited Title"


def test_operator_can_run_batch(client):
    """Operator role can run batch tasks."""
    res = client.post(
        "/api/batch/run",
        json={"task_ids": ["task-1"], "schedule": "now", "confirm": True},
        headers={"Authorization": "Bearer dev-operator-token"}
    )
    assert res.status_code in (200, 400)
    # Status code is 200 or 400 (if task doesn't exist), but NOT 401 or 403
    assert res.status_code not in (401, 403)


def test_admin_can_do_everything_operator_can(client):
    """Admin role can access consult endpoints and run write operations."""
    # Read state
    res_read = client.get("/api/consult/state", headers={"Authorization": "Bearer dev-admin-token"})
    assert res_read.status_code == 200

    # Create task
    res_create = client.post(
        "/api/tasks",
        json={"request": "Admin Created Task", "priority": 5},
        headers={"Authorization": "Bearer dev-admin-token"}
    )
    assert res_create.status_code == 200
    task_id = res_create.json()["task"]["id"]

    # Edit task
    res_edit = client.patch(
        f"/api/tasks/{task_id}",
        json={"priority": 1},
        headers={"Authorization": "Bearer dev-admin-token"}
    )
    assert res_edit.status_code == 200
    assert res_edit.json()["priority"] == 1


def test_health_public_with_query_param(client):
    """GET /api/consult/health with ?public=1 bypasses authentication."""
    res = client.get("/api/consult/health?public=1")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_health_requires_auth_without_public(client):
    """GET /api/consult/health without ?public=1 requires authentication."""
    res = client.get("/api/consult/health")
    assert res.status_code == 401
    data = res.json()
    assert data["code"] == "CONSULT_AUTH_REQUIRED"


def test_constant_time_compare_used(client):
    """Verify hmac.compare_digest is invoked during authentication resolution."""
    with patch("hmac.compare_digest", wraps=hmac.compare_digest) as mock_compare:
        res = client.get("/api/consult/state", headers={"Authorization": "Bearer dev-consultant-token"})
        assert res.status_code == 200
        assert mock_compare.called
