"""Tests for Co-SMOS v0.9 Backend Batch API Endpoints."""

import pytest
from fastapi.testclient import TestClient
from smos.api.main import app
from smos.core.queue import QueueManager
from smos.core.task import Task, TaskStatus

client = TestClient(app)
client.headers.update({"Authorization": "Bearer dev-operator-token"})

@pytest.fixture
def setup_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    qm = QueueManager(queue_dir=tmp_path / ".jules" / "queue")
    
    tasks = []
    for i in range(1, 6):
        t = Task(
            id=f"task-test-{i}",
            request=f"Test Task {i}",
            status=TaskStatus.READY,
            priority=5
        )
        qm.save_task(t)
        tasks.append(t)
        
    return qm, tasks

def test_batch_run_now(setup_tasks):
    qm, tasks = setup_tasks
    task_ids = [t.id for t in tasks[:3]]
    
    resp = client.post("/api/batch/run", json={
        "task_ids": task_ids,
        "schedule": "now",
        "concurrency": 3,
        "autonomy": "AUTO"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["concurrency"] == 3
    assert data["schedule"] == "now"
    assert len(data["started"]) == 3
    assert len(data["queued"]) == 0
    assert set(data["started"]) == set(task_ids)

def test_batch_run_now_sequential(setup_tasks):
    qm, tasks = setup_tasks
    task_ids = [t.id for t in tasks[:3]]
    
    resp = client.post("/api/batch/run", json={
        "task_ids": task_ids,
        "schedule": "now-sequential",
        "concurrency": 3,
        "autonomy": "AUTO"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["schedule"] == "now-sequential"
    assert len(data["started"]) == 1
    assert data["started"][0] == task_ids[0]
    assert len(data["queued"]) == 2
    assert data["queued"] == task_ids[1:]

def test_batch_run_night(setup_tasks):
    qm, tasks = setup_tasks
    task_ids = [t.id for t in tasks[:3]]
    
    resp = client.post("/api/batch/run", json={
        "task_ids": task_ids,
        "schedule": "night",
        "concurrency": 3,
        "autonomy": "AUTO"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["schedule"] == "night"
    assert len(data["started"]) == 0
    assert len(data["queued"]) == 3
    assert data["queued"] == task_ids

def test_batch_run_window_with_scheduler(setup_tasks):
    qm, tasks = setup_tasks
    task_ids = [t.id for t in tasks[:2]]
    
    resp = client.post("/api/batch/run", json={
        "task_ids": task_ids,
        "schedule": "window",
        "concurrency": 2,
        "autonomy": "AUTO"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["schedule"] == "window"
    assert len(data["queued"]) == 2

def test_batch_run_manual_requires_confirm(setup_tasks):
    qm, tasks = setup_tasks
    task_ids = [t.id for t in tasks[:2]]
    
    # Without confirm=True -> Fail
    resp = client.post("/api/batch/run", json={
        "task_ids": task_ids,
        "schedule": "now",
        "concurrency": 2,
        "autonomy": "MANUAL",
        "confirm": False
    })
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "error"
    assert data["code"] == "CONFIRMATION_REQUIRED"
    
    # With confirm=True -> Pass
    resp_ok = client.post("/api/batch/run", json={
        "task_ids": task_ids,
        "schedule": "now",
        "concurrency": 2,
        "autonomy": "MANUAL",
        "confirm": True
    })
    assert resp_ok.status_code == 200
    assert resp_ok.json()["status"] == "accepted"

def test_batch_concurrency_limit(setup_tasks):
    qm, tasks = setup_tasks
    task_ids = [t.id for t in tasks]  # 5 tasks
    
    resp = client.post("/api/batch/run", json={
        "task_ids": task_ids,
        "schedule": "now",
        "concurrency": 2,
        "autonomy": "AUTO"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["concurrency"] == 2
    assert len(data["started"]) == 2
    assert len(data["queued"]) == 3
    assert data["started"] == task_ids[:2]
    assert data["queued"] == task_ids[2:]

def test_batch_get_status(setup_tasks):
    qm, tasks = setup_tasks
    task_ids = [t.id for t in tasks[:2]]
    
    run_resp = client.post("/api/batch/run", json={
        "task_ids": task_ids,
        "schedule": "now",
        "concurrency": 2,
        "autonomy": "AUTO"
    })
    batch_id = run_resp.json()["batch_id"]
    
    get_resp = client.get(f"/api/batch/{batch_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == batch_id
    assert data["task_ids"] == task_ids
    assert data["status"] == "accepted"
    
    # Check 404 for non-existent batch
    get_404 = client.get("/api/batch/batch-non-existent")
    assert get_404.status_code == 404
    assert get_404.json()["code"] == "BATCH_NOT_FOUND"

def test_batch_list(setup_tasks):
    qm, tasks = setup_tasks
    
    # Create a couple of batches
    run1 = client.post("/api/batch/run", json={
        "task_ids": [tasks[0].id],
        "schedule": "now",
        "concurrency": 1,
        "autonomy": "AUTO"
    })
    run2 = client.post("/api/batch/run", json={
        "task_ids": [tasks[1].id],
        "schedule": "night",
        "concurrency": 1,
        "autonomy": "AUTO"
    })
    
    # List all
    list_resp = client.get("/api/batch")
    assert list_resp.status_code == 200
    batches = list_resp.json()
    assert len(batches) >= 2
    
    # List queued
    queue_resp = client.get("/api/batch/queue")
    assert queue_resp.status_code == 200
    queued_batches = queue_resp.json()
    assert len(queued_batches) == 1
    assert queued_batches[0]["id"] == run2.json()["batch_id"]
    assert queued_batches[0]["status"] == "queued"
