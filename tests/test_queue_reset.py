import pytest
import os
import json
from pathlib import Path
from fastapi.testclient import TestClient
from smos.api.main import app
from smos.core.queue import QueueManager
from smos.core.task import Task, TaskStatus

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer dev-operator-token"}


@pytest.fixture
def queue_env(tmp_path, monkeypatch):
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    qm = QueueManager(queue_dir=tmp_path / ".jules" / "queue")
    return qm, tmp_path


def test_queue_reset(queue_env):
    qm, tmp_path = queue_env

    # Create pending, running, completed tasks
    task_p = Task(id="task-p1", request="Pending task", status=TaskStatus.PENDING)
    task_r = Task(id="task-r1", request="Running task", status=TaskStatus.RUNNING)
    task_c = Task(id="task-c1", request="Completed task", status=TaskStatus.COMPLETED)

    qm.save_task(task_p)
    qm.save_task(task_r)
    qm.save_task(task_c)

    # Call reset for scope="pending"
    res1 = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "pending"}, headers=AUTH_HEADERS)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "success"
    assert data1["moved"] == 1
    assert data1["cleared"]["pending"] == 1

    # Pending task should be moved to deferred
    assert qm.get_task("task-p1") is None or qm.get_task("task-p1").status == TaskStatus.DEFERRED
    deferred_dir = tmp_path / ".jules" / "queue" / "deferred"
    assert (deferred_dir / "task-p1.json").exists()

    # Call reset for scope="all"
    res2 = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "success"
    assert data2["moved"] == 2
    assert data2["cleared"]["running"] == 1
    assert data2["cleared"]["completed"] == 1

    assert (deferred_dir / "task-r1.json").exists()
    assert (deferred_dir / "task-c1.json").exists()


def test_queue_reset_requires_confirm(queue_env):
    qm, tmp_path = queue_env
    task_p = Task(id="task-p2", request="Pending task", status=TaskStatus.PENDING)
    qm.save_task(task_p)

    # Missing or incorrect confirm string
    res = client.post("/api/queue/reset", json={"confirm": "NO", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 400
    data = res.json()
    assert data["status"] == "error"
    assert data["code"] == "INVALID_CONFIRMATION"

    # Pending task still in pending
    pending_file = tmp_path / ".jules" / "queue" / "pending" / "task-p2.json"
    assert pending_file.exists()
