import pytest
import json
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from smos.api.main import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    jules_dir = tmp_path / ".jules"
    jules_dir.mkdir(parents=True, exist_ok=True)
    return TestClient(app)

def test_consult_settings_get_patch(client):
    admin_headers = {"Authorization": "Bearer dev-admin-token"}
    consultant_headers = {"Authorization": "Bearer dev-consultant-token"}

    # GET settings as admin
    res = client.get("/api/consult/settings", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "tokens" in data
    assert "rate_limits" in data
    assert "endpoints" in data

    # Consultant cannot GET settings
    res_forbidden = client.get("/api/consult/settings", headers=consultant_headers)
    assert res_forbidden.status_code == 403

    # PATCH settings as admin
    patch_payload = {
        "rate_limits": {"consultant": 200},
        "endpoints": {"/api/consult/state": True}
    }
    res_patch = client.patch("/api/consult/settings", json=patch_payload, headers=admin_headers)
    assert res_patch.status_code == 200
    updated = res_patch.json()
    assert updated["rate_limits"]["consultant"] == 200

def test_consult_token_regenerate(client):
    admin_headers = {"Authorization": "Bearer dev-admin-token"}

    res = client.post("/api/consult/tokens/consultant/regenerate", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["role"] == "consultant"
    new_token = data["token"]
    assert new_token != "dev-consultant-token"

    # Verify old token no longer works
    res_old = client.get("/api/consult/state", headers={"Authorization": "Bearer dev-consultant-token"})
    assert res_old.status_code == 403

    # Verify new token works
    res_new = client.get("/api/consult/state", headers={"Authorization": f"Bearer {new_token}"})
    assert res_new.status_code == 200

def test_consult_token_disable(client):
    admin_headers = {"Authorization": "Bearer dev-admin-token"}

    res = client.post("/api/consult/tokens/consultant/disable", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["disabled"] is True

    # Verify token is forbidden when disabled
    res_dis = client.get("/api/consult/state", headers={"Authorization": "Bearer dev-consultant-token"})
    assert res_dis.status_code == 403

def test_consult_endpoint_toggle(client):
    admin_headers = {"Authorization": "Bearer dev-admin-token"}
    consultant_headers = {"Authorization": "Bearer dev-consultant-token"}

    # Disable /api/consult/state
    patch_payload = {"endpoints": {"/api/consult/state": False}}
    res_patch = client.patch("/api/consult/settings", json=patch_payload, headers=admin_headers)
    assert res_patch.status_code == 200

    # Request disabled endpoint returns 403
    res_get = client.get("/api/consult/state", headers=consultant_headers)
    assert res_get.status_code in (403, 404)
    data = res_get.json()
    assert data["code"] == "CONSULT_ENDPOINT_DISABLED"

    # Re-enable endpoint
    client.patch("/api/consult/settings", json={"endpoints": {"/api/consult/state": True}}, headers=admin_headers)
    res_ok = client.get("/api/consult/state", headers=consultant_headers)
    assert res_ok.status_code == 200

def test_consult_audit_log(client):
    consultant_headers = {"Authorization": "Bearer dev-consultant-token"}

    # Make consult request
    client.get("/api/consult/health?public=1")
    client.get("/api/consult/state", headers=consultant_headers)

    # Get audit log
    res = client.get("/api/consult/audit?limit=50", headers=consultant_headers)
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)
    assert len(logs) >= 2
    last_log = logs[0]
    assert "timestamp" in last_log
    assert "role" in last_log
    assert "method" in last_log
    assert "path" in last_log
    assert "status_code" in last_log

def test_consult_rate_limit_per_role(client):
    admin_headers = {"Authorization": "Bearer dev-admin-token"}
    consultant_headers = {"Authorization": "Bearer dev-consultant-token"}

    # Set consultant rate limit to 2 for testing
    client.patch("/api/consult/settings", json={"rate_limits": {"consultant": 2}}, headers=admin_headers)

    # First 2 requests succeed
    r1 = client.get("/api/consult/state", headers=consultant_headers)
    assert r1.status_code == 200
    r2 = client.get("/api/consult/state", headers=consultant_headers)
    assert r2.status_code == 200

    # 3rd request exceeds limit -> 429
    r3 = client.get("/api/consult/state", headers=consultant_headers)
    assert r3.status_code == 429
    assert r3.json()["code"] == "CONSULT_RATE_LIMIT_EXCEEDED"
