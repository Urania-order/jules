import pytest
import os
import json
from pathlib import Path
from fastapi.testclient import TestClient
from smos.api.main import app
from smos.core.queue import QueueManager
from smos.core.task import Task, TaskStatus

client = TestClient(app)
OPERATOR_HEADERS = {"Authorization": "Bearer dev-operator-token"}
CONSULTANT_HEADERS = {"Authorization": "Bearer dev-consultant-token"}


@pytest.fixture
def undo_env(tmp_path, monkeypatch):
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    qm = QueueManager(queue_dir=tmp_path / ".jules" / "queue")

    # Create and reset tasks to populate archive jsonl
    task1 = Task(
        id="task-undo-1",
        request="First archive task for undo",
        status=TaskStatus.READY,
        priority=2,
        source_task="src-001",
        proposed_by="operator"
    )
    task2 = Task(
        id="task-undo-2",
        request="Second archive task for search test",
        status=TaskStatus.RUNNING,
        priority=4,
        source_task="src-002",
        proposed_by="admin"
    )
    task3 = Task(
        id="task-undo-3",
        request="Third archive task completed",
        status=TaskStatus.COMPLETED,
        priority=1,
        source_task="src-003"
    )

    qm.save_task(task1)
    qm.save_task(task2)
    qm.save_task(task3)

    # Reset all tasks to archive them
    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=OPERATOR_HEADERS)
    assert res.status_code == 200

    return qm, tmp_path


