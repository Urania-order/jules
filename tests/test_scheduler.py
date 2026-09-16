"""Tests for Co-SMOS v0.9 Background Scheduler."""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from smos.api.main import app
from smos.core.batch import BatchManager
from smos.core.queue import QueueManager
from smos.core.task import Task, TaskStatus
from smos.core.scheduler import Scheduler

client = TestClient(app)
client.headers.update({"Authorization": "Bearer dev-operator-token"})

@pytest.fixture
def setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    bm = BatchManager(batch_dir=tmp_path / ".jules" / "batches")
    qm = QueueManager(queue_dir=tmp_path / ".jules" / "queue")
    scheduler = Scheduler(batch_manager=bm)
    
    tasks = []
    for i in range(1, 6):
        t = Task(
            id=f"task-sched-{i}",
            request=f"Sched Task {i}",
            status=TaskStatus.READY,
            priority=3
        )
        qm.save_task(t)
        tasks.append(t)
        
    return qm, bm, scheduler, tasks

def test_scheduler_registers_default_schedules(setup_env):
    _, _, scheduler, _ = setup_env
    schedules = scheduler.get_schedules()
    assert "night" in schedules
    assert "window" in schedules
    assert schedules["night"]["start"] == "02:00"
    assert schedules["night"]["end"] == "06:00"
    assert schedules["window"]["start"] == "09:00"
    assert schedules["window"]["end"] == "18:00"

def test_scheduler_is_due_night_in_window(setup_env):
    _, _, scheduler, _ = setup_env
    # 03:00 UTC Monday
    dt = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)
    assert scheduler.is_due("night", now=dt) is True

def test_scheduler_is_due_night_outside_window(setup_env):
    _, _, scheduler, _ = setup_env
    # 12:00 UTC Monday
    dt = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    assert scheduler.is_due("night", now=dt) is False

def test_scheduler_is_due_window_in_window(setup_env):
    _, _, scheduler, _ = setup_env
    # 10:00 UTC Monday (workday)
    dt = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
    assert scheduler.is_due("window", now=dt) is True

def test_scheduler_is_due_window_outside_window(setup_env):
    _, _, scheduler, _ = setup_env
    # 10:00 UTC Saturday (weekend)
    dt_sat = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
    assert scheduler.is_due("window", now=dt_sat) is False
    
    # 20:00 UTC Monday (after hours)
    dt_late = datetime(2026, 9, 14, 20, 0, tzinfo=timezone.utc)
    assert scheduler.is_due("window", now=dt_late) is False

def test_scheduler_runs_due_batches(setup_env):
    qm, bm, scheduler, tasks = setup_env
    task_ids = [t.id for t in tasks[:2]]
    
    batch = bm.create_batch(
        task_ids=task_ids,
        schedule="night",
        concurrency=2,
        status="queued",
        started=[],
        queued=task_ids,
        autonomy="AUTO"
    )
    
    dt = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)
    started_ids = scheduler.check_due_batches(now=dt)
    
    assert started_ids == [batch.id]
    updated_batch = bm.get_batch(batch.id)
    assert updated_batch.status == "completed"
    assert updated_batch.started == task_ids
    assert updated_batch.queued == []

def test_scheduler_does_not_run_early_batches(setup_env):
    qm, bm, scheduler, tasks = setup_env
    task_ids = [t.id for t in tasks[:2]]
    
    batch = bm.create_batch(
        task_ids=task_ids,
        schedule="night",
        concurrency=2,
        status="queued",
        started=[],
        queued=task_ids,
        autonomy="AUTO"
    )
    
    # 12:00 UTC Monday - outside night window
    dt = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    started_ids = scheduler.check_due_batches(now=dt)
    
    assert started_ids == []
    updated_batch = bm.get_batch(batch.id)
    assert updated_batch.status == "queued"

def test_scheduler_respects_concurrency(setup_env):
    qm, bm, scheduler, tasks = setup_env
    task_ids = [t.id for t in tasks[:4]]  # 4 tasks
    
    batch = bm.create_batch(
        task_ids=task_ids,
        schedule="night",
        concurrency=2,
        status="queued",
        started=[],
        queued=task_ids,
        autonomy="AUTO"
    )
    
    dt = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)
    started_ids = scheduler.check_due_batches(now=dt)
    
    assert started_ids == [batch.id]
    updated_batch = bm.get_batch(batch.id)
    assert len(updated_batch.started) == 2
    assert updated_batch.started == task_ids[:2]
    assert len(updated_batch.queued) == 2
    assert updated_batch.queued == task_ids[2:]

def test_scheduler_updates_batch_status(setup_env):
    qm, bm, scheduler, tasks = setup_env
    task_ids = [t.id for t in tasks[:2]]
    
    batch = bm.create_batch(
        task_ids=task_ids,
        schedule="night",
        concurrency=2,
        status="queued",
        started=[],
        queued=task_ids,
        autonomy="AUTO"
    )
    
    dt = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)
    started_ids = scheduler.check_due_batches(now=dt)
    
    assert batch.id in started_ids
    updated_batch = bm.get_batch(batch.id)
    assert updated_batch.status == "completed"
    
    for tid in task_ids:
        t = qm.get_task(tid)
        assert t.status == TaskStatus.RUNNING

def test_scheduler_does_not_touch_now_batches(setup_env):
    qm, bm, scheduler, tasks = setup_env
    task_ids = [t.id for t in tasks[:2]]
    
    batch_now = bm.create_batch(
        task_ids=task_ids,
        schedule="now",
        concurrency=2,
        status="queued",
        started=[],
        queued=task_ids,
        autonomy="AUTO"
    )
    
    dt = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)
    started_ids = scheduler.check_due_batches(now=dt)
    
    assert batch_now.id not in started_ids
    updated_batch = bm.get_batch(batch_now.id)
    assert updated_batch.status == "queued"
    assert updated_batch.started == []

def test_batch_run_window_now_works(setup_env):
    resp = client.post("/api/batch/run", json={
        "task_ids": ["task-sched-1", "task-sched-2"],
        "schedule": "window",
        "concurrency": 2,
        "autonomy": "AUTO"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["schedule"] == "window"
    assert len(data["queued"]) == 2

def test_scheduler_endpoint_status(setup_env):
    resp = client.get("/api/scheduler/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert "schedules" in data
    assert "night" in data["schedules"]

def test_scheduler_endpoint_register(setup_env):
    resp = client.post("/api/scheduler/schedules", json={
        "name": "custom",
        "config": {
            "start": "12:00",
            "end": "14:00",
            "days": ["mon", "tue"]
        }
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["schedule"] == "custom"
    
    # Verify in schedules list
    schedules_resp = client.get("/api/scheduler/schedules")
    assert schedules_resp.status_code == 200
    schedules = schedules_resp.json()
    assert "custom" in schedules
    assert schedules["custom"]["start"] == "12:00"

def test_scheduler_trigger_for_testing(setup_env):
    qm, bm, scheduler, tasks = setup_env
    task_ids = [t.id for t in tasks[:2]]
    
    # Create a batch scheduled for window (assume currently outside window, but trigger forces due check)
    batch = bm.create_batch(
        task_ids=task_ids,
        schedule="night",
        concurrency=2,
        status="queued",
        started=[],
        queued=task_ids,
        autonomy="AUTO"
    )
    
    resp = client.post("/api/scheduler/trigger")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert isinstance(data["started_batches"], list)
