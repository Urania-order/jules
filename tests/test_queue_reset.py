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


def test_queue_reset_archives_to_jsonl(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-jsonl-1", request="Archive test task", status=TaskStatus.READY, priority=4)
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "ready"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["moved"] == 1

    queue_dir = tmp_path / ".jules" / "queue"
    jsonl_files = list(queue_dir.glob("reset-*.jsonl"))
    assert len(jsonl_files) == 1

    lines = [json.loads(line) for line in jsonl_files[0].read_text().strip().split("\n") if line]
    assert len(lines) == 1
    assert lines[0]["task_id"] == "task-jsonl-1"
    assert lines[0]["status"] in ("ready", "pending")
    assert lines[0]["request"] == "Archive test task"
    assert lines[0]["priority"] == 4
    assert "reset_at" in lines[0]
    assert lines[0]["restored"] is False


def test_queue_reset_writes_history_md(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-md-1", request="History md task", status=TaskStatus.RUNNING)
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "running"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    history_dir = tmp_path / ".jules" / "history"
    md_files = list(history_dir.glob("reset-*.md"))
    assert len(md_files) == 1

    content = md_files[0].read_text()
    assert "# Queue Reset Report" in content
    assert "running" in content
    assert "task-md-1" in content


def test_queue_reset_preserves_why_block(queue_env):
    qm, tmp_path = queue_env
    task = Task(
        id="task-why-1",
        request="Task with why",
        status=TaskStatus.PENDING,
        source_task="src-task-99",
        proposed_by="operator"
    )
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "pending"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    queue_dir = tmp_path / ".jules" / "queue"
    jsonl_files = list(queue_dir.glob("reset-*.jsonl"))
    assert len(jsonl_files) == 1

    lines = [json.loads(line) for line in jsonl_files[0].read_text().strip().split("\n") if line]
    why = lines[0]["why"]
    assert why["source_task"] == "src-task-99"
    assert why["proposed_by"] == "operator"
    assert isinstance(why["history_transitions"], list)


def test_queue_reset_why_uses_existing_data_not_fabricated(queue_env):
    qm, tmp_path = queue_env
    # Task without source_task or proposed_by
    task = Task(id="task-no-why", request="Task without why", status=TaskStatus.PENDING)
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "pending"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    queue_dir = tmp_path / ".jules" / "queue"
    jsonl_files = list(queue_dir.glob("reset-*.jsonl"))
    assert len(jsonl_files) == 1

    lines = [json.loads(line) for line in jsonl_files[0].read_text().strip().split("\n") if line]
    why = lines[0]["why"]
    assert why["source_task"] is None
    assert why["proposal_origin"] is None
    assert why["proposed_by"] is None


def test_queue_reset_column_ready(queue_env):
    qm, tmp_path = queue_env
    task_p = Task(id="task-col-ready", request="Ready col task", status=TaskStatus.READY)
    task_r = Task(id="task-col-running-keep", request="Running keep", status=TaskStatus.RUNNING)
    qm.save_task(task_p)
    qm.save_task(task_r)

    res = client.post("/api/queue/reset-column", json={"confirm": "RESET", "column": "ready"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["moved"] == 1

    assert qm.get_task("task-col-ready").status == TaskStatus.DEFERRED
    assert qm.get_task("task-col-running-keep").status == TaskStatus.RUNNING


def test_queue_reset_column_running(queue_env):
    qm, tmp_path = queue_env
    task_r = Task(id="task-col-run", request="Running col task", status=TaskStatus.RUNNING)
    qm.save_task(task_r)

    res = client.post("/api/queue/reset-column", json={"confirm": "RESET", "column": "running"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["moved"] == 1

    assert qm.get_task("task-col-run").status == TaskStatus.DEFERRED


def test_queue_reset_column_completed(queue_env):
    qm, tmp_path = queue_env
    task_c = Task(id="task-col-comp", request="Completed col task", status=TaskStatus.COMPLETED)
    qm.save_task(task_c)

    res = client.post("/api/queue/reset-column", json={"confirm": "RESET", "column": "completed"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["moved"] == 1

    assert qm.get_task("task-col-comp").status == TaskStatus.DEFERRED


def test_queue_reset_all(queue_env):
    qm, tmp_path = queue_env
    task_p = Task(id="task-all-1", request="Pending all", status=TaskStatus.PENDING)
    task_r = Task(id="task-all-2", request="Running all", status=TaskStatus.RUNNING)
    task_c = Task(id="task-all-3", request="Completed all", status=TaskStatus.COMPLETED)
    qm.save_task(task_p)
    qm.save_task(task_r)
    qm.save_task(task_c)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["moved"] == 3
