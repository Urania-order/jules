import pytest
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from smos.api.main import app

@pytest.fixture
def client():
    c = TestClient(app)
    c.headers.update({"Authorization": "Bearer dev-operator-token"})
    return c

@pytest.fixture
def queue_dirs(tmp_path, monkeypatch):
    """Fixture providing isolated project root and queue scripts directory."""
    jules_queue = tmp_path / ".jules" / "queue"
    pending = jules_queue / "pending"
    running = jules_queue / "running"
    completed = jules_queue / "completed"
    proposed = jules_queue / "proposed"
    deferred = jules_queue / "deferred"

    pending.mkdir(parents=True, exist_ok=True)
    running.mkdir(parents=True, exist_ok=True)
    completed.mkdir(parents=True, exist_ok=True)
    proposed.mkdir(parents=True, exist_ok=True)
    deferred.mkdir(parents=True, exist_ok=True)

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    project_scripts = Path(__file__).parent.parent / "scripts"
    for s in project_scripts.glob("*.sh"):
        dest = scripts_dir / s.name
        shutil.copy(s, dest)
        dest.chmod(0o755)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))

    return {
        "root": tmp_path,
        "queue": jules_queue,
        "pending": pending,
        "running": running,
        "completed": completed,
        "proposed": proposed,
        "deferred": deferred,
    }

