import os
import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from smos.api.main import app

PROJECT_ROOT = Path(__file__).parent.parent
OPERATOR_HEADERS = {"Authorization": "Bearer dev-operator-token"}


@pytest.fixture(autouse=True)
def isolate_project_root(tmp_path, monkeypatch):
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    (tmp_path / ".jules" / "queue" / "pending").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".jules" / "queue" / "running").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".jules" / "queue" / "completed").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".jules" / "sequences").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".jules" / "batch_templates").mkdir(parents=True, exist_ok=True)
    
    # Copy scripts directory so JulesCLIAdapter can find scripts
    if (PROJECT_ROOT / "scripts").exists():
        shutil.copytree(PROJECT_ROOT / "scripts", tmp_path / "scripts")


def test_sequence_record_start_stop(tmp_path):
    client = TestClient(app)

    # Start recording
    res = client.post("/api/sequences/record/start", headers=OPERATOR_HEADERS)
    assert res.status_code == 200
    assert res.json().get("status") == "recording_started"

    # Add tasks while recording
    task1_res = client.post("/api/queue", json={"request": "Task A for Sequence", "priority": 3}, headers=OPERATOR_HEADERS)
    assert task1_res.status_code == 200

    task2_res = client.post("/api/queue", json={"request": "Task B for Sequence", "priority": 4}, headers=OPERATOR_HEADERS)
    assert task2_res.status_code == 200

    # Stop recording
    stop_res = client.post("/api/sequences/record/stop", json={"name": "Test Workflow Sequence"}, headers=OPERATOR_HEADERS)
    assert stop_res.status_code == 200
    data = stop_res.json()
    assert "sequence_id" in data
    assert len(data.get("tasks", [])) == 2

    # Verify saved file exists
    seq_id = data["sequence_id"]
    seq_file = tmp_path / ".jules" / "sequences" / f"{seq_id}.json"
    assert seq_file.exists()


def test_sequence_replay_sequential(tmp_path):
    client = TestClient(app)

    # Start and stop to record a sequence
    client.post("/api/sequences/record/start", headers=OPERATOR_HEADERS)
    client.post("/api/queue", json={"request": "Seq Task 1", "priority": 2}, headers=OPERATOR_HEADERS)
    client.post("/api/queue", json={"request": "Seq Task 2", "priority": 3}, headers=OPERATOR_HEADERS)
    stop_res = client.post("/api/sequences/record/stop", json={"name": "Seq Test"}, headers=OPERATOR_HEADERS)
    seq_id = stop_res.json()["sequence_id"]

    # Replay sequential
    replay_res = client.post(f"/api/sequences/{seq_id}/replay", json={
        "mode": "sequential",
        "schedule": "now",
        "concurrency": 1
    }, headers=OPERATOR_HEADERS)

    assert replay_res.status_code == 200
    data = replay_res.json()
    assert len(data.get("created_tasks", [])) == 2
    assert data.get("batch_id") is not None


def test_sequence_replay_parallel(tmp_path):
    client = TestClient(app)

    client.post("/api/sequences/record/start", headers=OPERATOR_HEADERS)
    client.post("/api/queue", json={"request": "Par Task 1", "priority": 5}, headers=OPERATOR_HEADERS)
    client.post("/api/queue", json={"request": "Par Task 2", "priority": 5}, headers=OPERATOR_HEADERS)
    client.post("/api/queue", json={"request": "Par Task 3", "priority": 5}, headers=OPERATOR_HEADERS)
    stop_res = client.post("/api/sequences/record/stop", json={"name": "Par Seq Test"}, headers=OPERATOR_HEADERS)
    seq_id = stop_res.json()["sequence_id"]

    # Replay parallel
    replay_res = client.post(f"/api/sequences/{seq_id}/replay", json={
        "mode": "parallel",
        "schedule": "now",
        "concurrency": 3
    }, headers=OPERATOR_HEADERS)

    assert replay_res.status_code == 200
    data = replay_res.json()
    assert len(data.get("created_tasks", [])) == 3
    assert data.get("batch_id") is not None


def test_batch_template_remember(tmp_path):
    client = TestClient(app)

    # Create tasks first
    t1 = client.post("/api/queue", json={"request": "Batch Item 1", "priority": 3}, headers=OPERATOR_HEADERS).json()
    t2 = client.post("/api/queue", json={"request": "Batch Item 2", "priority": 4}, headers=OPERATOR_HEADERS).json()

    task1_id = t1["task"]["id"]
    task2_id = t2["task"]["id"]

    # Remember as batch template
    rem_res = client.post("/api/batch/remember", json={
        "name": "My Batch Template",
        "task_ids": [task1_id, task2_id],
        "concurrency": 2,
        "schedule": "now"
    }, headers=OPERATOR_HEADERS)

    assert rem_res.status_code == 200
    data = rem_res.json()
    assert data["name"] == "My Batch Template"
    assert data["id"].startswith("btpl-")

    # Verify listing
    list_res = client.get("/api/batch/templates", headers=OPERATOR_HEADERS)
    assert list_res.status_code == 200
    templates = list_res.json()
    assert any(t["id"] == data["id"] for t in templates)


def test_batch_template_replay(tmp_path):
    client = TestClient(app)

    t1 = client.post("/api/queue", json={"request": "Replay Batch Item 1", "priority": 3}, headers=OPERATOR_HEADERS).json()
    t2 = client.post("/api/queue", json={"request": "Replay Batch Item 2", "priority": 3}, headers=OPERATOR_HEADERS).json()

    task1_id = t1["task"]["id"]
    task2_id = t2["task"]["id"]

    rem_res = client.post("/api/batch/remember", json={
        "name": "Replay Template",
        "task_ids": [task1_id, task2_id],
        "concurrency": 2,
        "schedule": "now"
    }, headers=OPERATOR_HEADERS)
    template_id = rem_res.json()["id"]

    # Replay batch template
    replay_res = client.post(f"/api/batch/templates/{template_id}/replay", headers=OPERATOR_HEADERS)
    assert replay_res.status_code == 200
    data = replay_res.json()
    assert len(data.get("created_tasks", [])) == 2
    assert data.get("batch_id") is not None
