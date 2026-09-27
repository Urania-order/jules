import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from smos.api.main import app
from smos.models.four_position_contract import normalize_four_position_analysis, FourPosition
from smos.models.phenomenon import Phenomenon
from smos.models.domain_relation import DomainRelation
from smos.models.prediction import Prediction
from smos.models.experience import Recipe
from smos.models.domain_event import DomainEvent

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer dev-operator-token"}


def test_1_successful_analysis():
    # Create phenomenon
    resp = client.post(
        "/api/phenomena",
        json={"name": "Api Analysis Phenomenon", "description": "Test phenomenon"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    p_id = resp.json()["id"]

    # Call four-position analyze endpoint
    anal_resp = client.post(f"/api/four-position/analyze/{p_id}", headers=AUTH_HEADERS)
    assert anal_resp.status_code == 200
    data = anal_resp.json()
    assert isinstance(data, dict)
    assert data["phenomenon_id"] == p_id


def test_2_authentication():
    # Unauthenticated request
    resp = client.post("/api/four-position/analyze/1")
    assert resp.status_code in (401, 403)


def test_3_unknown_phenomenon():
    # Valid integer ID that does not exist in DB
    resp = client.post("/api/four-position/analyze/999999", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["phenomenon_id"] == 999999
    assert data["created_at"] is None
    for pos_key, pos_val in data["positions"].items():
        assert pos_val["status"] == "UNRESOLVED"
        assert pos_val["claim"] is None


def test_4_invalid_path_parameter():
    resp = client.post("/api/four-position/analyze/not-an-integer", headers=AUTH_HEADERS)
    assert resp.status_code == 422


def test_5_canonical_structure():
    resp = client.post(
        "/api/phenomena",
        json={"name": "Canonical Structure Phenomenon"},
        headers=AUTH_HEADERS,
    )
    p_id = resp.json()["id"]

    anal_resp = client.post(f"/api/four-position/analyze/{p_id}", headers=AUTH_HEADERS)
    assert anal_resp.status_code == 200
    data = anal_resp.json()

    assert "phenomenon_id" in data
    assert "positions" in data
    assert "created_at" in data

    positions = data["positions"]
    expected_keys = {
        FourPosition.PRESENT_EXISTS.value,
        FourPosition.ABSENT_ABSENT.value,
        FourPosition.ABSENT_EXISTS.value,
        FourPosition.PRESENT_ABSENT.value,
    }
    assert set(positions.keys()) == expected_keys


def test_6_unresolved_positions_preserved():
    resp = client.post(
        "/api/phenomena",
        json={"name": "Unresolved Phenomenon"},
        headers=AUTH_HEADERS,
    )
    p_id = resp.json()["id"]

    anal_resp = client.post(f"/api/four-position/analyze/{p_id}", headers=AUTH_HEADERS)
    assert anal_resp.status_code == 200
    data = anal_resp.json()

    for pos_key, pos_val in data["positions"].items():
        assert pos_val["status"] == "UNRESOLVED"
        assert pos_val["claim"] is None
        assert pos_val["evidence"] == []
        assert pos_val["context"] == []


def test_7_read_only_behavior(db):
    resp = client.post(
        "/api/phenomena",
        json={"name": "Read Only Phenomenon"},
        headers=AUTH_HEADERS,
    )
    p_id = resp.json()["id"]

    # Snapshot entity counts
    phenomenon_count_before = db.query(Phenomenon).count()
    relation_count_before = db.query(DomainRelation).count()
    prediction_count_before = db.query(Prediction).count()
    recipe_count_before = db.query(Recipe).count()
    event_count_before = db.query(DomainEvent).count()

    anal_resp = client.post(f"/api/four-position/analyze/{p_id}", headers=AUTH_HEADERS)
    assert anal_resp.status_code == 200

    # Verify counts unchanged
    assert db.query(Phenomenon).count() == phenomenon_count_before
    assert db.query(DomainRelation).count() == relation_count_before
    assert db.query(Prediction).count() == prediction_count_before
    assert db.query(Recipe).count() == recipe_count_before
    assert db.query(DomainEvent).count() == event_count_before


def test_8_reproducibility():
    resp = client.post(
        "/api/phenomena",
        json={"name": "Reproducibility Phenomenon"},
        headers=AUTH_HEADERS,
    )
    p_id = resp.json()["id"]

    resp1 = client.post(f"/api/four-position/analyze/{p_id}", headers=AUTH_HEADERS).json()
    resp2 = client.post(f"/api/four-position/analyze/{p_id}", headers=AUTH_HEADERS).json()

    norm1 = normalize_four_position_analysis(resp1)
    norm2 = normalize_four_position_analysis(resp2)
    assert norm1 == norm2


def test_9_delegation():
    resp = client.post(
        "/api/phenomena",
        json={"name": "Delegation Phenomenon"},
        headers=AUTH_HEADERS,
    )
    p_id = resp.json()["id"]

    mock_analysis = {
        "phenomenon_id": p_id,
        "positions": {
            "PRESENT_EXISTS": {
                "position": "PRESENT_EXISTS",
                "claim": "Delegated Claim",
                "confidence": 0.9,
                "evidence": [1],
                "context": [],
                "provenance": {},
                "epistemic_status": "OBSERVED",
                "status": "RESOLVED",
            },
            "ABSENT_ABSENT": {
                "position": "ABSENT_ABSENT",
                "claim": None,
                "confidence": None,
                "evidence": [],
                "context": [],
                "provenance": {},
                "epistemic_status": "UNVALIDATED",
                "status": "UNRESOLVED",
            },
            "ABSENT_EXISTS": {
                "position": "ABSENT_EXISTS",
                "claim": None,
                "confidence": None,
                "evidence": [],
                "context": [],
                "provenance": {},
                "epistemic_status": "UNVALIDATED",
                "status": "UNRESOLVED",
            },
            "PRESENT_ABSENT": {
                "position": "PRESENT_ABSENT",
                "claim": None,
                "confidence": None,
                "evidence": [],
                "context": [],
                "provenance": {},
                "epistemic_status": "UNVALIDATED",
                "status": "UNRESOLVED",
            },
        },
        "created_at": "2026-09-27T17:00:00+00:00",
    }

    with patch(
        "smos.services.four_position_service.FourPositionService.build_analysis",
        return_value=mock_analysis,
    ) as mock_build:
        anal_resp = client.post(f"/api/four-position/analyze/{p_id}", headers=AUTH_HEADERS)
        assert anal_resp.status_code == 200
        mock_build.assert_called_once_with(phenomenon_id=p_id)
        assert anal_resp.json() == mock_analysis