def test_control_room_system_status(client, queue_dirs):
    res = client.get("/api/system/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "tasks_summary" in data
    assert "proposals_summary" in data

def test_control_room_create_and_list_tasks(client, queue_dirs):
    res_add = client.post("/api/queue", json={"request": "API Integration Test Task", "priority": 4})
    assert res_add.status_code == 200
    add_data = res_add.json()
    assert add_data["status"] == "success"

    res_list = client.get("/api/tasks")
    assert res_list.status_code == 200
    tasks = res_list.json()
    assert len(tasks) > 0

    task_id = tasks[0]["id"]
    res_get = client.get(f"/api/tasks/{task_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == task_id

def test_control_room_task_lifecycle(client, queue_dirs):
    res_add = client.post("/api/queue", json={"request": "Lifecycle Task", "priority": 5})
    assert res_add.status_code == 200
    task_id = res_add.json()["task"]["id"]

    res_start = client.post(f"/api/tasks/{task_id}/start")
    assert res_start.status_code == 200
    assert res_start.json()["task"]["status"] == "RUNNING"

    res_cancel = client.post(f"/api/tasks/{task_id}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["task"]["status"] == "CANCELLED"

    res_hist = client.get(f"/api/tasks/{task_id}/history")
    assert res_hist.status_code == 200
    assert len(res_hist.json()["history"]) >= 2

def test_control_room_patch_task(client, queue_dirs):
    res_add = client.post("/api/queue", json={"request": "Task to Patch", "priority": 5})
    assert res_add.status_code == 200
    task_id = res_add.json()["task"]["id"]

    res_patch = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Updated Title", "priority": 9, "status": "RUNNING"}
    )
    assert res_patch.status_code == 200
    data = res_patch.json()
    assert data["title"] == "Updated Title"
    assert data["priority"] == 9
    assert data["status"] == "RUNNING"

    # Test invalid status edge case
    res_bad_status = client.patch(f"/api/tasks/{task_id}", json={"status": "INVALID_STATUS"})
    assert res_bad_status.status_code == 400
    assert res_bad_status.json()["code"] == "INVALID_STATUS"


def test_control_room_task_not_found(client, queue_dirs):
    non_existent_id = "task-99999999-999999-9999"
    
    res_get = client.get(f"/api/tasks/{non_existent_id}")
    assert res_get.status_code == 404
    assert res_get.json()["code"] == "TASK_NOT_FOUND"

    res_patch = client.patch(f"/api/tasks/{non_existent_id}", json={"priority": 1})
    assert res_patch.status_code == 404
    assert res_patch.json()["code"] == "TASK_NOT_FOUND"

    res_start = client.post(f"/api/tasks/{non_existent_id}/start")
    assert res_start.status_code == 404
    assert res_start.json()["code"] == "TASK_NOT_FOUND"

    res_cancel = client.post(f"/api/tasks/{non_existent_id}/cancel")
    assert res_cancel.status_code == 404
    assert res_cancel.json()["code"] == "TASK_NOT_FOUND"

    res_hist = client.get(f"/api/tasks/{non_existent_id}/history")
    assert res_hist.status_code == 404
    assert res_hist.json()["code"] == "TASK_NOT_FOUND"


def test_control_room_queue_operations(client, queue_dirs):
    # Add two tasks
    res1 = client.post("/api/queue", json={"request": "Queue Task 1", "priority": 2})
    assert res1.status_code == 200
    t1 = res1.json()["task"]

    res2 = client.post("/api/queue", json={"request": "Queue Task 2", "priority": 8})
    assert res2.status_code == 200
    t2 = res2.json()["task"]

    # Test reorder queue endpoint
    res_reorder = client.post("/api/queue/reorder", json={"task_ids": [t1["id"], t2["id"]]})
    assert res_reorder.status_code == 200
    reordered_tasks = res_reorder.json()["reordered_tasks"]
    assert len(reordered_tasks) >= 2

    # Test run queue endpoint (dry run)
    res_run = client.post("/api/queue/run", json={"mode": "once", "dry_run": True})
    assert res_run.status_code == 200
    assert res_run.json()["status"] == "success"


def test_control_room_events(client, queue_dirs):
    res_events = client.get("/api/events?limit=10")
    assert res_events.status_code == 200
    events = res_events.json()
    assert isinstance(events, list)


def test_control_room_proposals(client, queue_dirs):
    """Test proposals API endpoints including list, modify, and action handlers."""
    res_props = client.get("/api/proposals")
    assert res_props.status_code == 200
    props = res_props.json()
    assert isinstance(props, list)
    
    if props:
        prop_id = props[0]["id"]

        # Test modify proposal
        res_mod = client.post(
            f"/api/proposals/{prop_id}/modify",
            json={"description": "Modified description for integration test", "priority": 4}
        )
        assert res_mod.status_code in (200, 404)

        # Test proposal defer/accept/reject action handling (accept 200 or failure error response)
        res_defer = client.post(f"/api/proposals/{prop_id}/defer")
        assert res_defer.status_code in (200, 400)

    # Test modify non-existent proposal returns 404
    res_mod_nf = client.post(
        "/api/proposals/prop-99999999-999999-9999/modify",
        json={"priority": 1}
    )
    assert res_mod_nf.status_code == 404
    assert res_mod_nf.json()["code"] == "PROPOSAL_NOT_FOUND"


def test_control_room_frontend_index(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Co-SMOS Web Control Room" in res.text

def test_get_proposal_by_id(client, queue_dirs):
    import json
    from smos.core.proposals import Proposal, ProposalManager

    # 404 case
    res_404 = client.get("/api/proposals/nonexistent-prop-999")
    assert res_404.status_code == 404
    err_data = res_404.json()
    assert err_data["status"] == "error"
    assert err_data["code"] == "PROPOSAL_NOT_FOUND"

    # 200 case
    pm = ProposalManager()
    prop = Proposal(id="prop-test-001", description="Test Proposal For Endpoint", priority=3)
    target_file = pm.proposed_dir / "prop-test-001.json"
    target_file.write_text(json.dumps(prop.model_dump(), indent=2))

    res_200 = client.get("/api/proposals/prop-test-001")
    assert res_200.status_code == 200
    prop_data = res_200.json()
    assert prop_data["id"] == "prop-test-001"
    assert prop_data["description"] == "Test Proposal For Endpoint"

    if target_file.exists():
        target_file.unlink()

def test_get_event_by_id(client, queue_dirs):
    from smos.core.events import EventTracker

    # 404 case
    res_404 = client.get("/api/events/nonexistent-evt-999")
    assert res_404.status_code == 404
    err_data = res_404.json()
    assert err_data["status"] == "error"
    assert err_data["code"] == "EVENT_NOT_FOUND"

    # 200 case
    evt = EventTracker.emit("test_event_type", payload={"detail": "test event payload"})
    res_200 = client.get(f"/api/events/{evt.id}")
    assert res_200.status_code == 200
    evt_data = res_200.json()
    assert evt_data["id"] == evt.id
    assert evt_data["type"] == "test_event_type"
    assert evt_data["payload"]["detail"] == "test event payload"

def test_get_task_dependencies(client, queue_dirs):
    # 404 case
    res_404 = client.get("/api/tasks/nonexistent-task-999/dependencies")
    assert res_404.status_code == 404
    err_data = res_404.json()
    assert err_data["status"] == "error"
    assert err_data["code"] == "TASK_NOT_FOUND"

    # 200 case
    res_add = client.post("/api/queue", json={"request": "Dependency Test Task", "priority": 5})
    task_id = res_add.json()["task"]["id"]

    res_200 = client.get(f"/api/tasks/{task_id}/dependencies")
    assert res_200.status_code == 200
    dep_data = res_200.json()
    assert dep_data["task_id"] == task_id
    assert dep_data["depends_on"] == []
    assert dep_data["blocks"] == []

def test_get_task_replay(client, queue_dirs):
    from smos.core.events import EventTracker

    # 404 case
    res_404 = client.get("/api/tasks/nonexistent-task-999/replay")
    assert res_404.status_code == 404
    err_data = res_404.json()
    assert err_data["status"] == "error"
    assert err_data["code"] == "TASK_NOT_FOUND"

    # 200 case
    res_add = client.post("/api/queue", json={"request": "Replay Test Task", "priority": 5})
    task_id = res_add.json()["task"]["id"]

    EventTracker.emit("task_step", task_id=task_id, payload={"message": "Step 1 complete"})

    res_200 = client.get(f"/api/tasks/{task_id}/replay")
    assert res_200.status_code == 200
    replay_data = res_200.json()
    assert replay_data["task_id"] == task_id
    assert isinstance(replay_data["timeline"], list)
    assert len(replay_data["timeline"]) >= 1

def test_post_task_retry(client, queue_dirs):
    # 404 case
    res_404 = client.post("/api/tasks/nonexistent-task-999/retry")
    assert res_404.status_code == 404
    err_data = res_404.json()
    assert err_data["status"] == "error"
    assert err_data["code"] == "TASK_NOT_FOUND"

    # 400 case (PENDING status does not allow retry)
    res_add = client.post("/api/queue", json={"request": "Task Not Retryable", "priority": 5})
    task_id = res_add.json()["task"]["id"]

    res_400 = client.post(f"/api/tasks/{task_id}/retry")
    assert res_400.status_code == 400
    err_400 = res_400.json()
    assert err_400["status"] == "error"
    assert err_400["code"] == "RETRY_NOT_ALLOWED"

    # 200 case (CANCELLED status allows retry)
    client.post(f"/api/tasks/{task_id}/cancel")
    res_retry = client.post(f"/api/tasks/{task_id}/retry")
    assert res_retry.status_code == 200
    new_task = res_retry.json()
    assert new_task["id"] != task_id
    assert new_task["request"] == "Task Not Retryable"

def test_get_graph(client, queue_dirs):
    res_add = client.post("/api/queue", json={"request": "Graph Node Task", "priority": 7})
    task_id = res_add.json()["task"]["id"]

    res = client.get("/api/graph")
    assert res.status_code == 200
    graph_data = res.json()
    assert "nodes" in graph_data
    assert "edges" in graph_data
    assert isinstance(graph_data["nodes"], list)
    assert isinstance(graph_data["edges"], list)

    node_ids = [n["id"] for n in graph_data["nodes"]]
    assert task_id in node_ids
    node = next(n for n in graph_data["nodes"] if n["id"] == task_id)
    assert "status" in node
    assert "priority" in node
    assert "title" in node

def test_get_search(client, queue_dirs):
    from smos.core.events import EventTracker

    # Empty query returns empty results
    res_empty = client.get("/api/search")
    assert res_empty.status_code == 200
    assert res_empty.json() == {"tasks": [], "proposals": [], "events": []}

    # Query with matching results
    unique_term = "UniqueSearchTermForTesting"
    res_add = client.post("/api/queue", json={"request": f"Task with {unique_term}", "priority": 5})
    task_id = res_add.json()["task"]["id"]

    EventTracker.emit("custom_search_event", task_id=task_id, payload={"data": f"Event with {unique_term}"})

    res_search = client.get(f"/api/search?q={unique_term.lower()}")
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert len(search_data["tasks"]) >= 1
    assert any(t["id"] == task_id for t in search_data["tasks"])
    assert len(search_data["events"]) >= 1
