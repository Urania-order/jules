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
def test_env(tmp_path, monkeypatch):
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    qm = QueueManager(queue_dir=tmp_path / ".jules" / "queue")
    return qm, tmp_path


def test_task_patch_extended(test_env):
    qm, tmp_path = test_env
    task = Task(id="task-ext1", request="Initial request", priority=3)
    qm.save_task(task)

    patch_payload = {
        "status": "RUNNING",
        "notes": "Added notes for execution",
        "tags": ["backend", "v1.1"],
        "priority": 1,
        "request": "Updated request"
    }
    res = client.patch("/api/tasks/task-ext1", json=patch_payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("running", "RUNNING")
    assert data["notes"] == "Added notes for execution"
    assert data["tags"] == ["backend", "v1.1"]
    assert data["priority"] == 1
    assert data["request"] == "Updated request"

    # Verify persistent task state
    updated_task = qm.get_task("task-ext1")
    assert updated_task.status == TaskStatus.RUNNING
    assert updated_task.notes == "Added notes for execution"
    assert updated_task.tags == ["backend", "v1.1"]


def test_task_remember_creates_template(test_env):
    qm, tmp_path = test_env
    task = Task(id="task-rem1", request="Task to remember", priority=2, notes="Some note", tags=["tpl-tag"])
    qm.save_task(task)

    res = client.post("/api/tasks/task-rem1/remember", json={"name": "My Template"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "template_id" in data
    tpl_id = data["template_id"]
    assert tpl_id.startswith("tpl-")

    # Check file stored in .jules/templates/tpl-XXXX.json
    tpl_file = tmp_path / ".jules" / "templates" / f"{tpl_id}.json"
    assert tpl_file.exists()
    tpl_data = json.loads(tpl_file.read_text(encoding="utf-8"))
    assert tpl_data["name"] == "My Template"
    assert tpl_data["request"] == "Task to remember"
    assert tpl_data["priority"] == 2
    assert tpl_data["notes"] == "Some note"
    assert tpl_data["tags"] == ["tpl-tag"]


def test_template_list_use_delete(test_env):
    qm, tmp_path = test_env

    # 1. Create a task and remember it
    task = Task(id="task-tpl-base", request="Template base task", priority=4, tags=["base"])
    qm.save_task(task)

    rem_res = client.post("/api/tasks/task-tpl-base/remember", json={"name": "Base Template"}, headers=AUTH_HEADERS)
    assert rem_res.status_code == 200
    tpl_id = rem_res.json()["template_id"]

    # 2. List templates
    list_res = client.get("/api/templates", headers=AUTH_HEADERS)
    assert list_res.status_code == 200
    templates = list_res.json()
    assert len(templates) == 1
    assert templates[0]["id"] == tpl_id
    assert templates[0]["name"] == "Base Template"

    # 3. Use template to create new task
    use_res = client.post(f"/api/templates/{tpl_id}/use", headers=AUTH_HEADERS)
    assert use_res.status_code == 200
    new_task = use_res.json()
    assert new_task["id"] != "task-tpl-base"
    assert new_task["request"] == "Template base task"
    assert new_task["priority"] == 4
    assert new_task["tags"] == ["base"]

    # Verify task exists in queue manager
    created_task = qm.get_task(new_task["id"])
    assert created_task is not None
    assert created_task.request == "Template base task"

    # 4. Delete template
    del_res = client.delete(f"/api/templates/{tpl_id}", headers=AUTH_HEADERS)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # 5. List templates after delete
    list_res2 = client.get("/api/templates", headers=AUTH_HEADERS)
    assert list_res2.status_code == 200
    assert len(list_res2.json()) == 0
