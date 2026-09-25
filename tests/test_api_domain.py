import pytest
from fastapi.testclient import TestClient
from smos.api.main import app

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer dev-operator-token"}


def test_phenomenon_crud_and_auth():
    # Unauthorized write
    resp = client.post("/api/phenomena", json={"name": "P1"})
    assert resp.status_code == 401

    # Create
    resp = client.post(
        "/api/phenomena",
        json={"name": "Emergent Noise", "description": "A test phenomenon", "epistemic_status": "OBSERVED"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    p_id = data["id"]
    assert data["name"] == "Emergent Noise"
    assert data["epistemic_status"] == "OBSERVED"

    # Get
    resp = client.get(f"/api/phenomena/{p_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == p_id

    # List
    resp = client.get("/api/phenomena")
    assert resp.status_code == 200
    items = resp.json()
    assert any(i["id"] == p_id for i in items)

    # Update
    resp = client.put(
        f"/api/phenomena/{p_id}",
        json={"description": "Updated description"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated description"

    # Delete
    resp = client.delete(f"/api/phenomena/{p_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # Get Not Found
    resp = client.get(f"/api/phenomena/{p_id}")
    assert resp.status_code == 404


def test_context_crud():
    resp = client.post(
        "/api/contexts",
        json={"name": "Lab Context", "spatial_scope": "Building A"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    c_id = resp.json()["id"]

    resp = client.get(f"/api/contexts/{c_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Lab Context"

    resp = client.put(
        f"/api/contexts/{c_id}",
        json={"spatial_scope": "Building B"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["spatial_scope"] == "Building B"

    resp = client.delete(f"/api/contexts/{c_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 200


def test_constraint_crud():
    resp = client.post(
        "/api/constraints",
        json={"name": "Thermal Limit", "type": "PHYSICAL", "confidence": 0.9},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    k_id = resp.json()["id"]

    resp = client.get(f"/api/constraints/{k_id}")
    assert resp.status_code == 200
    assert resp.json()["type"] == "PHYSICAL"

    resp = client.put(
        f"/api/constraints/{k_id}",
        json={"confidence": 0.95},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["confidence"] == 0.95

    resp = client.delete(f"/api/constraints/{k_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 200


def test_potential_crud():
    resp = client.post(
        "/api/potential-phenomena",
        json={"phenomenon": "Thermal Runaway", "status": "POSSIBLE"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    pot_id = resp.json()["id"]

    resp = client.get(f"/api/potential-phenomena/{pot_id}")
    assert resp.status_code == 200
    assert resp.json()["phenomenon"] == "Thermal Runaway"

    resp = client.put(
        f"/api/potential-phenomena/{pot_id}",
        json={"status": "BLOCKED"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "BLOCKED"

    resp = client.delete(f"/api/potential-phenomena/{pot_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 200


def test_domain_relation_crud_and_cross_domain():
    p_resp = client.post("/api/phenomena", json={"name": "Phenomenon A"}, headers=AUTH_HEADERS)
    p_id = p_resp.json()["id"]

    c_resp = client.post("/api/contexts", json={"name": "Context B"}, headers=AUTH_HEADERS)
    c_id = c_resp.json()["id"]

    r_resp = client.post(
        "/api/domain-relations",
        json={
            "source_type": "context",
            "source_id": c_id,
            "target_type": "phenomenon",
            "target_id": p_id,
            "relation_type": "ENABLES",
            "provenance": {"source": "unit_test"},
            "confidence": 0.85,
        },
        headers=AUTH_HEADERS,
    )
    assert r_resp.status_code == 200
    rel_data = r_resp.json()
    rel_id = rel_data["id"]
    assert rel_data["provenance"] == {"source": "unit_test"}

    resp = client.get(f"/api/domain-relations/{rel_id}")
    assert resp.status_code == 200
    assert resp.json()["relation_type"] == "ENABLES"

    resp = client.put(
        f"/api/domain-relations/{rel_id}",
        json={"confidence": 0.95},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["confidence"] == 0.95

    resp = client.delete(f"/api/domain-relations/{rel_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 200


def test_prediction_api_contract():
    # Create prediction
    p_resp = client.post(
        "/api/predictions",
        json={
            "expected_state": {"temperature": 100},
            "source_hypothesis_type": "potential_phenomenon",
            "source_hypothesis_id": 42,
            "confidence": 0.75,
        },
        headers=AUTH_HEADERS,
    )
    assert p_resp.status_code == 200
    pred = p_resp.json()
    pred_id = pred["id"]
    assert pred["epistemic_status"] == "PREDICTED"
    assert pred["source_hypothesis_type"] == "potential_phenomenon"
    assert pred["source_hypothesis_id"] == 42
    assert pred["created_at"] is not None
    assert pred["prediction_time"] is not None

    # Get prediction
    resp = client.get(f"/api/predictions/{pred_id}")
    assert resp.status_code == 200
    assert resp.json()["confidence"] == 0.75

    # List predictions
    resp = client.get("/api/predictions")
    assert resp.status_code == 200
    assert any(p["id"] == pred_id for p in resp.json())

    # Update metadata only
    resp = client.put(
        f"/api/predictions/{pred_id}",
        json={"confidence": 0.88, "provenance": {"note": "recalculated"}},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["confidence"] == 0.88
    assert updated["provenance"] == {"note": "recalculated"}
    # Epistemic status remains PREDICTED (not promoted)
    assert updated["epistemic_status"] == "PREDICTED"

    # DELETE MUST NOT be exposed
    resp = client.delete(f"/api/predictions/{pred_id}", headers=AUTH_HEADERS)
    assert resp.status_code in (404, 405)


def test_analysis_endpoints():
    p_resp = client.post("/api/phenomena", json={"name": "Signal Drift"}, headers=AUTH_HEADERS)
    p_id = p_resp.json()["id"]

    c_resp = client.post("/api/constraints", json={"name": "Bandwidth Limit"}, headers=AUTH_HEADERS)
    c_id = c_resp.json()["id"]

    client.post(
        "/api/domain-relations",
        json={
            "source_type": "constraint",
            "source_id": c_id,
            "target_type": "phenomenon",
            "target_id": p_id,
            "relation_type": "BLOCKS",
        },
        headers=AUTH_HEADERS,
    )

    # Blockage analysis
    resp = client.post(f"/api/blockage/analyze/{p_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    blockage = resp.json()
    assert blockage["kind"] == "blockage_analysis"
    assert blockage["phenomenon_id"] == p_id

    # Emergence analysis
    resp = client.post(f"/api/emergence/analyze/{p_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    emergence = resp.json()
    assert emergence["kind"] == "emergence_analysis"
    assert emergence["phenomenon_id"] == p_id

    # Convergent resonance detection
    resp = client.post("/api/resonance/detect", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_vertical_slice():
    # 1. Phenomenon
    p_resp = client.post("/api/phenomena", json={"name": "Slice Phenomenon"}, headers=AUTH_HEADERS)
    p_id = p_resp.json()["id"]

    # 2. Context
    c_resp = client.post("/api/contexts", json={"name": "Slice Context"}, headers=AUTH_HEADERS)
    c_id = c_resp.json()["id"]

    # 3. DomainRelation (Context -> Phenomenon ENABLES)
    client.post(
        "/api/domain-relations",
        json={
            "source_type": "context",
            "source_id": c_id,
            "target_type": "phenomenon",
            "target_id": p_id,
            "relation_type": "ENABLES",
        },
        headers=AUTH_HEADERS,
    )

    # 4. Constraint
    k_resp = client.post("/api/constraints", json={"name": "Slice Constraint"}, headers=AUTH_HEADERS)
    k_id = k_resp.json()["id"]

    # 5. DomainRelation (Constraint -> Phenomenon BLOCKS)
    client.post(
        "/api/domain-relations",
        json={
            "source_type": "constraint",
            "source_id": k_id,
            "target_type": "phenomenon",
            "target_id": p_id,
            "relation_type": "BLOCKS",
        },
        headers=AUTH_HEADERS,
    )

    # 6. Blockage Analysis
    b_resp = client.post(f"/api/blockage/analyze/{p_id}", headers=AUTH_HEADERS)
    assert b_resp.status_code == 200
    assert len(b_resp.json()["direct_constraints"]) > 0

    # 7. Prediction
    pred_resp = client.post(
        "/api/predictions",
        json={
            "expected_state": {"slice": "active"},
            "source_hypothesis_type": "phenomenon",
            "source_hypothesis_id": p_id,
        },
        headers=AUTH_HEADERS,
    )
    pred_id = pred_resp.json()["id"]

    # 8. PUT Prediction
    put_resp = client.put(
        f"/api/predictions/{pred_id}",
        json={"confidence": 0.9},
        headers=AUTH_HEADERS,
    )
    assert put_resp.status_code == 200

    # 9. GET Prediction
    get_pred = client.get(f"/api/predictions/{pred_id}")
    assert get_pred.status_code == 200
    assert get_pred.json()["confidence"] == 0.9
