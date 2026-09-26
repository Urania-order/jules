import pytest
from fastapi.testclient import TestClient
from smos.api.main import app

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer dev-operator-token"}


@pytest.fixture
def created_prediction():
    resp = client.post(
        "/api/predictions",
        json={
            "expected_state": {"temperature": 105.5, "status": "overheating"},
            "source_hypothesis_type": "phenomenon",
            "source_hypothesis_id": 1,
            "conditions": ["high_load"],
            "confidence": 0.82,
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["epistemic_status"] == "PREDICTED"
    return data


def test_attach_outcome_endpoint_returns_200(created_prediction):
    pred_id = created_prediction["id"]
    outcome_payload = {"actual_outcome": {"temperature": 108.0, "result": "melted"}}
    resp = client.post(
        f"/api/predictions/{pred_id}/outcome",
        json=outcome_payload,
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == pred_id
    assert data["actual_outcome"] == {"temperature": 108.0, "result": "melted"}


def test_attach_outcome_persists(created_prediction):
    pred_id = created_prediction["id"]
    outcome_payload = {"actual_outcome": {"measured_val": 42}}
    client.post(
        f"/api/predictions/{pred_id}/outcome",
        json=outcome_payload,
        headers=AUTH_HEADERS,
    )

    get_resp = client.get(f"/api/predictions/{pred_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["actual_outcome"] == {"measured_val": 42}


def test_attach_outcome_does_not_change_epistemic_status(created_prediction):
    pred_id = created_prediction["id"]
    assert created_prediction["epistemic_status"] == "PREDICTED"

    resp = client.post(
        f"/api/predictions/{pred_id}/outcome",
        json={"actual_outcome": {"observed": True}},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["epistemic_status"] == "PREDICTED"

    get_resp = client.get(f"/api/predictions/{pred_id}")
    assert get_resp.json()["epistemic_status"] == "PREDICTED"


def test_attach_outcome_404_for_unknown_prediction():
    resp = client.post(
        "/api/predictions/999999/outcome",
        json={"actual_outcome": {"test": 1}},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "NOT_FOUND"


def test_attach_outcome_422_on_invalid_body(created_prediction):
    pred_id = created_prediction["id"]
    # Missing actual_outcome field
    resp = client.post(
        f"/api/predictions/{pred_id}/outcome",
        json={"wrong_key": 123},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 422


def test_attach_outcome_requires_operator(created_prediction):
    pred_id = created_prediction["id"]
    resp = client.post(
        f"/api/predictions/{pred_id}/outcome",
        json={"actual_outcome": {"data": "test"}},
    )
    assert resp.status_code == 401


def test_evaluate_endpoint_returns_200(created_prediction):
    pred_id = created_prediction["id"]
    eval_payload = {"evaluation": {"accuracy": 0.95, "verdict": "accurate"}}
    resp = client.post(
        f"/api/predictions/{pred_id}/evaluate",
        json=eval_payload,
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == pred_id
    assert data["evaluation"] == {"accuracy": 0.95, "verdict": "accurate"}


def test_evaluate_persists(created_prediction):
    pred_id = created_prediction["id"]
    eval_payload = {"evaluation": {"error_margin": 0.02}}
    client.post(
        f"/api/predictions/{pred_id}/evaluate",
        json=eval_payload,
        headers=AUTH_HEADERS,
    )

    get_resp = client.get(f"/api/predictions/{pred_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["evaluation"] == {"error_margin": 0.02}


def test_evaluate_does_not_change_epistemic_status(created_prediction):
    pred_id = created_prediction["id"]
    assert created_prediction["epistemic_status"] == "PREDICTED"

    resp = client.post(
        f"/api/predictions/{pred_id}/evaluate",
        json={"evaluation": {"valid": True}},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["epistemic_status"] == "PREDICTED"

    get_resp = client.get(f"/api/predictions/{pred_id}")
    assert get_resp.json()["epistemic_status"] == "PREDICTED"


def test_evaluate_404_for_unknown_prediction():
    resp = client.post(
        "/api/predictions/999999/evaluate",
        json={"evaluation": {"score": 100}},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "NOT_FOUND"


def test_evaluate_422_on_invalid_body(created_prediction):
    pred_id = created_prediction["id"]
    # Missing evaluation field
    resp = client.post(
        f"/api/predictions/{pred_id}/evaluate",
        json={"wrong_key": 123},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 422


def test_evaluate_requires_operator(created_prediction):
    pred_id = created_prediction["id"]
    resp = client.post(
        f"/api/predictions/{pred_id}/evaluate",
        json={"evaluation": {"score": 50}},
    )
    assert resp.status_code == 401


def test_prediction_no_auto_promotion_full_flow():
    # 1. Create prediction
    create_resp = client.post(
        "/api/predictions",
        json={
            "expected_state": {"pressure": 101.3},
            "source_hypothesis_type": "potential_phenomenon",
            "source_hypothesis_id": 10,
            "confidence": 0.90,
        },
        headers=AUTH_HEADERS,
    )
    assert create_resp.status_code == 200
    pred = create_resp.json()
    pred_id = pred["id"]
    assert pred["epistemic_status"] == "PREDICTED"

    # 2. Attach outcome
    outcome_resp = client.post(
        f"/api/predictions/{pred_id}/outcome",
        json={"actual_outcome": {"pressure": 101.5, "delta": 0.2}},
        headers=AUTH_HEADERS,
    )
    assert outcome_resp.status_code == 200
    outcome_data = outcome_resp.json()
    assert outcome_data["actual_outcome"] == {"pressure": 101.5, "delta": 0.2}
    assert outcome_data["epistemic_status"] == "PREDICTED"

    # 3. Evaluate prediction
    eval_resp = client.post(
        f"/api/predictions/{pred_id}/evaluate",
        json={"evaluation": {"match": True, "score": 0.98}},
        headers=AUTH_HEADERS,
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["evaluation"] == {"match": True, "score": 0.98}
    assert eval_data["epistemic_status"] == "PREDICTED"

    # 4. Re-fetch via GET, verify status PREDICTED and both outcome/evaluation persist
    get_resp = client.get(f"/api/predictions/{pred_id}")
    assert get_resp.status_code == 200
    final_pred = get_resp.json()
    assert final_pred["epistemic_status"] == "PREDICTED"
    assert final_pred["actual_outcome"] == {"pressure": 101.5, "delta": 0.2}
    assert final_pred["evaluation"] == {"match": True, "score": 0.98}


def test_existing_crud_endpoints_unchanged(created_prediction):
    pred_id = created_prediction["id"]

    # GET list
    list_resp = client.get("/api/predictions")
    assert list_resp.status_code == 200
    assert any(p["id"] == pred_id for p in list_resp.json())

    # GET single
    get_resp = client.get(f"/api/predictions/{pred_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == pred_id

    # PUT metadata update
    put_resp = client.put(
        f"/api/predictions/{pred_id}",
        json={"confidence": 0.99, "provenance": {"source": "test_crud"}},
        headers=AUTH_HEADERS,
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["confidence"] == 0.99
    assert updated["provenance"] == {"source": "test_crud"}
    assert updated["epistemic_status"] == "PREDICTED"


def test_delete_still_not_available_for_predictions(created_prediction):
    pred_id = created_prediction["id"]
    resp = client.delete(f"/api/predictions/{pred_id}", headers=AUTH_HEADERS)
    assert resp.status_code in (404, 405)