def test_archive_list_returns_entries(undo_env):
    qm, tmp_path = undo_env

    res = client.get("/api/queue/archive", headers=OPERATOR_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "entries" in data
    entries = data["entries"]
    assert len(entries) == 3

    # Verify fields of entries
    e0 = entries[0]
    assert "archive_id" in e0
    assert ":" in e0["archive_id"]
    assert "task_id" in e0
    assert "status" in e0
    assert "request" in e0
    assert "priority" in e0
    assert "created_at" in e0
    assert "reset_at" in e0
    assert "scope" in e0
    assert "restored" in e0
    assert e0["restored"] is False


def test_undo_selected_creates_tasks(undo_env):
    qm, tmp_path = undo_env

    # Get archive list
    res_list = client.get("/api/queue/archive", headers=OPERATOR_HEADERS)
    entries = res_list.json()["entries"]
    target_aid = entries[0]["archive_id"]

    # Call undo endpoint
    res_undo = client.post(
        "/api/queue/archive/undo",
        json={"archive_ids": [target_aid], "confirm": "UNDO"},
        headers=OPERATOR_HEADERS
    )
    assert res_undo.status_code == 200
    data_undo = res_undo.json()
    assert data_undo["status"] == "success"
    assert target_aid in data_undo["restored"]

    # Verify a new task was created in queue
    all_tasks = qm.list_all_tasks()
    assert len(all_tasks) == 1
    new_task = all_tasks[0]
    assert new_task.request == entries[0]["request"]
    assert new_task.priority == entries[0]["priority"]
    assert new_task.status == TaskStatus.PENDING


def test_undo_marks_restored(undo_env):
    qm, tmp_path = undo_env

    res_list = client.get("/api/queue/archive", headers=OPERATOR_HEADERS)
    entries = res_list.json()["entries"]
    target_aid = entries[0]["archive_id"]

    # Undo target entry
    client.post(
        "/api/queue/archive/undo",
        json={"archive_ids": [target_aid], "confirm": "UNDO"},
        headers=OPERATOR_HEADERS
    )

    # Check updated archive list
    res_list_after = client.get("/api/queue/archive", headers=OPERATOR_HEADERS)
    entries_after = res_list_after.json()["entries"]
    restored_entry = next(e for e in entries_after if e["archive_id"] == target_aid)
    assert restored_entry["restored"] is True


def test_undo_preserves_why(undo_env):
    qm, tmp_path = undo_env

    res_list = client.get("/api/queue/archive", headers=OPERATOR_HEADERS)
    entries = res_list.json()["entries"]
    entry0 = entries[0]
    target_aid = entry0["archive_id"]

    client.post(
        "/api/queue/archive/undo",
        json={"archive_ids": [target_aid], "confirm": "UNDO"},
        headers=OPERATOR_HEADERS
    )

    all_tasks = qm.list_all_tasks()
    assert len(all_tasks) == 1
    task = all_tasks[0]

    # Verify why block preserved
    meta_why = task.metadata.get("why", {})
    assert meta_why.get("source_task") == entry0["why"].get("source_task")
    assert meta_why.get("proposed_by") == entry0["why"].get("proposed_by")

    # Verify history transition appended
    transitions = meta_why.get("history_transitions", [])
    assert len(transitions) > 0
    last_transition = transitions[-1]
    assert last_transition["status"] == "PENDING"
    assert f"RESTORED from {target_aid}" in last_transition["message"]


def test_undo_skips_already_restored(undo_env):
    qm, tmp_path = undo_env

    res_list = client.get("/api/queue/archive", headers=OPERATOR_HEADERS)
    entries = res_list.json()["entries"]
    target_aid = entries[0]["archive_id"]

    # First undo
    client.post(
        "/api/queue/archive/undo",
        json={"archive_ids": [target_aid], "confirm": "UNDO"},
        headers=OPERATOR_HEADERS
    )
    assert len(qm.list_all_tasks()) == 1

    # Second undo on same archive_id
    res_second = client.post(
        "/api/queue/archive/undo",
        json={"archive_ids": [target_aid], "confirm": "UNDO"},
        headers=OPERATOR_HEADERS
    )
    assert res_second.status_code == 200
    data_second = res_second.json()
    assert target_aid not in data_second["restored"]

    # Task count should remain 1
    assert len(qm.list_all_tasks()) == 1


def test_undo_filter_by_status(undo_env):
    qm, tmp_path = undo_env

    res = client.post(
        "/api/queue/archive/undo-filter",
        json={"status": "ready", "confirm": "UNDO"},
        headers=OPERATOR_HEADERS
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["matched"] == 1
    assert len(data["restored"]) == 1


def test_undo_filter_by_date(undo_env):
    qm, tmp_path = undo_env

    # Filter with date from far past
    res = client.post(
        "/api/queue/archive/undo-filter",
        json={"date_from": "2020-01-01T00:00:00", "confirm": "UNDO"},
        headers=OPERATOR_HEADERS
    )
    assert res.status_code == 200
    data = res.json()
    assert data["matched"] == 3


def test_undo_filter_by_search(undo_env):
    qm, tmp_path = undo_env

    res = client.post(
        "/api/queue/archive/undo-filter",
        json={"search": "search test", "confirm": "UNDO"},
        headers=OPERATOR_HEADERS
    )
    assert res.status_code == 200
    data = res.json()
    assert data["matched"] == 1
    assert len(data["restored"]) == 1


def test_undo_filter_returns_matched_count(undo_env):
    qm, tmp_path = undo_env

    # Dry run should return matched count and entries without creating tasks
    res = client.post(
        "/api/queue/archive/undo-filter",
        json={"dry_run": True},
        headers=OPERATOR_HEADERS
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["matched"] == 3
    assert len(data["entries"]) == 3
    # No tasks created in queue
    assert len(qm.list_all_tasks()) == 0


def test_undo_requires_confirm(undo_env):
    qm, tmp_path = undo_env

    res = client.post(
        "/api/queue/archive/undo",
        json={"archive_ids": ["reset-1.jsonl:1"], "confirm": "WRONG"},
        headers=OPERATOR_HEADERS
    )
    assert res.status_code == 400
    data = res.json()
    assert data["code"] == "INVALID_CONFIRMATION"

    res_filter = client.post(
        "/api/queue/archive/undo-filter",
        json={"confirm": "WRONG", "dry_run": False},
        headers=OPERATOR_HEADERS
    )
    assert res_filter.status_code == 400
    data_f = res_filter.json()
    assert data_f["code"] == "INVALID_CONFIRMATION"


def test_undo_requires_operator(undo_env):
    qm, tmp_path = undo_env

    res_list = client.get("/api/queue/archive", headers=CONSULTANT_HEADERS)
    assert res_list.status_code == 403

    res_undo = client.post(
        "/api/queue/archive/undo",
        json={"archive_ids": ["reset-1.jsonl:1"], "confirm": "UNDO"},
        headers=CONSULTANT_HEADERS
    )
    assert res_undo.status_code == 403

    res_filter = client.post(
        "/api/queue/archive/undo-filter",
        json={"confirm": "UNDO"},
        headers=CONSULTANT_HEADERS
    )
    assert res_filter.status_code == 403
