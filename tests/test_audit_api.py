"""Unit and integration tests for Co-SMOS Audit API endpoints."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from smos.api.main import app


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_audit_reports_endpoint_empty(client, tmp_path, monkeypatch):
    """Verify GET /api/audit/reports returns empty list when INDEX.md is missing."""
    monkeypatch.chdir(tmp_path)
    response = client.get("/api/audit/reports")
    assert response.status_code == 200
    assert response.json() == []


def test_audit_reports_endpoint_with_data(client, tmp_path, monkeypatch):
    """Verify GET /api/audit/reports parses INDEX.md correctly."""
    monkeypatch.chdir(tmp_path)
    reports_dir = tmp_path / "docs" / "audit-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    index_file = reports_dir / "INDEX.md"
    index_file.write_text(
        "# Co-SMOS — Audit Reports Index\n\n"
        "| Task ID | Saved At (UTC) | Decision | Lines | HEAD | Report |\n"
        "|---|---|---|---|---|---|\n"
        "| task-20261015-122801 | 2026-10-15T14:27:30Z | Final Decision: READY_FOR_M-02_IMPLEMENTATION | 224 | a2ad2f3 | [report](task-20261015-122801-report.md) |\n",
        encoding="utf-8",
    )

    response = client.get("/api/audit/reports")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["task_id"] == "task-20261015-122801"
    assert data[0]["saved_at"] == "2026-10-15T14:27:30Z"
    assert data[0]["decision"] == "Final Decision: READY_FOR_M-02_IMPLEMENTATION"
    assert data[0]["lines"] == 224
    assert data[0]["head"] == "a2ad2f3"
    assert data[0]["report_url"] == "task-20261015-122801-report.md"


def test_audit_report_get_by_id(client, tmp_path, monkeypatch):
    """Verify GET /api/audit/reports/{task_id} returns report markdown."""
    monkeypatch.chdir(tmp_path)
    reports_dir = tmp_path / "docs" / "audit-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / "task-20261015-122801-report.md"
    report_file.write_text("# Test Report\n\nDecision: READY", encoding="utf-8")

    response = client.get("/api/audit/reports/task-20261015-122801")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "# Test Report" in response.text


def test_audit_report_get_missing(client, tmp_path, monkeypatch):
    """Verify GET /api/audit/reports/{task_id} returns 404 for missing report."""
    monkeypatch.chdir(tmp_path)
    reports_dir = tmp_path / "docs" / "audit-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    response = client.get("/api/audit/reports/task-20261015-999999")
    assert response.status_code == 404


def test_audit_report_invalid_task_id_returns_400(client):
    """Verify GET /api/audit/reports/{task_id} returns 400 for invalid task ID format."""
    response = client.get("/api/audit/reports/invalid-task-id")
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_task_id"


def test_audit_report_path_traversal_returns_400(client):
    """Verify GET /api/audit/reports/{task_id} rejects path traversal attempts."""
    response = client.get("/api/audit/reports/task-20261015-122801..slash..other")
    assert response.status_code == 400


def test_audit_active_endpoint(client, tmp_path, monkeypatch):
    """Verify GET /api/audit/active returns active task details."""
    monkeypatch.chdir(tmp_path)
    cosmos_dir = tmp_path / ".co-smos"
    cosmos_dir.mkdir(parents=True, exist_ok=True)
    state_file = cosmos_dir / "state.json"
    state_file.write_text(
        json.dumps({
            "active_task": {
                "id": "task-20261015-145701",
                "status": "RUNNING",
                "started_at": "2026-10-15T15:00:00Z",
                "unrelated_secret": "FORBIDDEN_FIELD"
            }
        }),
        encoding="utf-8",
    )

    response = client.get("/api/audit/active")
    assert response.status_code == 200
    data = response.json()
    assert "active_task" in data
    assert data["active_task"]["id"] == "task-20261015-145701"
    assert data["active_task"]["status"] == "RUNNING"
    assert data["active_task"]["started_at"] == "2026-10-15T15:00:00Z"
    # Guardrail B: Verify unrelated state fields are NOT exposed
    assert "unrelated_secret" not in data["active_task"]


def test_audit_active_no_active_task(client, tmp_path, monkeypatch):
    """Verify GET /api/audit/active returns None active_task when missing."""
    monkeypatch.chdir(tmp_path)
    response = client.get("/api/audit/active")
    assert response.status_code == 200
    assert response.json() == {"active_task": None}


def test_audit_trail_endpoint(client, tmp_path, monkeypatch):
    """Verify GET /api/audit/trail builds trail from actual report files."""
    monkeypatch.chdir(tmp_path)
    reports_dir = tmp_path / "docs" / "audit-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    index_file = reports_dir / "INDEX.md"
    index_file.write_text(
        "# Co-SMOS — Audit Reports Index\n\n"
        "| Task ID | Saved At (UTC) | Decision | Lines | HEAD | Report |\n"
        "|---|---|---|---|---|---|\n"
        "| task-20261015-122801 | 2026-10-15T14:27:30Z | READY_FOR_M-02 | 100 | a2ad2f3 | [report](task-20261015-122801-report.md) |\n",
        encoding="utf-8",
    )

    report_file = reports_dir / "task-20261015-122801-report.md"
    report_file.write_text("Report referencing task-20261015-100000 in text.", encoding="utf-8")

    response = client.get("/api/audit/trail")
    assert response.status_code == 200
    trail = response.json()
    assert len(trail) == 1
    assert trail[0]["task_id"] == "task-20261015-122801"
    assert trail[0]["decision"] == "READY_FOR_M-02"
    assert trail[0]["links"] == ["task-20261015-100000"]


def test_audit_trail_does_not_assume_planned_chain(client, tmp_path, monkeypatch):
    """Guardrail C: Verify audit trail contains ONLY actual report items, no assumed planned chains."""
    monkeypatch.chdir(tmp_path)
    reports_dir = tmp_path / "docs" / "audit-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    index_file = reports_dir / "INDEX.md"
    index_file.write_text(
        "# Co-SMOS — Audit Reports Index\n\n"
        "| Task ID | Saved At (UTC) | Decision | Lines | HEAD | Report |\n"
        "|---|---|---|---|---|---|\n"
        "| task-20261015-122801 | 2026-10-15T14:27:30Z | READY_FOR_M-02 | 100 | a2ad2f3 | [report](task-20261015-122801-report.md) |\n",
        encoding="utf-8",
    )

    response = client.get("/api/audit/trail")
    trail = response.json()
    task_ids = [t["task_id"] for t in trail]
    assert "task-20261015-122801" in task_ids
    # Planned unexecuted tasks like M-02 must NOT appear in trail
    assert "task-20261015-999999" not in task_ids


def test_audit_verify_endpoint(client):
    """Verify POST /api/audit/verify returns verification status JSON."""
    response = client.post("/api/audit/verify")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "total" in data
    assert "missing" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["missing"], list)


def test_audit_save_endpoint_returns_501(client):
    """Verify POST /api/audit/save returns HTTP 501 Not Implemented per Guardrail E."""
    response = client.post("/api/audit/save", json={"task_id": "task-20261015-122801"})
    assert response.status_code == 501


def test_audit_save_returns_cli_command(client):
    """Verify POST /api/audit/save response contains error message and copyable CLI command."""
    response = client.post("/api/audit/save", json={"task_id": "task-20261015-122801"})
    assert response.status_code == 501
    data = response.json()
    assert "error" in data
    assert "clipboard access not available" in data["error"]
    assert "cli_command" in data
    assert "./scripts/jules-audit-report.sh task-20261015-122801" in data["cli_command"]
