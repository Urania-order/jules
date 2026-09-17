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

    # Pending task should be removed from state.json
    assert qm.get_task("task-p1") is None

    # Call reset for scope="all"
    res2 = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "success"
    assert data2["moved"] == 2
    assert data2["cleared"]["running"] == 1
    assert data2["cleared"]["completed"] == 1

    assert qm.get_task("task-r1") is None
    assert qm.get_task("task-c1") is None


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

    # Pending task still in queue
    assert qm.get_task("task-p2") is not None


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

    assert qm.get_task("task-col-ready") is None
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

    assert qm.get_task("task-col-run") is None


def test_queue_reset_column_completed(queue_env):
    qm, tmp_path = queue_env
    task_c = Task(id="task-col-comp", request="Completed col task", status=TaskStatus.COMPLETED)
    qm.save_task(task_c)

    res = client.post("/api/queue/reset-column", json={"confirm": "RESET", "column": "completed"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["moved"] == 1

    assert qm.get_task("task-col-comp") is None


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


def test_reset_all_removes_from_state_json(queue_env):
    qm, tmp_path = queue_env
    task_p = Task(id="task-s1", request="Pending task 1", status=TaskStatus.PENDING)
    task_r = Task(id="task-s2", request="Running task 2", status=TaskStatus.RUNNING)
    qm.save_task(task_p)
    qm.save_task(task_r)

    state_file = tmp_path / ".co-smos" / "state.json"
    assert state_file.exists()

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["moved"] == 2

    state_data = json.loads(state_file.read_text())
    assert state_data.get("active_task") is None
    assert len(state_data.get("history", [])) == 0


def test_reset_completed_removes_deferred_and_cancelled(queue_env):
    qm, tmp_path = queue_env
    t_comp = Task(id="task-comp", request="Completed task", status=TaskStatus.COMPLETED)
    t_fail = Task(id="task-fail", request="Failed task", status=TaskStatus.FAILED)
    t_canc = Task(id="task-canc", request="Cancelled task", status=TaskStatus.CANCELLED)
    t_def = Task(id="task-def", request="Deferred task", status=TaskStatus.DEFERRED)
    t_pend = Task(id="task-pend", request="Pending task", status=TaskStatus.PENDING)

    qm.save_task(t_comp)
    qm.save_task(t_fail)
    qm.save_task(t_canc)
    qm.save_task(t_def)
    qm.save_task(t_pend)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "completed"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["moved"] == 4

    assert qm.get_task("task-comp") is None
    assert qm.get_task("task-fail") is None
    assert qm.get_task("task-canc") is None
    assert qm.get_task("task-def") is None
    assert qm.get_task("task-pend") is not None


def test_reset_archives_to_jsonl(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-arch-1", request="Archiving test", status=TaskStatus.PENDING, priority=3)
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "pending"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    queue_dir = tmp_path / ".jules" / "queue"
    jsonl_files = list(queue_dir.glob("reset-*.jsonl"))
    assert len(jsonl_files) == 1

    lines = [json.loads(line) for line in jsonl_files[0].read_text().strip().split("\n") if line]
    assert len(lines) == 1
    assert lines[0]["task_id"] == "task-arch-1"
    assert lines[0]["status"] == "pending"
    assert lines[0]["request"] == "Archiving test"
    assert lines[0]["priority"] == 3
    assert lines[0]["restored"] is False


def test_reset_preserves_why_from_state(queue_env):
    qm, tmp_path = queue_env
    task = Task(
        id="task-why-state",
        request="State why task",
        status=TaskStatus.RUNNING,
        source_task="src-task-100",
        proposed_by="admin",
        metadata={"proposal_origin": "origin-abc"}
    )
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "running"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    queue_dir = tmp_path / ".jules" / "queue"
    jsonl_files = list(queue_dir.glob("reset-*.jsonl"))
    assert len(jsonl_files) == 1

    lines = [json.loads(line) for line in jsonl_files[0].read_text().strip().split("\n") if line]
    why = lines[0]["why"]
    assert why["source_task"] == "src-task-100"
    assert why["proposed_by"] == "admin"
    assert why["proposal_origin"] == "origin-abc"


def test_reset_updates_state_json(queue_env):
    qm, tmp_path = queue_env
    task_r = Task(id="task-running-st", request="Running in state", status=TaskStatus.RUNNING)
    qm.save_task(task_r)

    state_file = tmp_path / ".co-smos" / "state.json"
    state_before = json.loads(state_file.read_text())
    assert state_before.get("active_task") is not None

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "running"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    state_after = json.loads(state_file.read_text())
    assert state_after.get("active_task") is None
    assert state_after.get("status") in ("idle", "online")


def test_reset_no_files_in_queue_dir(queue_env):
    qm, tmp_path = queue_env
    task_p = Task(id="task-nf-1", request="No files pending", status=TaskStatus.PENDING)
    task_r = Task(id="task-nf-2", request="No files running", status=TaskStatus.RUNNING)
    qm.save_task(task_p)
    qm.save_task(task_r)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    queue_dir = tmp_path / ".jules" / "queue"
    for folder_name in ["pending", "running", "completed", "deferred"]:
        folder = queue_dir / folder_name
        json_files = list(folder.glob("*.json"))
        assert len(json_files) == 0, f"Found unexpected task json files in {folder_name}: {json_files}"
