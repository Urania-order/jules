import pytest
from smos.models.models import EpistemicStatus
from smos.models.phenomenon import Phenomenon
from smos.services.phenomenon_service import PhenomenonService


def test_create_phenomenon(db):
    service = PhenomenonService(db)
    phenomenon = service.create(
        name="Solar Flare Anomaly",
        description="Unusual magnetic disruption observed in region 402",
        epistemic_status=EpistemicStatus.OBSERVED,
        source="Observatory Station Alpha",
        provenance={"sensor_ids": [101, 102], "confidence": 0.88},
    )
    assert phenomenon.id is not None
    assert phenomenon.name == "Solar Flare Anomaly"
    assert phenomenon.description == "Unusual magnetic disruption observed in region 402"
    assert phenomenon.epistemic_status == EpistemicStatus.OBSERVED
    assert phenomenon.source == "Observatory Station Alpha"
    assert phenomenon.provenance == {"sensor_ids": [101, 102], "confidence": 0.88}


def test_serialize_phenomenon(db):
    service = PhenomenonService(db)
    phenomenon = service.create(
        name="Gravitational Drift",
        description="Minor orbital offset detected",
        epistemic_status=EpistemicStatus.INFERRED,
        source="Telemetry Data",
        provenance={"run_id": "sim-99"},
    )
    serialized = phenomenon.to_dict()
    assert isinstance(serialized, dict)
    assert serialized["id"] == phenomenon.id
    assert serialized["name"] == "Gravitational Drift"
    assert serialized["description"] == "Minor orbital offset detected"
    assert serialized["epistemic_status"] == "INFERRED"
    assert serialized["source"] == "Telemetry Data"
    assert serialized["provenance"] == {"run_id": "sim-99"}
    assert "created_at" in serialized
    assert "updated_at" in serialized


def test_persist_phenomenon(db):
    phenomenon = Phenomenon(
        name="Direct Persistence Test",
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
        provenance={"created_by": "direct_sql"},
    )
    db.add(phenomenon)
    db.commit()
    db.refresh(phenomenon)

    persisted = db.get(Phenomenon, phenomenon.id)
    assert persisted is not None
    assert persisted.name == "Direct Persistence Test"
    assert persisted.epistemic_status == EpistemicStatus.HYPOTHESIZED
    assert persisted.provenance == {"created_by": "direct_sql"}


def test_retrieve_phenomenon(db):
    service = PhenomenonService(db)
    created = service.create(name="Retrieval Target")
    retrieved = service.get(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.name == "Retrieval Target"

    non_existent = service.get(99999)
    assert non_existent is None


def test_list_phenomena(db):
    service = PhenomenonService(db)
    p1 = service.create(name="Phenomenon A")
    p2 = service.create(name="Phenomenon B")
    p3 = service.create(name="Phenomenon C")

    items = service.list(limit=10, offset=0)
    assert len(items) >= 3
    names = [p.name for p in items]
    assert "Phenomenon A" in names
    assert "Phenomenon B" in names
    assert "Phenomenon C" in names


def test_update_phenomenon(db):
    service = PhenomenonService(db)
    created = service.create(name="Original Name", epistemic_status=EpistemicStatus.OBSERVED)

    updated = service.update(
        created.id,
        name="Updated Name",
        epistemic_status="hypothesized",
        description="New description added",
    )
    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.epistemic_status == EpistemicStatus.HYPOTHESIZED
    assert updated.description == "New description added"


def test_delete_phenomenon(db):
    service = PhenomenonService(db)
    created = service.create(name="To Be Deleted")
    deleted_ok = service.delete(created.id)
    assert deleted_ok is True

    assert service.get(created.id) is None
    assert service.delete(created.id) is False


def test_invalid_epistemic_state_rejected(db):
    service = PhenomenonService(db)
    with pytest.raises(ValueError):
        service.create(name="Invalid State Test", epistemic_status="INVALID_EPISTEMIC_STATUS")

    created = service.create(name="Valid State Test", epistemic_status=EpistemicStatus.OBSERVED)
    with pytest.raises(ValueError):
        service.update(created.id, epistemic_status="NON_EXISTENT_STATUS")


def test_phenomenon_default_not_fact(db):
    """Ensure default status is OBSERVED and registering a phenomenon does not mean fact/VERIFIED."""
    service = PhenomenonService(db)
    phenomenon = service.create(name="Default State Phenomenon")
    assert phenomenon.epistemic_status == EpistemicStatus.OBSERVED
    assert phenomenon.epistemic_status != EpistemicStatus.VERIFIED

    # Check that Phenomenon model default is EpistemicStatus.OBSERVED upon DB insert
    direct_p = Phenomenon(name="Model Default")
    db.add(direct_p)
    db.commit()
    db.refresh(direct_p)
    assert direct_p.epistemic_status == EpistemicStatus.OBSERVED
    assert direct_p.epistemic_status != EpistemicStatus.VERIFIED


def test_phenomenon_provenance_preserved(db):
    service = PhenomenonService(db)
    provenance_data = {
        "evidence_ids": ["ev-001", "ev-002"],
        "source_references": ["http://example.com/obs/1"],
        "nested_meta": {"agent": "observer-1", "score": 0.95},
    }
    phenomenon = service.create(name="Provenance Test", provenance=provenance_data)
    assert phenomenon.provenance == provenance_data

    retrieved = service.get(phenomenon.id)
    assert retrieved.provenance["evidence_ids"] == ["ev-001", "ev-002"]
    assert retrieved.provenance["nested_meta"]["score"] == 0.95


def test_phenomenon_source_optional(db):
    service = PhenomenonService(db)
    no_source = service.create(name="No Source Phenomenon")
    assert no_source.source is None

    with_source = service.create(name="With Source Phenomenon", source="Sensor Array 5")
    assert with_source.source == "Sensor Array 5"
