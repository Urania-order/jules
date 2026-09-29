import json
import subprocess
from pathlib import Path
from fastapi.testclient import TestClient
from smos.api.main import app

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer dev-operator-token"}


def test_post_tasks_with_test_header_returns_ephemeral():
    resp = client.post(
        "/api/tasks",
        json={"request": "Ephemeral Test Task", "priority": 1},
        headers={**AUTH_HEADERS, "X-Cosmos-Test": "1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"].startswith("test-")
    assert data["status"] == "EPHEMERAL"
    assert data["is_test"] is True
    assert data["request"] == "Ephemeral Test Task"


def test_post_tasks_with_test_header_does_not_create_queue_file(tmp_path):
    queue_pending = Path(".jules/queue/pending")
    queue_deferred = Path(".jules/queue/deferred")
    pending_before = set(queue_pending.glob("*.json")) if queue_pending.exists() else set()
    deferred_before = set(queue_deferred.glob("*.json")) if queue_deferred.exists() else set()

    resp = client.post(
        "/api/tasks",
        json={"request": "Ephemeral Task Queue Check", "priority": 2},
        headers={**AUTH_HEADERS, "X-Cosmos-Test": "1"},
    )
    assert resp.status_code == 200

    pending_after = set(queue_pending.glob("*.json")) if queue_pending.exists() else set()
    deferred_after = set(queue_deferred.glob("*.json")) if queue_deferred.exists() else set()

    assert pending_before == pending_after
    assert deferred_before == deferred_after


def test_post_tasks_with_test_header_does_not_appear_in_api_tasks():
    resp_create = client.post(
        "/api/tasks",
        json={"request": "Ephemeral API List Check", "priority": 3},
        headers={**AUTH_HEADERS, "X-Cosmos-Test": "1"},
    )
    assert resp_create.status_code == 200
    ephemeral_id = resp_create.json()["id"]

    resp_list = client.get("/api/tasks", headers=AUTH_HEADERS)
    assert resp_list.status_code == 200
    tasks = resp_list.json()
    task_ids = [t.get("id") for t in tasks if isinstance(t, dict)]
    assert ephemeral_id not in task_ids


from unittest.mock import patch

def test_post_tasks_without_test_header_persists_normally():
    # Normal POST /api/tasks persists via JulesCLIAdapter and QueueManager
    # Mock adapter.add_task to avoid creating persistent files on disk during unit test runs
    mock_add_res = {
        "success": True,
        "exit_code": 0,
        "stdout": "Added task: task-20260929-mock-0001\nTask ID: task-20260929-mock-0001",
        "stderr": "",
        "error": None,
    }
    with patch("smos.adapters.jules_cli.JulesCLIAdapter.add_task", return_value=mock_add_res):
        resp = client.post(
            "/api/tasks",
            json={"request": "Normal Task Persistence Test", "priority": 5},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "cli_output" in data


def test_cleanup_script_removes_from_pending_and_deferred(tmp_path):
    pending_dir = Path(".jules/queue/pending")
    deferred_dir = Path(".jules/queue/deferred")
    pending_dir.mkdir(parents=True, exist_ok=True)
    deferred_dir.mkdir(parents=True, exist_ok=True)

    fake_pending = pending_dir / "test_leak_pending.json"
    fake_deferred = deferred_dir / "test_leak_deferred.json"

    fake_pending.write_text(json.dumps({"id": "p1", "request": "Graph Task Test"}), encoding="utf-8")
    fake_deferred.write_text(json.dumps({"id": "d1", "request": "Graph Task Test"}), encoding="utf-8")

    try:
        res = subprocess.run(["./scripts/clean-test-tasks.sh"], capture_output=True, text=True, check=True)
        assert "Removed" in res.stdout
        assert not fake_pending.exists()
        assert not fake_deferred.exists()
    finally:
        if fake_pending.exists():
            fake_pending.unlink()
        if fake_deferred.exists():
            fake_deferred.unlink()


def test_cleanup_script_preserves_other_tasks():
    pending_dir = Path(".jules/queue/pending")
    pending_dir.mkdir(parents=True, exist_ok=True)

    other_task = pending_dir / "legitimate_task.json"
    other_task.write_text(json.dumps({"id": "real1", "request": "Real user request"}), encoding="utf-8")

    try:
        res = subprocess.run(["./scripts/clean-test-tasks.sh"], capture_output=True, text=True, check=True)
        assert res.returncode == 0
        assert other_task.exists()
    finally:
        if other_task.exists():
            other_task.unlink()


def test_cleanup_script_idempotent():
    res1 = subprocess.run(["./scripts/clean-test-tasks.sh"], capture_output=True, text=True, check=True)
    res2 = subprocess.run(["./scripts/clean-test-tasks.sh"], capture_output=True, text=True, check=True)
    assert res1.returncode == 0
    assert res2.returncode == 0
    assert "Removed 0 test task files" in res2.stdout


def test_no_graph_task_test_in_api_tasks_after_tests():
    resp = client.get("/api/tasks", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    tasks = resp.json()
    for task in tasks:
        req = task.get("request") or task.get("title") or ""
        # Real leak has request == "Graph Task Test" (first line == whole request).
        # Tasks that merely contain the phrase as example text (like the TASK
        # description itself) are NOT leaks.
        first_line = req.split("\n")[0].strip()
        assert first_line != "Graph Task Test", (
            f"Leaked test task: {task.get('id')}"
        )
