import pytest
from fastapi.testclient import TestClient
from smos.api.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_control_room_system_status(client):
    res = client.get("/api/system/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "tasks_summary" in data
    assert "proposals_summary" in data

def test_control_room_create_and_list_tasks(client):
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

def test_control_room_task_lifecycle(client):
    res_add = client.post("/api/queue", json={"request": "Lifecycle Task", "priority": 5})
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

def test_control_room_proposals(client):
    """Test proposals API. Defer may return 200 or 400 depending on state."""
    res_props = client.get("/api/proposals")
    assert res_props.status_code == 200
    props = res_props.json()
    assert isinstance(props, list)
    
    if props:
        prop_id = props[0]["id"]
        res_defer = client.post(f"/api/proposals/{prop_id}/defer")
        assert res_defer.status_code in (200, 400)

def test_control_room_frontend_index(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Co-SMOS Web Control Room" in res.text
