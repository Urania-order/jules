import json
import pytest
from smos.models.models import EpistemicStatus, MemoryNode, User, Timeline, TimelineType
from smos.services.epistemic_service import EpistemicService
from smos.core.database import SessionLocal
from fastapi.testclient import TestClient
from smos.api.main import app

client = TestClient(app)

def test_canonical_and_legacy_statuses_exist():
    # Canonical 7
    canonical_expected = {
        "OBSERVED",
        "INFERRED",
        "HYPOTHESIZED",
        "PREDICTED",
        "UNVALIDATED",
        "CONTESTED",
        "REFUTED",
    }
    for name in canonical_expected:
        status = EpistemicStatus[name]
        assert status.value == name
        assert status.is_canonical is True

    # Legacy statuses preserved
    legacy_expected = {
        "VERIFIED": "Verified",
        "HYPOTHESIS": "Hypothesis",
        "COUNTERFACTUAL": "Counterfactual",
        "HISTORICAL_RECONSTRUCTION": "Historical Reconstruction",
        "SPECULATIVE": "Speculative",
        "BEYOND_ALL_CONSENSUS": "Beyond All Consensus",
        "UNVERIFIED": "Unverified",
    }
    for name, expected_val in legacy_expected.items():
        status = EpistemicStatus[name]
        assert status.value == expected_val
        assert status.is_canonical is False


def test_serialization_deserialization():
    for status in EpistemicStatus:
        # Serialized form
        serialized = status.serialize()
        assert isinstance(serialized, str)

        # Deserialized back
        deserialized = EpistemicStatus.deserialize(serialized)
        assert deserialized == status

        # JSON roundtrip
        data = {"status": status.serialize()}
        json_str = json.dumps(data)
        loaded = json.loads(json_str)
        assert EpistemicStatus.deserialize(loaded["status"]) == status


def test_flexible_string_parsing_and_case_insensitivity():
    # Canonical string parsing (upper, lower, mixed)
    assert EpistemicStatus.from_str("OBSERVED") == EpistemicStatus.OBSERVED
    assert EpistemicStatus.from_str("observed") == EpistemicStatus.OBSERVED
    assert EpistemicStatus.from_str("Observed") == EpistemicStatus.OBSERVED

    # Legacy string parsing
    assert EpistemicStatus.from_str("Verified") == EpistemicStatus.VERIFIED
    assert EpistemicStatus.from_str("VERIFIED") == EpistemicStatus.VERIFIED
    assert EpistemicStatus.from_str("verified") == EpistemicStatus.VERIFIED

    with pytest.raises(ValueError):
        EpistemicStatus.from_str("NON_EXISTENT_STATUS")


def test_legacy_to_canonical_mapping():
    assert EpistemicStatus.VERIFIED.to_canonical() == EpistemicStatus.OBSERVED
    assert EpistemicStatus.HYPOTHESIS.to_canonical() == EpistemicStatus.HYPOTHESIZED
    assert EpistemicStatus.UNVERIFIED.to_canonical() == EpistemicStatus.UNVALIDATED
    assert EpistemicStatus.BEYOND_ALL_CONSENSUS.to_canonical() == EpistemicStatus.CONTESTED

    # Canonical status maps to self
    for canonical in [
        EpistemicStatus.OBSERVED,
        EpistemicStatus.INFERRED,
        EpistemicStatus.HYPOTHESIZED,
        EpistemicStatus.PREDICTED,
        EpistemicStatus.UNVALIDATED,
        EpistemicStatus.CONTESTED,
        EpistemicStatus.REFUTED,
    ]:
        assert canonical.to_canonical() == canonical


def test_epistemic_service_integration():
    db = SessionLocal()
    try:
        user = User(display_name="Tester")
        db.add(user)
        db.commit()

        tl = Timeline(type=TimelineType.REAL, description="Main")
        db.add(tl)
        db.commit()

        node = MemoryNode(
            content="Observation statement",
            owner_id=user.id,
            timeline_id=tl.id,
            epistemic_status=EpistemicStatus.UNVALIDATED,
        )
        db.add(node)
        db.commit()
        db.refresh(node)

        svc = EpistemicService(db)

        # Update using canonical enum
        updated = svc.update_node_status(node.id, EpistemicStatus.OBSERVED)
        assert updated.epistemic_status == EpistemicStatus.OBSERVED

        # Update using string (case insensitive)
        updated2 = svc.update_node_status(node.id, "hypothesized")
        assert updated2.epistemic_status == EpistemicStatus.HYPOTHESIZED

        # Query by status
        hyp_nodes = svc.get_nodes_by_status("HYPOTHESIZED")
        assert len(hyp_nodes) == 1
        assert hyp_nodes[0].id == node.id

    finally:
        db.close()


def test_epistemic_api_endpoints():
    # GET /epistemic/statuses
    resp = client.get("/epistemic/statuses")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert "OBSERVED" in body["canonical"]
    assert "Verified" in body["legacy"]

    # POST /epistemic/node/{node_id}/status
    db = SessionLocal()
    try:
        user = User(display_name="API Tester")
        db.add(user)
        db.commit()

        tl = Timeline(type=TimelineType.REAL, description="Main")
        db.add(tl)
        db.commit()

        node = MemoryNode(
            content="API test node",
            owner_id=user.id,
            timeline_id=tl.id,
            epistemic_status=EpistemicStatus.UNVALIDATED,
        )
        db.add(node)
        db.commit()
        node_id = node.id
    finally:
        db.close()

    resp_post = client.post(f"/epistemic/node/{node_id}/status?status=CONTESTED")
    assert resp_post.status_code == 200
    assert resp_post.json()["epistemic_status"] == "CONTESTED"

    resp_err = client.post(f"/epistemic/node/{node_id}/status?status=INVALID_STATUS")
    assert resp_err.status_code == 400
