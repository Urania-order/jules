import pytest
from smos.models.domain_event import DomainEvent, DomainEventType
from smos.models.phenomenon import Phenomenon
from smos.services.domain_event_service import DomainEventService
from smos.services.phenomenon_service import PhenomenonService


@pytest.fixture(autouse=True)
def cleanup_db(db):
    db.query(DomainEvent).delete()
    db.query(Phenomenon).delete()
    db.commit()


def test_record_event_created(db):
    service = DomainEventService(db)
    event = service.record(
        entity_type="phenomenon",
        entity_id=1,
        event_type=DomainEventType.CREATED,
        changes={"name": "New Phenomenon"},
    )
    assert event.id is not None
    assert event.entity_type == "phenomenon"
    assert event.entity_id == 1
    assert event.event_type == DomainEventType.CREATED
    assert event.changes == {"name": "New Phenomenon"}


def test_record_event_updated_with_changes(db):
    service = DomainEventService(db)
    event = service.record(
        entity_type="context",
        entity_id=2,
        event_type="UPDATED",
        changes={"name": {"old": "Old Name", "new": "New Name"}},
    )
    assert event.event_type == DomainEventType.UPDATED
    assert event.changes["name"]["old"] == "Old Name"
    assert event.changes["name"]["new"] == "New Name"


def test_record_event_deleted(db):
    service = DomainEventService(db)
    event = service.record(
        entity_type="constraint",
        entity_id=3,
        event_type=DomainEventType.DELETED,
    )
    assert event.event_type == DomainEventType.DELETED


def test_record_event_with_actor(db):
    service = DomainEventService(db)
    event = service.record(
        entity_type="prediction",
        entity_id=4,
        event_type=DomainEventType.CREATED,
        actor_type="cosmonaut",
        actor_id=42,
    )
    assert event.actor_type == "cosmonaut"
    assert event.actor_id == 42


def test_record_event_with_context_ids(db):
    service = DomainEventService(db)
    event = service.record(
        entity_type="phenomenon",
        entity_id=1,
        event_type=DomainEventType.LINKED,
        context_ids=[10, 20],
    )
    assert event.context_ids == [10, 20]


def test_record_event_with_evidence_ids(db):
    service = DomainEventService(db)
    event = service.record(
        entity_type="phenomenon",
        entity_id=1,
        event_type=DomainEventType.UPDATED,
        evidence_ids=[101, 102],
    )
    assert event.evidence_ids == [101, 102]


def test_record_event_changes_json(db):
    service = DomainEventService(db)
    changes = {"status": {"old": "OBSERVED", "new": "INFERRED"}, "score": 0.95}
    event = service.record(
        entity_type="phenomenon",
        entity_id=1,
        event_type=DomainEventType.STATE_CHANGED,
        changes=changes,
    )
    assert event.changes == changes


def test_list_for_entity(db):
    service = DomainEventService(db)
    e1 = service.record("phenomenon", 1, DomainEventType.CREATED)
    e2 = service.record("phenomenon", 1, DomainEventType.UPDATED)
    service.record("phenomenon", 2, DomainEventType.CREATED)

    phenom1_events = service.list_for_entity("phenomenon", 1)
    assert len(phenom1_events) == 2
    assert phenom1_events[0].id == e1.id
    assert phenom1_events[1].id == e2.id


def test_list_recent(db):
    service = DomainEventService(db)
    for i in range(5):
        service.record("phenomenon", i, DomainEventType.CREATED)

    recent = service.list_recent(limit=3)
    assert len(recent) == 3


def test_get_event(db):
    service = DomainEventService(db)
    event = service.record("phenomenon", 1, DomainEventType.CREATED)
    fetched = service.get(event.id)
    assert fetched is not None
    assert fetched.id == event.id


def test_event_to_dict(db):
    service = DomainEventService(db)
    event = service.record(
        entity_type="phenomenon",
        entity_id=1,
        event_type=DomainEventType.CREATED,
        actor_type="user",
        actor_id=5,
        context_ids=[1],
        evidence_ids=[2],
        changes={"a": 1},
        provenance={"source": "test"},
    )
    d = event.to_dict()
    assert d["id"] == event.id
    assert d["actor_type"] == "user"
    assert d["actor_id"] == 5
    assert d["entity_type"] == "phenomenon"
    assert d["entity_id"] == 1
    assert d["event_type"] == "CREATED"
    assert d["context_ids"] == [1]
    assert d["evidence_ids"] == [2]
    assert d["changes"] == {"a": 1}
    assert d["provenance"] == {"source": "test"}


def test_actor_fields_optional(db):
    service = DomainEventService(db)
    event = service.record("phenomenon", 1, DomainEventType.CREATED)
    assert event.actor_type is None
    assert event.actor_id is None


def test_event_does_not_modify_entity(db):
    event_service = DomainEventService(db)
    p_service = PhenomenonService(db, event_service=event_service)
    p = p_service.create("Test Phenomenon")
    original_name = p.name

    event_service.record("phenomenon", p.id, DomainEventType.UPDATED, changes={"name": "Fake Change"})
    
    fetched = p_service.get(p.id)
    assert fetched.name == original_name


def test_event_is_append_only_no_update_method(db):
    service = DomainEventService(db)
    assert not hasattr(service, "update")
    assert not hasattr(service, "delete")


def test_poc_phenomenon_create_logs_event(db):
    event_service = DomainEventService(db)
    p_service = PhenomenonService(db, event_service=event_service)
    
    p = p_service.create("Solar Flare", actor_type="cosmonaut", actor_id=1)
    events = event_service.list_for_entity("phenomenon", p.id)
    assert len(events) == 1
    assert events[0].event_type == DomainEventType.CREATED
    assert events[0].actor_type == "cosmonaut"
    assert events[0].actor_id == 1


def test_poc_phenomenon_update_logs_event_with_changes(db):
    event_service = DomainEventService(db)
    p_service = PhenomenonService(db, event_service=event_service)
    
    p = p_service.create("Initial Name")
    p_service.update(p.id, name="Updated Name", actor_type="user", actor_id=2)

    events = event_service.list_for_entity("phenomenon", p.id)
    assert len(events) == 2
    update_event = events[1]
    assert update_event.event_type == DomainEventType.UPDATED
    assert update_event.changes["name"] == {"old": "Initial Name", "new": "Updated Name"}


def test_poc_phenomenon_delete_logs_event(db):
    event_service = DomainEventService(db)
    p_service = PhenomenonService(db, event_service=event_service)
    
    p = p_service.create("Temporary Phenomenon")
    p_id = p.id
    p_service.delete(p_id, actor_type="system")

    events = event_service.list_for_entity("phenomenon", p_id)
    assert len(events) == 2
    assert events[1].event_type == DomainEventType.DELETED
    assert events[1].actor_type == "system"
