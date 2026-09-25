import pytest
from smos.models.domain_event import DomainEvent, DomainEventType
from smos.models.phenomenon import Phenomenon
from smos.services.domain_event_service import DomainEventService
from smos.services.phenomenon_service import PhenomenonService
from smos.models.models import EpistemicStatus


@pytest.fixture(autouse=True)
def cleanup_db(db):
    db.query(DomainEvent).delete()
    db.query(Phenomenon).delete()
    db.commit()


def test_reconstruct_entity_full_lifecycle(db):
    event_service = DomainEventService(db)
    event_service.record("phenomenon", 10, DomainEventType.CREATED, changes={"name": "P1"})
    event_service.record("phenomenon", 10, DomainEventType.UPDATED, changes={"name": {"old": "P1", "new": "P2"}})
    event_service.record("phenomenon", 10, DomainEventType.DELETED)

    reconstruction = event_service.reconstruct_entity("phenomenon", 10)
    assert reconstruction["entity_type"] == "phenomenon"
    assert reconstruction["entity_id"] == 10
    assert reconstruction["event_count"] == 3
    assert len(reconstruction["events"]) == 3
    assert reconstruction["reconstruction_note"].startswith("Reconstructed from DomainEvent records")


def test_reconstruct_entity_returns_events_in_order(db):
    event_service = DomainEventService(db)
    e1 = event_service.record("context", 5, DomainEventType.CREATED)
    e2 = event_service.record("context", 5, DomainEventType.UPDATED)
    e3 = event_service.record("context", 5, DomainEventType.STATE_CHANGED)

    events = event_service.reconstruct_lifecycle("context", 5)
    assert len(events) == 3
    assert [e["id"] for e in events] == [e1.id, e2.id, e3.id]


def test_reconstruct_entity_includes_event_count(db):
    event_service = DomainEventService(db)
    for _ in range(4):
        event_service.record("constraint", 99, DomainEventType.CREATED)

    recon = event_service.reconstruct_entity("constraint", 99)
    assert recon["event_count"] == 4


def test_reconstruct_entity_empty_for_unknown(db):
    event_service = DomainEventService(db)
    recon = event_service.reconstruct_entity("unknown_entity", 999)
    assert recon["entity_type"] == "unknown_entity"
    assert recon["entity_id"] == 999
    assert recon["event_count"] == 0
    assert recon["created_at"] is None
    assert recon["updated_at"] is None
    assert recon["events"] == []


def test_reconstruct_lifecycle_create_update_delete(db):
    event_service = DomainEventService(db)
    event_service.record("prediction", 1, DomainEventType.CREATED)
    event_service.record("prediction", 1, DomainEventType.UPDATED)
    event_service.record("prediction", 1, DomainEventType.DELETED)

    lifecycle = event_service.reconstruct_lifecycle("prediction", 1)
    types = [e["event_type"] for e in lifecycle]
    assert types == ["CREATED", "UPDATED", "DELETED"]


def test_phenomenon_lifecycle_reconstruction_end_to_end(db):
    """Full lifecycle reconstruction scenario for Phenomenon from ТЗ:
    - create
    - update name
    - link context (context_ids in event)
    - update epistemic_status (STATE_CHANGED)
    Reconstruct from events and assert who, what, when, context_ids, evidence_ids, changes.
    """
    event_service = DomainEventService(db)
    p_service = PhenomenonService(db, event_service=event_service)

    # 1. Create
    p = p_service.create(
        name="Aurora Emergence",
        description="Initial observation",
        epistemic_status=EpistemicStatus.OBSERVED,
        actor_type="cosmonaut",
        actor_id=101,
        evidence_ids=[501],
    )
    p_id = p.id

    # 2. Update name
    p_service.update(
        p_id,
        name="Geomagnetic Aurora Emergence",
        actor_type="cosmonaut",
        actor_id=101,
        evidence_ids=[501, 502],
    )

    # 3. Link context
    p_service.link_context(
        p_id,
        context_id=42,
        actor_type="llm",
        actor_id=202,
        evidence_ids=[503],
    )

    # 4. Update epistemic status
    p_service.update(
        p_id,
        epistemic_status=EpistemicStatus.INFERRED,
        actor_type="system",
        actor_id=303,
        evidence_ids=[504],
    )

    # Reconstruct history
    recon = event_service.reconstruct_entity("phenomenon", p_id)
    lifecycle = recon["events"]

    assert recon["event_count"] == 4
    assert len(lifecycle) == 4

    # Step 1 Assertions: CREATED
    ev0 = lifecycle[0]
    assert ev0["event_type"] == "CREATED"
    assert ev0["actor_type"] == "cosmonaut"
    assert ev0["actor_id"] == 101
    assert ev0["evidence_ids"] == [501]

    # Step 2 Assertions: UPDATED (name)
    ev1 = lifecycle[1]
    assert ev1["event_type"] == "UPDATED"
    assert ev1["actor_type"] == "cosmonaut"
    assert ev1["actor_id"] == 101
    assert ev1["changes"]["name"] == {
        "old": "Aurora Emergence",
        "new": "Geomagnetic Aurora Emergence",
    }
    assert ev1["evidence_ids"] == [501, 502]

    # Step 3 Assertions: LINKED (context)
    ev2 = lifecycle[2]
    assert ev2["event_type"] == "LINKED"
    assert ev2["actor_type"] == "llm"
    assert ev2["actor_id"] == 202
    assert ev2["context_ids"] == [42]
    assert ev2["evidence_ids"] == [503]

    # Step 4 Assertions: STATE_CHANGED (epistemic_status)
    ev3 = lifecycle[3]
    assert ev3["event_type"] == "STATE_CHANGED"
    assert ev3["actor_type"] == "system"
    assert ev3["actor_id"] == 303
    assert ev3["changes"]["epistemic_status"] == {
        "old": "OBSERVED",
        "new": "INFERRED",
    }
    assert ev3["evidence_ids"] == [504]

    # Assert creation order timestamp monotonicity (when)
    created_ats = [ev["created_at"] for ev in lifecycle]
    assert created_ats == sorted(created_ats)
