import pytest
from fastapi.testclient import TestClient
from smos.api.main import app

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer dev-operator-token"}


def test_graph_returns_nodes_and_edges():
    resp = client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


def test_graph_includes_task_nodes():
    # Add a task via queue
    add_resp = client.post("/api/queue", json={"request": "Graph Task Test", "priority": 3}, headers=AUTH_HEADERS)
    assert add_resp.status_code == 200
    task_id = add_resp.json()["task"]["id"]

    resp = client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()

    task_nodes = [n for n in data["nodes"] if n.get("type") == "task" or n["id"] == task_id]
    assert len(task_nodes) > 0
    node = next(n for n in data["nodes"] if n["id"] == task_id)
    assert node["type"] == "task"
    assert "status" in node
    assert "priority" in node


def test_graph_includes_phenomenon_nodes():
    resp = client.post(
        "/api/phenomena",
        json={"name": "Graph Phenomenon", "description": "Test phenomenon for graph", "epistemic_status": "OBSERVED"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    p_id = resp.json()["id"]

    resp = client.get("/api/graph")
    assert resp.status_code == 200
    nodes = resp.json()["nodes"]

    target_id = f"phenomenon:{p_id}"
    phen_node = next((n for n in nodes if n["id"] == target_id), None)
    assert phen_node is not None
    assert phen_node["type"] == "phenomenon"
    assert phen_node["label"] == "Graph Phenomenon"
    assert phen_node["status"] == "OBSERVED"


def test_graph_includes_context_nodes():
    resp = client.post(
        "/api/contexts",
        json={"name": "Graph Context", "description": "Test context for graph"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    c_id = resp.json()["id"]

    resp = client.get("/api/graph")
    assert resp.status_code == 200
    nodes = resp.json()["nodes"]

    target_id = f"context:{c_id}"
    ctx_node = next((n for n in nodes if n["id"] == target_id), None)
    assert ctx_node is not None
    assert ctx_node["type"] == "context"
    assert ctx_node["label"] == "Graph Context"


def test_graph_includes_constraint_nodes():
    resp = client.post(
        "/api/constraints",
        json={"name": "Graph Constraint", "type": "PHYSICAL", "status": "ACTIVE"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    k_id = resp.json()["id"]

    resp = client.get("/api/graph")
    assert resp.status_code == 200
    nodes = resp.json()["nodes"]

    target_id = f"constraint:{k_id}"
    const_node = next((n for n in nodes if n["id"] == target_id), None)
    assert const_node is not None
    assert const_node["type"] == "constraint"
    assert const_node["label"] == "Graph Constraint"
    assert const_node["status"] == "ACTIVE"


def test_graph_includes_potential_nodes():
    resp = client.post(
        "/api/potential-phenomena",
        json={"phenomenon": "Graph Potential", "status": "POSSIBLE"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    pot_id = resp.json()["id"]

    resp = client.get("/api/graph")
    assert resp.status_code == 200
    nodes = resp.json()["nodes"]

    target_id = f"potential:{pot_id}"
    pot_node = next((n for n in nodes if n["id"] == target_id), None)
    assert pot_node is not None
    assert pot_node["type"] == "potential"
    assert pot_node["label"] == "Graph Potential"
    assert pot_node["status"] == "POSSIBLE"


def test_graph_includes_prediction_nodes():
    resp = client.post(
        "/api/predictions",
        json={
            "expected_state": {"detail": "System equilibrium reached"},
            "source_hypothesis_type": "phenomenon",
            "source_hypothesis_id": 1,
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    pred_id = resp.json()["id"]

    resp = client.get("/api/graph")
    assert resp.status_code == 200
    nodes = resp.json()["nodes"]

    target_id = f"prediction:{pred_id}"
    pred_node = next((n for n in nodes if n["id"] == target_id), None)
    assert pred_node is not None
    assert pred_node["type"] == "prediction"
    assert "equilibrium" in pred_node["label"]
    assert pred_node["status"] == "PREDICTED"


def test_graph_edges_from_domain_relations():
    # Create context and phenomenon
    c_resp = client.post("/api/contexts", json={"name": "Rel Context"}, headers=AUTH_HEADERS)
    c_id = c_resp.json()["id"]
    p_resp = client.post("/api/phenomena", json={"name": "Rel Phenomenon"}, headers=AUTH_HEADERS)
    p_id = p_resp.json()["id"]

    # Create domain relation
    rel_resp = client.post(
        "/api/domain-relations",
        json={
            "source_type": "context",
            "source_id": c_id,
            "target_type": "phenomenon",
            "target_id": p_id,
            "relation_type": "ENABLES",
            "confidence": 0.9,
        },
        headers=AUTH_HEADERS,
    )
    assert rel_resp.status_code == 200

    resp = client.get("/api/graph")
    assert resp.status_code == 200
    edges = resp.json()["edges"]

    edge = next(
        (e for e in edges if e["source"] == f"context:{c_id}" and e["target"] == f"phenomenon:{p_id}"),
        None,
    )
    assert edge is not None
    assert edge["type"] == "ENABLES"
    assert edge["confidence"] == 0.9


def test_graph_edges_from_prediction_source():
    # Create phenomenon
    p_resp = client.post("/api/phenomena", json={"name": "Pred Source Phen"}, headers=AUTH_HEADERS)
    p_id = p_resp.json()["id"]

    # Create prediction referencing phenomenon
    pred_resp = client.post(
        "/api/predictions",
        json={
            "expected_state": {"detail": "Prediction with source link"},
            "source_hypothesis_type": "phenomenon",
            "source_hypothesis_id": p_id,
        },
        headers=AUTH_HEADERS,
    )
    assert pred_resp.status_code == 200
    pred_id = pred_resp.json()["id"]

    resp = client.get("/api/graph")
    assert resp.status_code == 200
    edges = resp.json()["edges"]

    edge = next(
        (e for e in edges if e["source"] == f"prediction:{pred_id}" and e["target"] == f"phenomenon:{p_id}"),
        None,
    )
    assert edge is not None
    assert edge["type"] == "PREDICTS"


def test_graph_node_id_format():
    resp = client.get("/api/graph")
    assert resp.status_code == 200
    nodes = resp.json()["nodes"]

    for n in nodes:
        node_id = n["id"]
        node_type = n["type"]
        if node_type == "task":
            assert node_id.startswith("task")
        else:
            assert node_id.startswith(f"{node_type}:")


def test_graph_empty_db():
    resp = client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


def test_graph_read_only():
    resp_get = client.get("/api/graph")
    assert resp_get.status_code == 200

    resp_post = client.post("/api/graph", json={"data": "test"})
    assert resp_post.status_code in (404, 405)

    resp_put = client.put("/api/graph", json={"data": "test"})
    assert resp_put.status_code in (404, 405)

    resp_delete = client.delete("/api/graph")
    assert resp_delete.status_code in (404, 405)
